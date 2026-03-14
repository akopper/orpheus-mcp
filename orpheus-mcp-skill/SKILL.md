---
name: orpheus-tts
description: Use this skill when the user wants to generate speech or audio using Orpheus TTS via mcporter. This includes (1) converting text to speech, (2) generating audiobooks from long texts, (3) listing or selecting voices, (4) working with emotion tags for expressive speech, (5) estimating tokens for chunking long texts. Always use estimate_tokens first for texts over 500 characters to plan chunking.
---

# Orpheus TTS MCP - mcporter Usage Guide

This skill provides instructions for using the Orpheus TTS MCP server with mcporter to generate speech and audio.

## Quick Reference

```bash
# List available voices
mcporter call orpheus-tts.list_voices

# Get info about a specific voice
mcporter call orpheus-tts.get_voice_info voice=tara

# Estimate tokens for text (for long texts)
mcporter call orpheus-tts.estimate_tokens text="Your long text here..."

# Generate speech
mcporter call orpheus-tts.generate_speech text="Hello world" voice=tara
```

## Configuration

### mcporter Setup

Add to `~/.mcporter/mcporter.json`:

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

## Available Tools

### 1. list_voices

List all available voices with their languages.

```bash
mcporter call orpheus-tts.list_voices
```

**Returns:** JSON array of voices with language codes and default flag.

---

### 2. get_voice_info

Get detailed information about a specific voice.

```bash
mcporter call orpheus-tts.get_voice_info voice=tara
```

**Parameters:**
- `voice` (required): Voice name

**Returns:** Voice details including language, supported emotions, sample rate.

---

### 3. estimate_tokens

Estimate token count for text to plan chunking strategy. Always use this first for texts longer than 500 characters.

```bash
mcporter call orpheus-tts.estimate_tokens text="Your text here..."
```

**Parameters:**
- `text` (required): Text to estimate

**Returns:** Token count, chunking recommendations, whether text fits in single request.

---

### 4. generate_speech

Convert text to speech and save as WAV file.

```bash
mcporter call orpheus-tts.generate_speech \
    text="Hello world" \
    voice=tara \
    output_path=~/.openclaw/media/tts/hello.wav
```

**Parameters:**
- `text` (required): Text to convert. Supports emotion tags.
- `voice` (optional): Voice name. Default: "tara"
- `output_path` (optional): Output file path. Recommended: `~/.openclaw/media/tts/filename.wav`
- `streaming` (optional): For real-time playback. Default: false

**Returns:** JSON with success status, output path, voice, file size.

---

## Voice Selection

**English:** tara, leah, jess, leo, dan, mia, zac, zoe  
**French:** pierre, amelie, marie  
**German:** jana, thomas, max  
**Korean:** 유나, 준서  
**Hindi:** ऋतिका  
**Mandarin:** 长乐, 白芷  
**Spanish:** javi, sergio, maria  
**Italian:** pietro, giulia, carlo

**Default:** tara

---

## Emotion Tags

Add these tags in your text for expressive speech:

| Tag | Effect |
|-----|--------|
| `<laugh>` | Laughter |
| `<chuckle>` | Light amusement |
| `<sigh>` | Weariness |
| `<gasp>` | Surprise |
| `<sniffle>` | Sadness |
| `<cough>` | Hesitation |
| `<groan>` | Frustration |
| `<yawn>` | Tiredness |

**Example:**
```bash
mcporter call orpheus-tts.generate_speech \
    text="That's amazing! <laugh> I can't believe it!" \
    voice=tara \
    output_path=~/.openclaw/media/tts/happy.wav
```

---

## Common Workflows

### Simple Speech Generation

```bash
mcporter call orpheus-tts.generate_speech \
    text="Hello world" \
    voice=tara
```

### Audiobook Generation

For long texts (>800 tokens):

```bash
# 1. Estimate tokens
mcporter call orpheus-tts.estimate_tokens text="[YOUR LONG TEXT]"

# 2. Split text into chunks (recommended: under 800 tokens each)

# 3. Generate each chunk
mcporter call orpheus-tts.generate_speech text="[CHAPTER 1]" voice=tara output_path=~/.openclaw/media/tts/chapter1.wav
mcporter call orpheus-tts.generate_speech text="[CHAPTER 2]" voice=tara output_path=~/.openclaw/media/tts/chapter2.wav
mcporter call orpheus-tts.generate_speech text="[CHAPTER 3]" voice=tara output_path=~/.openclaw/media/tts/chapter3.wav
```

### Multi-Voice Audiobook

```bash
mcporter call orpheus-tts.generate_speech text="[NARRATOR TEXT]" voice=tara output_path=~/.openclaw/media/tts/narrator.wav
mcporter call orpheus-tts.generate_speech text="[MALE CHARACTER]" voice=leo output_path=~/.openclaw/media/tts/character_male.wav
mcporter call orpheus-tts.generate_speech text="[FEMALE CHARACTER]" voice=leah output_path=~/.openclaw/media/tts/character_female.wav
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Server not ready" | Wait 5 seconds and retry |
| "Timeout" | Split text into smaller chunks |
| "Invalid voice" | Run `list_voices` to get valid options |
| "Model not found" | Check ORPHEUS_MODEL_PATH environment variable |

---

## Environment Variables

- `ORPHEUS_MODEL_PATH` - Path to Orpheus GGUF model (required)
- `ORPHEUS_LLAMA_CPP_PATH` - Path to llama-server binary (optional)
- `ORPHEUS_OUTPUT_DIR` - Output directory (default: ~/Documents/tts)
- `MCP_TRANSPORT` - stdio or sse (default: stdio)