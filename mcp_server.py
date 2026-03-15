#!/usr/bin/env python3
"""
Orpheus MCP Server - Model Context Protocol server for Orpheus TTS

This server provides MCP tools for text-to-speech generation using the Orpheus model.
llama-server must be started separately before using this MCP server.

Usage:
    python mcp_server.py

Environment Variables:
    ORPHEUS_API_URL: URL for llama.cpp server (default: http://127.0.0.1:1234/v1/completions)
    ORPHEUS_MODEL_PATH: Path to the Orpheus GGUF model (for your reference)
    MCP_TRANSPORT: Transport type (stdio or sse, default: stdio)
    MCP_PORT: Port for SSE transport (default: 5006)

Prerequisites:
    Start llama-server before using this MCP server:
    llama-server -m /path/to/model.gguf --port 1234 -ngl 99
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
import threading
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass


def parse_duration(value: Optional[str], default_seconds: int) -> int:
    """
    Parse duration string to seconds.

    Supports formats:
    - Plain number: "300" -> 300 seconds
    - With suffix: "5m" -> 300 seconds, "30s" -> 30 seconds, "1h" -> 3600 seconds
    - Mixed: "1h30m" -> 5400 seconds

    Args:
        value: Duration string to parse (can be None or empty)
        default_seconds: Default value if parsing fails

    Returns:
        Duration in seconds
    """
    if not value:
        return default_seconds

    # Try plain number first (backward compatibility)
    try:
        return int(value)
    except ValueError:
        pass

    # Parse duration string (e.g., "5m", "30s", "1h30m")
    total_seconds = 0
    pattern = r"(\d+)([smh])"
    matches = re.findall(pattern, value.lower())

    if not matches:
        print(
            f"WARNING: Invalid duration format '{value}', using default {default_seconds}s"
        )
        return default_seconds

    for num, unit in matches:
        num = int(num)
        if unit == "s":
            total_seconds += num
        elif unit == "m":
            total_seconds += num * 60
        elif unit == "h":
            total_seconds += num * 3600

    return total_seconds if total_seconds > 0 else default_seconds


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

# Import Voice Cloning modules
try:
    from voice_cloning import SNACTokenizer, VoiceCloneEngine, ReferenceStore
    from voice_cloning.config import (
        TIMEOUT_CLONE_DIRECT,
        TIMEOUT_CLONE_REFERENCE,
        get_reference_dir,
    )

    VOICE_CLONING_AVAILABLE = True
except ImportError as e:
    VOICE_CLONING_AVAILABLE = False
    print(f"Voice cloning not available: {e}", file=sys.stderr)


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
        transport=os.environ.get("MCP_TRANSPORT", "stdio"),
        port=int(os.environ.get("MCP_PORT", "5006")),
        output_dir=os.environ.get("ORPHEUS_OUTPUT_DIR", default_output),
    )


def check_server_running() -> bool:
    """Check if llama-server is reachable at the configured API URL"""
    import requests

    try:
        response = requests.post(
            config.api_url,
            json={"prompt": "hi", "max_tokens": 1, "cache_prompt": False},
            timeout=2,
        )
        return response.status_code in (200, 400)
    except:
        return False


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)"""
    # Rough estimate: ~4 characters per token for English
    return len(text) // 4 + 1


# Create MCP server
app = Server("orpheus-tts")

# Global state
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
    elif VOICE_CLONING_AVAILABLE and name == "clone_voice_direct":
        return await _handle_clone_voice_direct(arguments)
    elif VOICE_CLONING_AVAILABLE and name == "clone_voice":
        return await _handle_clone_voice(arguments)
    elif VOICE_CLONING_AVAILABLE and name == "list_reference_voices":
        return await _handle_list_reference_voices(arguments)
    elif VOICE_CLONING_AVAILABLE and name == "delete_reference_voice":
        return await _handle_delete_reference_voice(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_speech(
    arguments: dict,
) -> List[TextContent | ImageContent | EmbeddedResource]:
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

    if not check_server_running():
        return [
            TextContent(
                type="text",
                text=f"Error: llama-server not running at {config.api_url}. Please start llama-server before use:\n\nllama-server -m /path/to/model.gguf --port 1234 -ngl 99",
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


async def handle_list_voices() -> List[TextContent | ImageContent | EmbeddedResource]:
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


async def handle_get_voice_info(
    arguments: dict,
) -> List[TextContent | ImageContent | EmbeddedResource]:
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


async def handle_estimate_tokens(
    arguments: dict,
) -> List[TextContent | ImageContent | EmbeddedResource]:
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


def _get_voice_cloning_tools() -> List[Tool]:
    """Get voice cloning tools if available"""
    if not VOICE_CLONING_AVAILABLE:
        return []

    return [
        Tool(
            name="clone_voice_direct",
            description="Clone voice from an audio file and optionally save for later use.",
            inputSchema={
                "type": "object",
                "properties": {
                    "audio_path": {
                        "type": "string",
                        "description": "Path to reference audio file",
                    },
                    "transcript": {
                        "type": "string",
                        "description": "Transcript of reference audio",
                    },
                    "text": {"type": "string", "description": "Text to generate"},
                    "output_path": {
                        "type": "string",
                        "description": "Optional output path",
                    },
                    "save_reference": {
                        "type": "string",
                        "description": "Optional name to save reference",
                    },
                    "voice_name": {
                        "type": "string",
                        "description": "Optional display name",
                    },
                },
                "required": ["audio_path", "transcript", "text"],
            },
        ),
        Tool(
            name="clone_voice",
            description="Generate speech using a saved reference voice.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference_name": {
                        "type": "string",
                        "description": "Saved reference name",
                    },
                    "text": {"type": "string", "description": "Text to generate"},
                    "output_path": {
                        "type": "string",
                        "description": "Optional output path",
                    },
                },
                "required": ["reference_name", "text"],
            },
        ),
        Tool(
            name="list_reference_voices",
            description="List all saved reference voices.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="delete_reference_voice",
            description="Delete a saved reference voice.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Reference name to delete",
                    }
                },
                "required": ["name"],
            },
        ),
    ]


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
    ] + _get_voice_cloning_tools()


def _get_voice_cloning_handlers():
    """Map tool names to their handlers"""
    return {
        "clone_voice_direct": _handle_clone_voice_direct,
        "clone_voice": _handle_clone_voice,
        "list_reference_voices": _handle_list_reference_voices,
        "delete_reference_voice": _handle_delete_reference_voice,
    }


async def _handle_clone_voice_direct(arguments: dict) -> List[TextContent]:
    """Handle clone_voice_direct tool call"""
    if not VOICE_CLONING_AVAILABLE:
        return [
            TextContent(
                type="text",
                text="Error: Voice cloning not available. Install required packages.",
            )
        ]

    audio_path = arguments.get("audio_path")
    transcript = arguments.get("transcript")
    text = arguments.get("text")
    output_path = arguments.get("output_path")
    save_reference = arguments.get("save_reference")
    voice_name = arguments.get("voice_name")

    if not all([audio_path, transcript, text]):
        return [
            TextContent(
                type="text", text="Error: audio_path, transcript, and text are required"
            )
        ]

    config = get_config()

    # Generate output path if not provided
    if not output_path:
        timestamp = int(time.time())
        output_path = os.path.join(config.output_dir, f"clone_{timestamp}.wav")

    # Ensure output directory exists
    os.makedirs(config.output_dir, exist_ok=True)

    try:
        # Save reference if requested
        if save_reference:
            store = ReferenceStore()
            store.save_reference(
                name=save_reference,
                audio_path=audio_path,
                transcript=transcript,
                voice_name=voice_name,
            )

        # Run voice cloning in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _clone_voice_sync,
            audio_path,
            transcript,
            text,
            output_path,
        )

        if result.success:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "output_path": result.output_path,
                            "reference_saved": bool(save_reference),
                            "duration_seconds": result.duration_seconds,
                        },
                        indent=2,
                    ),
                )
            ]
        else:
            return [TextContent(type="text", text=f"Error: {result.error}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def _clone_voice_sync(audio_path: str, transcript: str, text: str, output_path: str):
    """Synchronous wrapper for voice cloning"""
    engine = VoiceCloneEngine()
    return engine.clone_voice(
        reference_audio_path=audio_path,
        reference_transcript=transcript,
        text_to_speak=text,
        output_path=output_path,
    )


async def _handle_clone_voice(arguments: dict) -> List[TextContent]:
    """Handle clone_voice tool call"""
    if not VOICE_CLONING_AVAILABLE:
        return [TextContent(type="text", text="Error: Voice cloning not available")]

    reference_name = arguments.get("reference_name")
    text = arguments.get("text")
    output_path = arguments.get("output_path")

    if not all([reference_name, text]):
        return [
            TextContent(type="text", text="Error: reference_name and text are required")
        ]

    config = get_config()

    if not output_path:
        timestamp = int(time.time())
        output_path = os.path.join(config.output_dir, f"clone_{timestamp}.wav")

    os.makedirs(config.output_dir, exist_ok=True)

    try:
        store = ReferenceStore()
        ref = store.get_reference(reference_name)

        if not ref:
            return [
                TextContent(
                    type="text", text=f"Error: Reference '{reference_name}' not found"
                )
            ]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _clone_voice_sync,
            ref["audio_path"],
            store.get_transcript(reference_name),
            text,
            output_path,
        )

        if result.success:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "output_path": result.output_path,
                            "reference_name": reference_name,
                            "duration_seconds": result.duration_seconds,
                        },
                        indent=2,
                    ),
                )
            ]
        else:
            return [TextContent(type="text", text=f"Error: {result.error}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _handle_list_reference_voices(arguments: dict) -> List[TextContent]:
    """Handle list_reference_voices tool call"""
    if not VOICE_CLONING_AVAILABLE:
        return [TextContent(type="text", text="Error: Voice cloning not available")]

    try:
        store = ReferenceStore()
        refs = store.list_references()

        # Clean output (remove internal paths)
        for ref in refs:
            ref.pop("audio_path", None)
            ref.pop("transcript_path", None)
            ref.pop("reference_dir", None)

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "references": refs,
                        "total": len(refs),
                    },
                    indent=2,
                ),
            )
        ]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _handle_delete_reference_voice(arguments: dict) -> List[TextContent]:
    """Handle delete_reference_voice tool call"""
    if not VOICE_CLONING_AVAILABLE:
        return [TextContent(type="text", text="Error: Voice cloning not available")]

    name = arguments.get("name")

    if not name:
        return [TextContent(type="text", text="Error: name is required")]

    try:
        store = ReferenceStore()
        deleted = store.delete_reference(name)

        if deleted:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "deleted": name,
                        },
                        indent=2,
                    ),
                )
            ]
        else:
            return [
                TextContent(type="text", text=f"Error: Reference '{name}' not found")
            ]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


@asynccontextmanager
async def app_lifespan():
    """Manage server lifecycle"""
    yield


async def main():
    """Main entry point"""
    config = get_config()

    # Ensure output directory exists
    os.makedirs(config.output_dir, exist_ok=True)

    # Use lifespan context manager to handle server lifecycle (autostart, cleanup)
    async with app_lifespan():
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
