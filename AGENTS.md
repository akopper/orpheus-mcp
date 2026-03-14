# Agent Instructions for Orpheus MCP Server

This document provides guidance for AI agents using the Orpheus TTS MCP server to generate speech and audiobooks.

## Overview

The Orpheus MCP server provides text-to-speech capabilities with 25 voices across 8 languages. It's designed for agentic workflows where the AI manages the text processing, chunking, and audio generation strategy.

## Available Tools

### 1. `estimate_tokens`

**Purpose**: Estimate token count before generation to plan chunking strategy.

**When to use**: Always call this first for texts longer than 500 characters.

**Example**:
```json
{
  "text": "Your long text here..."
}
```

**Response interpretation**:
- `estimated_tokens`: Approximate token count
- `fits_in_single_request`: Whether text fits in one request (max 8192 tokens)
- `recommended_chunks`: How many chunks to split into
- `recommended_chunk_size`: Safe chunk size (~800 tokens)

### 2. `list_voices`

**Purpose**: Get all available voices.

**When to use**: At start of session or when user asks about voice options.

**Response**: List of voices with language codes.

### 3. `get_voice_info`

**Purpose**: Get detailed information about a specific voice.

**When to use**: Before generating speech to confirm voice capabilities.

**Example**:
```json
{
  "voice": "tara"
}
```

### 4. `generate_speech`

**Purpose**: Convert text to speech.

**Parameters**:
- `text` (required): Text to convert. Supports emotion tags.
- `voice` (optional): Voice name. Default: "tara"
- `output_path` (optional): Where to save. Auto-generated if not provided.
- `streaming` (optional): For real-time playback. Default: false

**Emotion Tags** (include in text):
- `<laugh>` - Laughter
- `<chuckle>` - Light amusement
- `<sigh>` - Weariness
- `<gasp>` - Surprise
- `<sniffle>` - Sadness
- `<cough>` - Hesitation
- `<groan>` - Frustration
- `<yawn>` - Tiredness

**Example**:
```json
{
  "text": "Hello there! <chuckle> It's great to meet you.",
  "voice": "tara",
  "output_path": "outputs/greeting.wav"
}
```

## Best Practices for Audiobook Generation

### 1. Text Analysis

Before generating:
1. Call `estimate_tokens` to understand text size
2. Identify natural break points (paragraphs, chapters, headers)
3. Plan chunk boundaries at sentence ends

### 2. Chunking Strategy

**For texts > 800 tokens**:
- Split at paragraph boundaries when possible
- Keep chunks under 800 tokens (conservative limit)
- Maintain context - don't split mid-sentence
- Track which chunks succeeded/failed

**Example workflow**:
```
1. estimate_tokens(text) → 2500 tokens, 4 chunks recommended
2. Split into 4 logical sections
3. generate_speech for each section
4. Track output paths: section_1.wav, section_2.wav, etc.
5. Report all generated files to user
```

### 3. Voice Selection

**Guidelines**:
- Use `list_voices` to show options
- Match voice to content language
- Consider content tone (serious vs playful)
- Default "tara" works well for English

**Language-specific voices**:
- English: tara, leah, jess, leo, dan, mia, zac, zoe
- French: pierre, amelie, marie
- German: jana, thomas, max
- Korean: 유나, 준서
- Hindi: ऋतिका
- Mandarin: 长乐, 白芷
- Spanish: javi, sergio, maria
- Italian: pietro, giulia, carlo

### 4. Error Handling

**Retry strategy**:
- If generation fails, retry once with same parameters
- If still failing, try shorter text chunk
- Report specific error to user
- Continue with remaining chunks

**Common errors**:
- "Server not ready": Wait 5 seconds and retry
- "Timeout": Split text into smaller chunks
- "Invalid voice": Use `list_voices` to get valid options

### 5. Output Management

**File organization**:
- Use descriptive names: `chapter_1.wav`, `introduction.wav`
- Include voice name: `intro_tara.wav`
- Group related files in subdirectories
- Report all generated file paths to user

**Example**:
```
outputs/
  audiobook/
    chapter_1_tara.wav
    chapter_2_tara.wav
    chapter_3_tara.wav
```

## Example Workflows

### Simple Speech Generation

```
User: "Convert this to speech: Hello world"

Agent:
1. generate_speech({"text": "Hello world", "voice": "tara"})
2. Report: "Generated speech saved to outputs/speech_tara_1234567890.wav"
```

### README to Audiobook

```
User: "Convert my README to an audiobook"

Agent:
1. Read README file content
2. estimate_tokens(readme_text) → 3500 tokens, 5 chunks
3. Split into sections: Introduction, Installation, Usage, API, Contributing
4. For each section:
   - generate_speech({"text": section_text, "voice": "tara", "output_path": f"outputs/readme_{section_name}.wav"})
   - Track successful generations
5. Report: "Generated 5 audio files in outputs/ directory"
```

### Multi-Voice Audiobook

```
User: "Create an audiobook with different voices for different characters"

Agent:
1. Parse text to identify speakers/characters
2. Assign voices:
   - Narrator: tara
   - Character A: leo
   - Character B: leah
3. Generate each section with appropriate voice
4. Report voice assignments and file locations
```

## Configuration

The MCP server reads from environment variables or `.env` file:

```bash
# Required
ORPHEUS_MODEL_PATH=/path/to/Orpheus-3b-FT-Q8_0.gguf

# Optional
ORPHEUS_API_URL=http://127.0.0.1:1234/v1/completions
ORPHEUS_LLAMA_CPP_PATH=/path/to/llama-server
ORPHEUS_OUTPUT_DIR=~/Documents/tts  # Defaults to ~/Documents/tts
MCP_TRANSPORT=stdio  # or sse
```

## Performance Tips

1. **Batch processing**: Generate multiple short chunks in parallel when possible
2. **Voice consistency**: Use same voice for entire audiobook unless style change needed
3. **Preview first**: Generate first paragraph to test voice before full audiobook
4. **Monitor tokens**: Keep chunks under 800 tokens for reliability
5. **Save incrementally**: Don't wait for all chunks - save as you go

## Troubleshooting

**Server not starting**:
- Check ORPHEUS_MODEL_PATH points to valid .gguf file
- Ensure llama-server binary is available
- Check port 1234 is not in use

**Generation slow**:
- Normal for first generation (model loading)
- Subsequent generations are faster
- Consider using GPU if available

**Audio quality issues**:
- Try different voice
- Check text doesn't have unusual characters
- Ensure emotion tags are properly formatted

## Integration Examples

### With mcporter

```json
{
  "mcpServers": {
    "orpheus-tts": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "ORPHEUS_MODEL_PATH": "/path/to/model.gguf"
      }
    }
  }
}
```

### With Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "orpheus-tts": {
      "command": "python",
      "args": ["/path/to/Orpheus-FastAPI/mcp_server.py"],
      "env": {
        "ORPHEUS_MODEL_PATH": "/path/to/Orpheus-3b-FT-Q8_0.gguf"
      }
    }
  }
}
```

## Notes

- Audio output is 24kHz WAV format
- Each voice supports emotion tags for expressive speech
- The server auto-starts llama.cpp if not already running
- Generated files persist in ~/Documents/tts/ directory by default
- Use absolute paths for output_path to avoid confusion
