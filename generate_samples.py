#!/usr/bin/env python3
"""
Generate sample audio files using Orpheus MCP Server
This script demonstrates the MCP server workflow and generates test audio files.

Prerequisites:
1. Install dependencies: pip install -r requirements.txt
2. Download model: Orpheus-3b-FT-Q8_0.gguf
3. Set ORPHEUS_MODEL_PATH environment variable
4. Start llama.cpp server or let MCP server auto-start it

Usage:
    python generate_samples.py

Output:
    Creates sample audio files in samples/ directory
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Ensure output directory exists
SAMPLES_DIR = Path("samples")
SAMPLES_DIR.mkdir(exist_ok=True)

# Sample texts for different voices and emotions
SAMPLES = [
    {
        "name": "tara_hello",
        "voice": "tara",
        "text": "Hello! I'm Tara, and this is a sample of my voice. I can speak naturally with emotion tags like this: I just love talking to you!",
        "description": "Basic greeting with Tara (default English voice)",
    },
    {
        "name": "leah_happy",
        "voice": "leah",
        "text": "What a wonderful day! <chuckle> I'm Leah, and I'm so happy to meet you. This is my cheerful voice.",
        "description": "Happy tone with Leah and chuckle emotion",
    },
    {
        "name": "zac_contemplative",
        "voice": "zac",
        "text": "Hmm... let me think about that. <sigh> Sometimes, the best ideas come when we pause and reflect.",
        "description": "Contemplative tone with Zac and sigh emotion",
    },
    {
        "name": "tara_sad",
        "voice": "tara",
        "text": "I remember that day... <sniffle> It was so hard to say goodbye. But we carry those memories with us.",
        "description": "Emotional/sad tone with Tara and sniffle",
    },
    {
        "name": "leo_surprised",
        "voice": "leo",
        "text": "Wait, what? <gasp> I can't believe it! That's absolutely amazing news!",
        "description": "Surprised tone with Leo and gasp emotion",
    },
    {
        "name": "mia_tired",
        "voice": "mia",
        "text": "Oh... <yawn> I'm so tired today. It's been a long day, and I can barely keep my eyes open.",
        "description": "Tired tone with Mia and yawn emotion",
    },
    {
        "name": "dan_frustrated",
        "voice": "dan",
        "text": "Ugh, not again! <groan> This is so frustrating. Why does this always happen at the worst time?",
        "description": "Frustrated tone with Dan and groan emotion",
    },
    {
        "name": "zoe_cough",
        "voice": "zoe",
        "text": "Excuse me... <cough> Sorry about that. <cough> I think I'm coming down with something.",
        "description": "Hesitant tone with Zoe and cough emotion",
    },
]


def check_environment():
    """Check if environment is properly configured"""
    print("Checking environment...")

    # Check for model path
    model_path = os.environ.get("ORPHEUS_MODEL_PATH")
    if not model_path:
        print("⚠️  Warning: ORPHEUS_MODEL_PATH not set")
        print("   Set it to the path of your Orpheus-3b-FT-Q8_0.gguf model")
        return False

    if not os.path.exists(model_path):
        print(f"⚠️  Warning: Model not found at {model_path}")
        return False

    print(f"✓ Model found: {model_path}")

    # Check for llama-server
    llama_path = os.environ.get("ORPHEUS_LLAMA_CPP_PATH")
    if llama_path and os.path.exists(llama_path):
        print(f"✓ llama-server found: {llama_path}")
    else:
        print("ℹ️  llama-server will be auto-detected or MCP server will auto-start")

    return True


def play_audio(filepath):
    """Play audio file using afplay (macOS)"""
    import subprocess

    try:
        subprocess.run(["afplay", str(filepath)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error playing audio: {e}")
        return False
    except FileNotFoundError:
        print("⚠️  afplay not found (macOS only)")
        return False


async def generate_sample(sample_config, play=False):
    """Generate a single sample audio file"""
    name = sample_config["name"]
    voice = sample_config["voice"]
    text = sample_config["text"]
    description = sample_config["description"]

    output_path = SAMPLES_DIR / f"{name}.wav"

    print(f"\n{'=' * 60}")
    print(f"Generating: {name}")
    print(f"Voice: {voice}")
    print(f"Description: {description}")
    print(f"Text: {text[:80]}...")
    print(f"Output: {output_path}")

    try:
        # Import here to avoid dependency issues during validation
        from mcp_server import handle_generate_speech

        result = await handle_generate_speech(
            {
                "text": text,
                "voice": voice,
                "output_path": str(output_path),
            }
        )

        if result and len(result) > 0:
            response_text = result[0].text
            try:
                data = json.loads(response_text)
                if data.get("success"):
                    print(f"✓ Generated successfully: {output_path}")
                    print(f"  File size: {data.get('file_size_bytes', 0)} bytes")

                    if play and output_path.exists():
                        print(f"  Playing...")
                        play_audio(output_path)

                    return True
                else:
                    print(f"✗ Generation failed: {data}")
                    return False
            except json.JSONDecodeError:
                print(f"✗ Error: {response_text}")
                return False
        else:
            print("✗ No result returned")
            return False

    except Exception as e:
        print(f"✗ Error generating sample: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("Orpheus TTS Sample Generator")
    print("=" * 60)

    # Check environment
    if not check_environment():
        print("\n⚠️  Environment not fully configured.")
        print("Please set ORPHEUS_MODEL_PATH and ensure the model is downloaded.")
        print("\nExample:")
        print("  export ORPHEUS_MODEL_PATH=/path/to/Orpheus-3b-FT-Q8_0.gguf")
        print("\nYou can download the model from:")
        print("  https://huggingface.co/lex-au/Orpheus-3b-FT-Q8_0.gguf")
        return 1

    print(f"\nGenerating {len(SAMPLES)} sample audio files...")
    print(f"Output directory: {SAMPLES_DIR.absolute()}")

    # Ask if user wants to play samples
    play_samples = (
        input("\nPlay samples after generation? (y/N): ").lower().startswith("y")
    )

    # Generate samples
    successful = 0
    failed = 0

    for sample in SAMPLES:
        if await generate_sample(sample, play=play_samples):
            successful += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("Generation Summary")
    print("=" * 60)
    print(f"Total samples: {len(SAMPLES)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nOutput directory: {SAMPLES_DIR.absolute()}")
    print("\nGenerated files:")

    for sample in SAMPLES:
        filepath = SAMPLES_DIR / f"{sample['name']}.wav"
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  ✓ {filepath.name} ({size:,} bytes)")
        else:
            print(f"  ✗ {filepath.name} (not found)")

    print("\n" + "=" * 60)

    if successful > 0:
        print("\nTo play a sample manually:")
        print(f"  afplay {SAMPLES_DIR}/tara_hello.wav")
        print("\n" + "=" * 60 + "\n")
        return 0
    else:
        print("\n⚠️  No samples were generated successfully.")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
