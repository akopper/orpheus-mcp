#!/usr/bin/env python3
"""
Orpheus MCP Server - Model Context Protocol server for Orpheus TTS

This server provides MCP tools for text-to-speech generation using the Orpheus model.
It can run standalone and manages the llama.cpp server lifecycle automatically.

Usage:
    python mcp_server.py

Environment Variables:
    ORPHEUS_API_URL: URL for llama.cpp server (default: auto-start local server)
    ORPHEUS_MODEL_PATH: Path to the Orpheus GGUF model
    ORPHEUS_LLAMA_CPP_PATH: Path to llama.cpp server binary
    MCP_TRANSPORT: Transport type (stdio or sse, default: stdio)
    MCP_PORT: Port for SSE transport (default: 5006)
"""

import os
import sys
import json
import time
import wave
import base64
import asyncio
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel,
)

# Load environment variables
load_dotenv()

# Import TTS engine
from tts_engine import (
    generate_speech_from_api,
    AVAILABLE_VOICES,
    DEFAULT_VOICE,
    VOICE_TO_LANGUAGE,
    AVAILABLE_LANGUAGES,
    list_available_voices,
)
from tts_engine.inference import generate_tokens_from_api, tokens_decoder_sync


def get_default_output_dir() -> str:
    """Get default output directory based on platform"""
    system = platform.system()
    if system == "Darwin":
        return os.path.join(os.path.expanduser("~/Documents"), "tts")
    elif system == "Windows":
        return os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "tts")
    else:
        return os.path.join(os.path.expanduser("~/Documents"), "tts")


@dataclass
class ServerConfig:
    """Server configuration"""

    api_url: str = "http://127.0.0.1:1234/v1/completions"
    model_path: Optional[str] = None
    llama_cpp_path: Optional[str] = None
    auto_start_llama: bool = True
    transport: str = "stdio"
    port: int = 5006
    output_dir: str = ""


def get_config() -> ServerConfig:
    """Load configuration from environment variables"""
    default_output = get_default_output_dir()
    return ServerConfig(
        api_url=os.environ.get(
            "ORPHEUS_API_URL", "http://127.0.0.1:1234/v1/completions"
        ),
        model_path=os.environ.get("ORPHEUS_MODEL_PATH"),
        llama_cpp_path=os.environ.get("ORPHEUS_LLAMA_CPP_PATH"),
        auto_start_llama=os.environ.get("ORPHEUS_AUTO_START", "true").lower() == "true",
        transport=os.environ.get("MCP_TRANSPORT", "stdio"),
        port=int(os.environ.get("MCP_PORT", "5006")),
        output_dir=os.environ.get("ORPHEUS_OUTPUT_DIR", default_output),
    )


class LlamaServerManager:
    """Manages the llama.cpp server lifecycle"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.server_ready = False

    def is_server_running(self) -> bool:
        """Check if llama.cpp server is already running"""
        import requests

        try:
            response = requests.get(
                self.config.api_url.replace("/v1/completions", "/health"), timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def start_server(self) -> bool:
        """Start the llama.cpp server"""
        if self.is_server_running():
            print("✓ llama.cpp server already running", file=sys.stderr)
            return True

        if not self.config.model_path:
            print("✗ ORPHEUS_MODEL_PATH not set", file=sys.stderr)
            return False

        if not os.path.exists(self.config.model_path):
            print(f"✗ Model not found: {self.config.model_path}", file=sys.stderr)
            return False

        # Find llama-server binary
        llama_server = self.config.llama_cpp_path or self._find_llama_server()
        if not llama_server:
            print("✗ llama-server binary not found", file=sys.stderr)
            return False

        # Start server
        cmd = [
            llama_server,
            "-m",
            self.config.model_path,
            "--host",
            "127.0.0.1",
            "--port",
            "1234",
            "-ngl",
            "99",  # Use all GPU layers
        ]

        print(f"Starting llama.cpp server...", file=sys.stderr)
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for server to be ready
            for i in range(60):  # 60 second timeout
                time.sleep(1)
                if self.is_server_running():
                    print("✓ llama.cpp server ready", file=sys.stderr)
                    return True

            print("✗ Server failed to start within timeout", file=sys.stderr)
            return False

        except Exception as e:
            print(f"✗ Failed to start server: {e}", file=sys.stderr)
            return False

    def _find_llama_server(self) -> Optional[str]:
        """Find llama-server binary in common locations"""
        custom_path = os.environ.get("LLAMA_SERVER_PATH")
        if (
            custom_path
            and os.path.isfile(custom_path)
            and os.access(custom_path, os.X_OK)
        ):
            return custom_path

        paths = [
            "llama-server",
            "./llama-server",
        ]

        home = Path.home()
        build_paths = [
            home / "llama.cpp" / "build" / "bin" / "llama-server",
            home / "llama.cpp" / "llama-server",
        ]

        all_paths = paths + [str(p) for p in build_paths]

        for path in all_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
            if os.path.isfile(path + ".exe"):
                return path + ".exe"

        return None

    def stop_server(self):
        """Stop the llama.cpp server"""
        if self.process:
            print("Stopping llama.cpp server...", file=sys.stderr)
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.process = None


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)"""
    # Rough estimate: ~4 characters per token for English
    return len(text) // 4 + 1


# Create MCP server
app = Server("orpheus-tts")

# Global state
server_manager: Optional[LlamaServerManager] = None
config: ServerConfig = get_config()


@app.call_tool()
async def handle_tool_call(
    name: str, arguments: dict | None
) -> List[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls"""
    arguments = arguments or {}

    if name == "generate_speech":
        return await handle_generate_speech(arguments)
    elif name == "list_voices":
        return await handle_list_voices()
    elif name == "get_voice_info":
        return await handle_get_voice_info(arguments)
    elif name == "estimate_tokens":
        return await handle_estimate_tokens(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_speech(arguments: dict) -> List[TextContent]:
    """Generate speech from text"""
    text = arguments.get("text", "")
    voice = arguments.get("voice", DEFAULT_VOICE)
    output_path = arguments.get("output_path")
    streaming = arguments.get("streaming", False)

    if not text:
        return [TextContent(type="text", text="Error: text is required")]

    if voice not in AVAILABLE_VOICES:
        return [
            TextContent(
                type="text",
                text=f"Error: Invalid voice '{voice}'. Use list_voices to see available options.",
            )
        ]

    try:
        # Ensure output directory exists
        os.makedirs(config.output_dir, exist_ok=True)

        # Generate output path if not provided
        if not output_path:
            timestamp = int(time.time())
            output_path = os.path.join(
                config.output_dir, f"speech_{voice}_{timestamp}.wav"
            )

        # Generate speech in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        audio_segments = await loop.run_in_executor(
            None, generate_speech_from_api, text, voice, output_path
        )

        # Get file size
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        result = {
            "success": True,
            "output_path": output_path,
            "voice": voice,
            "text_length": len(text),
            "file_size_bytes": file_size,
            "streaming": streaming,
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error generating speech: {str(e)}")]


async def handle_list_voices() -> List[TextContent]:
    """List all available voices"""
    voices_info = []

    for voice in AVAILABLE_VOICES:
        lang = VOICE_TO_LANGUAGE.get(voice, "Unknown")
        voices_info.append(
            {
                "name": voice,
                "language": lang,
                "is_default": voice == DEFAULT_VOICE,
            }
        )

    result = {
        "voices": voices_info,
        "total": len(voices_info),
        "default": DEFAULT_VOICE,
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_get_voice_info(arguments: dict) -> List[TextContent]:
    """Get detailed information about a voice"""
    voice = arguments.get("voice", DEFAULT_VOICE)

    if voice not in AVAILABLE_VOICES:
        return [
            TextContent(
                type="text",
                text=f"Error: Voice '{voice}' not found. Use list_voices to see available options.",
            )
        ]

    language = VOICE_TO_LANGUAGE.get(voice, "Unknown")

    # Emotion tags supported by the model
    emotion_tags = [
        "<laugh>",
        "<chuckle>",
        "<sigh>",
        "<cough>",
        "<sniffle>",
        "<groan>",
        "<yawn>",
        "<gasp>",
    ]

    result = {
        "name": voice,
        "language": language,
        "language_code": language,
        "is_default": voice == DEFAULT_VOICE,
        "supported_emotions": emotion_tags,
        "sample_rate_hz": 24000,
        "format": "WAV",
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_estimate_tokens(arguments: dict) -> List[TextContent]:
    """Estimate token count for text"""
    text = arguments.get("text", "")

    if not text:
        return [TextContent(type="text", text="Error: text is required")]

    token_count = estimate_tokens(text)

    # Provide recommendations
    max_tokens = 8192  # Default max
    chunks_needed = (token_count // 800) + 1  # Conservative chunking

    result = {
        "text_length": len(text),
        "estimated_tokens": token_count,
        "max_tokens": max_tokens,
        "fits_in_single_request": token_count <= max_tokens,
        "recommended_chunks": chunks_needed if chunks_needed > 1 else 1,
        "recommended_chunk_size": 800,  # Conservative for safety
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="generate_speech",
            description="Convert text to speech using Orpheus TTS. Returns path to generated WAV file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to convert to speech. Supports emotion tags like <laugh>, <sigh>, etc.",
                    },
                    "voice": {
                        "type": "string",
                        "description": f"Voice to use. Default: {DEFAULT_VOICE}",
                        "enum": list(AVAILABLE_VOICES),
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional output file path. If not provided, saves to outputs/ directory.",
                    },
                    "streaming": {
                        "type": "boolean",
                        "description": "Whether to stream audio chunks (for real-time playback). Default: false",
                        "default": False,
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="list_voices",
            description="List all available voices for speech generation.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_voice_info",
            description="Get detailed information about a specific voice including language and supported features.",
            inputSchema={
                "type": "object",
                "properties": {
                    "voice": {
                        "type": "string",
                        "description": "Voice name to get info for",
                        "enum": list(AVAILABLE_VOICES),
                    },
                },
                "required": ["voice"],
            },
        ),
        Tool(
            name="estimate_tokens",
            description="Estimate token count for text to help plan chunking strategy for long texts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to estimate token count for",
                    },
                },
                "required": ["text"],
            },
        ),
    ]


@asynccontextmanager
async def app_lifespan():
    """Manage server lifecycle"""
    global server_manager

    config = get_config()

    # Start llama.cpp server if needed
    if config.auto_start_llama:
        server_manager = LlamaServerManager(config)
        if not server_manager.start_server():
            print("⚠️ Warning: Could not start llama.cpp server", file=sys.stderr)
            print("  Make sure ORPHEUS_MODEL_PATH is set correctly", file=sys.stderr)

    yield

    # Cleanup
    if server_manager:
        server_manager.stop_server()


async def main():
    """Main entry point"""
    config = get_config()

    # Ensure output directory exists
    os.makedirs(config.output_dir, exist_ok=True)

    # Run server with appropriate transport
    if config.transport == "stdio":
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    elif config.transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0],
                    streams[1],
                    app.create_initialization_options(),
                )

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages/", endpoint=sse.handle_post_message),
            ],
        )

        import uvicorn

        uvicorn.run(starlette_app, host="0.0.0.0", port=config.port)
    else:
        print(f"Unknown transport: {config.transport}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
