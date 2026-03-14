# Voice Cloning Feature - Status Report

**Branch:** voice-cloning-feature  
**Commit:** 5125c69  
**Date:** 2024-03-14

---

## ✅ Completed Features

### 1. Voice Cloning Module (`voice_cloning/`)

| File | Description | Status |
|------|-------------|--------|
| `__init__.py` | Package initialization | ✅ |
| `config.py` | Configuration (tokens, timeouts, paths) | ✅ |
| `snac_tokenizer.py` | SNAC audio encoding/decoding | ✅ |
| `voice_clone.py` | Voice Clone Engine | ✅ |
| `reference_store.py` | Reference voice management | ✅ |

### 2. New MCP Tools

| Tool | Description | Status |
|------|-------------|--------|
| `clone_voice_direct` | Clone from audio file, optionally save for later | ✅ |
| `clone_voice` | Clone using saved reference | ✅ |
| `list_reference_voices` | List all saved references | ✅ |
| `delete_reference_voice` | Delete a saved reference | ✅ |

### 3. Dependencies

Added to `requirements.txt`:
- `soundfile>=0.12.1`
- `librosa>=0.10.1`
- `scipy>=1.11.0`
- `transformers>=4.35.0`
- `huggingface_hub>=0.20.0`

### 4. Test Script

`test_voice_cloning.py` - Full test suite with:
- SNAC tokenizer test
- Reference store test
- Voice cloning test
- Save/load/delete reference tests

---

## ⏳ Pending / In Progress

### Testing with Real Voice Cloning

**Issue:** Requires access to `canopylabs/orpheus-3b-0.1-pretrained` (gated model)

**Status:** Access now granted (2024-03-14)

**Test Command:**
```bash
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### MCP Server Timeouts

Should increase timeout for voice cloning tools:
- `clone_voice_direct`: 180s (currently missing)
- `clone_voice`: 120s (currently missing)

---

## 📋 Usage Examples

### Direct Voice Cloning
```bash
mcporter call orpheus-tts.clone_voice_direct \
    audio_path="/path/to/reference.m4a" \
    transcript="Exact transcript of what is said in the reference audio" \
    text="Text to speak in cloned voice" \
    output_path="/path/to/output.wav"
```

### Clone with Save Reference
```bash
mcporter call orpheus-tts.clone_voice_direct \
    audio_path="/path/to/reference.m4a" \
    transcript="..." \
    text="..." \
    save_reference="my_voice" \
    voice_name="My Voice"
```

### Use Saved Reference
```bash
mcporter call orpheus-tts.clone_voice \
    reference_name="my_voice" \
    text="Hello world in my cloned voice" \
    output_path="/path/to/output.wav"
```

### List References
```bash
mcporter call orpheus-tts.list_reference_voices
```

---

## 🔧 Architecture

```
voice_cloning/
├── __init__.py           # Package exports
├── config.py              # Constants (tokens, timeouts)
├── snac_tokenizer.py     # SNAC encode/decode
│   - SNACTokenizer.encode(audio_path) → tokens
│   - SNACTokenizer.decode(tokens) → audio
│   - SNACTokenizer.convert_audio_to_24khz()
├── voice_clone.py         # Main engine
│   - VoiceCloneEngine.clone_voice()
│   - Auto-downloads pretrained model
│   - Auto-downloads SNAC tokenizer
├── reference_store.py    # Reference management
│   - ReferenceStore.save_reference()
│   - ReferenceStore.get_reference()
│   - ReferenceStore.list_references()
│   - ReferenceStore.delete_reference()
```

---

## 📦 Storage

Reference voices stored in: `~/Documents/tts/references/`

Structure:
```
~/Documents/tts/references/
├── my_voice/
│   ├── audio.wav           # 24kHz mono
│   ├── transcript.txt      # Reference transcript
│   └── manifest.json       # Metadata
└── another_voice/
    └── ...
```

---

## ⚠️ Known Issues

1. **Gated Model**: Was blocked, now resolved (access granted)
2. **First Run**: Model download takes 15-20 minutes
3. **VRAM**: Requires ~6GB GPU memory (bfloat16)
4. **Quality**: Voice cloning can be inconsistent (known issue with Orpheus)

---

## 🚀 Next Steps

1. ✅ Run test with real voice cloning
2. ⬜ Adjust MCP timeouts if needed
3. ⬜ Test with different voices
4. ⬜ Add voice cloning to AGENTS.md documentation
5. ⬜ Merge to main when stable