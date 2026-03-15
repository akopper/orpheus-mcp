# Orpheus-MCP

A standalone MCP (Model Context Protocol) server for Orpheus TTS - generate speech and audiobooks with AI agents.

## Overview

Orpheus-MCP provides text-to-speech capabilities through the Model Context Protocol, enabling integration with AI agents and tools like Claude Desktop, mcporter, and opencode. Generate natural-sounding speech with 25 voices across 8 languages, complete with emotion tags and voice cloning capabilities.

## Features

- **25 Voices**: 8 languages including English, French, German, Korean, Hindi, Mandarin, Spanish, Italian
- **Emotion Tags**: Add `<laugh>`, `<sigh>`, `<chuckle>`, and more for expressive speech
- **MCP Integration**: Works with any MCP-compatible client
- **Auto-Setup**: Wrapper script handles virtual environment and dependencies automatically
- **Standalone**: Runs offline with local llama.cpp inference

## Quick Start

### Prerequisites

- Python 3.11+
- llama.cpp server binary
- Orpheus model file (~3-4GB)

### 1. Install llama.cpp

**macOS (Apple Silicon):**
```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -B build -DLLAMA_METAL=ON
cmake --build build --config Release -j 8
# Binary at: build/bin/llama-server
```

**Other platforms:** Download from [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases)

### 2. Download Model

Download an Orpheus model from Hugging Face:

| Model | Link | Size |
|-------|------|------|
| Orpheus-3b (Official) | [huggingface.co/baseten/orpheus-3b-0.1-ft](https://huggingface.co/baseten/orpheus-3b-0.1-ft) | ~4GB |
| Orpheus-3b-FT-Q8_0 (Quantized) | [huggingface.co/lex-au/Orpheus-3b-FT-Q8_0.gguf](https://huggingface.co/lex-au/Orpheus-3b-FT-Q8_0.gguf) | ~3.8GB |
| Orpheus-3b-0.1-ft-UD-Q8_K_XL | [huggingface.co/akocop/orpheus-3b-0.1-ft-UD-Q8_K_XL.gguf](https://huggingface.co/akocop/orpheus-3b-0.1-ft-UD-Q8_K_XL.gguf) | ~3.8GB |

```bash
# Option 1: Download official model (requires conversion)
mkdir -p models
wget https://huggingface.co/baseten/orpheus-3b-0.1-ft/resolve/main/model-00001-of-00085.safetensors -P models/

# Option 2: Download pre-quantized GGUF (recommended - works out of box)
mkdir -p models
wget https://huggingface.co/lex-au/Orpheus-3b-FT-Q8_0.gguf -O models/Orpheus-3b-FT-Q8_0.gguf
```

### 3. Configure mcporter

Add to `~/.mcporter/mcporter.json`:

```json
{
  "mcpServers": {
    "orpheus-tts": {
      "command": "/path/to/orpheus-mcp/run_mcp_server.sh",
      "env": {
        "ORPHEUS_MODEL_PATH": "/path/to/models/orpheus-3b-0.1-ft-UD-Q8_K_XL.gguf",
        "ORPHEUS_LLAMA_CPP_PATH": "/path/to/llama.cpp/build/bin/llama-server"
      }
    }
  }
}
```

### 4. Run

```bash
# Test it works
mcporter call orpheus-tts.list_voices
```

The wrapper script (`run_mcp_server.sh`) automatically:
- Creates Python virtual environment (if needed)
- Installs dependencies
- Starts llama.cpp server
- Runs MCP server

## MCP Tools

### `list_voices`
List all available voices.

```bash
mcporter call orpheus-tts.list_voices
```

### `get_voice_info`
Get detailed information about a voice.

```bash
mcporter call orpheus-tts.get_voice_info voice=tara
```

### `estimate_tokens`
Estimate token count for text (helps plan chunking).

```bash
mcporter call orpheus-tts.estimate_tokens text="Your text here"
```

### `generate_speech`
Convert text to speech.

```bash
mcporter call orpheus-tts.generate_speech \
    text="Hello world" \
    voice=tara
```

**With emotion tags:**
```bash
mcporter call orpheus-tts.generate_speech \
    text="That's amazing! <laugh> I can't believe it!" \
    voice=tara
```

## Available Voices

**English:** tara, leah, jess, leo, dan, mia, zac, zoe  
**French:** pierre, amelie, marie  
**German:** jana, thomas, max  
**Korean:** 유나, 준서  
**Hindi:** ऋतिका  
**Mandarin:** 长乐, 白芷  
**Spanish:** javi, sergio, maria  
**Italian:** pietro, giulia, carlo

## Emotion Tags

- `<laugh>` - Laughter
- `<chuckle>` - Light amusement  
- `<sigh>` - Weariness
- `<gasp>` - Surprise
- `<sniffle>` - Sadness
- `<cough>` - Hesitation
- `<groan>` - Frustration
- `<yawn>` - Tiredness

## Configuration

### mcporter

Add to `~/.mcporter/mcporter.json`:
```json
{
  "mcpServers": {
    "orpheus-tts": {
      "command": "/path/to/orpheus-mcp/run_mcp_server.sh",
      "env": {
        "ORPHEUS_MODEL_PATH": "/path/to/Orpheus-3b-FT-Q8_0.gguf",
        "ORPHEUS_IDLE_TIMEOUT": "5m",
        "ORPHEUS_STREAM_TIMEOUT": "15s"
      }
    }
  }
}
```

**Note:** The mcporter daemon (`lifecycle: "keep-alive"`) requires ALL servers in your config to start successfully. If any server (like jira, etc.) fails to start, the entire daemon fails. For now, use the default ephemeral mode - the MCP server will start on demand.

### Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "orpheus-tts": {
      "command": "/path/to/orpheus-mcp/run_mcp_server.sh",
      "env": {
        "ORPHEUS_MODEL_PATH": "/path/to/Orpheus-3b-FT-Q8_0.gguf"
      }
    }
  }
}
```

## Testing

Run integration tests:
```bash
./test_mcporter_integration.sh
```

Generate sample audio files:
```bash
./generate_samples.py
```

## Project Structure

```
orpheus-mcp/
├── mcp_server.py              # MCP server implementation
├── run_mcp_server.sh         # Auto-setup wrapper script
├── tts_engine/               # Core TTS functionality
│   ├── inference.py         # Token generation
│   └── speechpipe.py        # Audio synthesis
├── generate_samples.py       # Sample generation script
├── test_mcporter_integration.sh  # Integration tests
├── AGENTS.md                 # Agent instructions
└── requirements.txt         # Python dependencies
```

## Environment Variables

- `ORPHEUS_MODEL_PATH` - Path to Orpheus GGUF model (required)
- `ORPHEUS_LLAMA_CPP_PATH` - Path to llama-server binary (optional, auto-detected)
- `ORPHEUS_OUTPUT_DIR` - Output directory (default: ~/Documents/tts)
- `ORPHEUS_IDLE_TIMEOUT` - Idle timeout before stopping llama-server (default: 5m)
  - Supports duration strings: `300`, `5m`, `1h30m`, etc.
- `ORPHEUS_STREAM_TIMEOUT` - Stream liveness timeout (default: 15s)
  - Supports duration strings: `15`, `15s`, `1m30s`, etc.
- `ORPHEUS_AUTO_START` - Auto-start llama-server (default: true)
- `MCP_TRANSPORT` - Transport type: stdio or sse (default: stdio)

## Pitfalls

### Slow Hardware

On slower hardware (CPU-only or older GPUs), token generation may be slow enough that the stream liveness timeout triggers. If you experience timeouts on longer texts:

1. Increase `ORPHEUS_STREAM_TIMEOUT` (e.g., `30s`, `1m`)
2. Use shorter text chunks via the `estimate_tokens` tool to plan chunking

### mcporter Daemon Limitation

The mcporter daemon (`"lifecycle": "keep-alive"`) requires ALL servers in your config to start successfully. If any server (like jira, etc.) fails to start, the entire daemon fails. 

Use default ephemeral mode instead - the MCP server starts on demand and the idle timeout watchdog manages llama-server lifecycle automatically.

## License

Apache License 2.0

## Acknowledgments

Based on [Orpheus-FastAPI](https://github.com/Lex-au/Orpheus-FastAPI) by Lex-au. This fork focuses exclusively on MCP server functionality for agentic workflows.
