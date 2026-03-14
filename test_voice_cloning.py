#!/usr/bin/env python3
"""
Test script for Voice Cloning functionality

Usage:
    python test_voice_cloning.py [options]

Options:
    --reference-audio PATH    Path to reference audio file
    --transcript TEXT         Transcript of reference audio
    --text TEXT               Text to generate in cloned voice
    --output PATH             Output file path
    --save-ref NAME           Name to save reference voice
    --use-ref NAME            Use saved reference voice
    --list-references         List all saved references
    --delete-ref NAME         Delete saved reference
"""

import argparse
import os
import sys
import time
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_snac_tokenizer():
    """Test SNAC tokenizer can load and encode audio"""
    print("\n=== Testing SNAC Tokenizer ===")
    from voice_cloning.snac_tokenizer import SNACTokenizer

    tokenizer = SNACTokenizer()
    print("SNAC model loaded successfully")
    return True


def test_reference_store():
    """Test reference store functionality"""
    print("\n=== Testing Reference Store ===")
    from voice_cloning.reference_store import ReferenceStore

    store = ReferenceStore()

    # Test list (should be empty)
    refs = store.list_references()
    print(f"Initial references: {len(refs)}")

    return True


def test_clone_voice_direct(
    audio_path: str, transcript: str, text: str, output_path: str = None
):
    """Test direct voice cloning"""
    print("\n=== Testing clone_voice_direct ===")

    from voice_cloning.voice_clone import VoiceCloneEngine

    if not output_path:
        output_dir = os.path.expanduser("~/Documents/tts")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"clone_test_{int(time.time())}.wav")

    print(f"Reference audio: {audio_path}")
    print(f"Transcript: {transcript[:50]}...")
    print(f"Text to speak: {text}")
    print(f"Output: {output_path}")

    engine = VoiceCloneEngine()

    start = time.time()
    result = engine.clone_voice(
        reference_audio_path=audio_path,
        reference_transcript=transcript,
        text_to_speak=text,
        output_path=output_path,
    )
    duration = time.time() - start

    print(f"\nResult:")
    print(f"  Success: {result.success}")
    print(f"  Output: {result.output_path}")
    print(f"  Duration: {duration:.1f}s")
    if result.error:
        print(f"  Error: {result.error}")

    return result.success, result.output_path


def test_save_reference(
    audio_path: str, transcript: str, name: str, voice_name: str = None
):
    """Test saving a reference voice"""
    print("\n=== Testing save_reference ===")

    from voice_cloning.reference_store import ReferenceStore

    store = ReferenceStore()

    result = store.save_reference(
        name=name,
        audio_path=audio_path,
        transcript=transcript,
        voice_name=voice_name,
    )

    print(f"Saved reference '{name}':")
    print(f"  Audio: {result['audio_path']}")
    print(f"  Transcript: {result['transcript_path']}")

    return True


def test_list_references():
    """Test listing references"""
    print("\n=== Testing list_references ===")

    from voice_cloning.reference_store import ReferenceStore

    store = ReferenceStore()
    refs = store.list_references()

    print(f"Found {len(refs)} reference(s):")
    for ref in refs:
        print(f"  - {ref['name']} ({ref.get('voice_name', ref['name'])})")

    return refs


def test_delete_reference(name: str):
    """Test deleting a reference"""
    print("\n=== Testing delete_reference ===")

    from voice_cloning.reference_store import ReferenceStore

    store = ReferenceStore()
    deleted = store.delete_reference(name)

    print(f"Deleted '{name}': {deleted}")

    return deleted


def main():
    parser = argparse.ArgumentParser(description="Test Voice Cloning")
    parser.add_argument("--reference-audio", "-a", help="Path to reference audio file")
    parser.add_argument("--transcript", "-t", help="Transcript of reference audio")
    parser.add_argument("--text", "-x", help="Text to generate in cloned voice")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--save-ref", "-s", help="Save reference with this name")
    parser.add_argument("--voice-name", "-n", help="Display name for saved reference")
    parser.add_argument("--use-ref", "-u", help="Use saved reference by name")
    parser.add_argument(
        "--list", "-l", action="store_true", help="List all saved references"
    )
    parser.add_argument("--delete", "-d", help="Delete saved reference")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip model download (for testing imports only)",
    )

    args = parser.parse_args()

    print("=" * 50)
    print("Voice Cloning Test Suite")
    print("=" * 50)

    # Test basic imports and setup
    try:
        from voice_cloning import SNACTokenizer, VoiceCloneEngine, ReferenceStore

        print("\n✓ All modules imported successfully")
    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        print("\nInstall required packages:")
        print(
            "  pip install snac transformers huggingface_hub librosa soundfile scipy torch"
        )
        sys.exit(1)

    # Run basic tests
    test_snac_tokenizer()
    test_reference_store()

    # Handle list option
    if args.list:
        test_list_references()
        return

    # Handle delete option
    if args.delete:
        test_delete_reference(args.delete)
        return

    # Handle reference audio provided
    if args.reference_audio:
        audio_path = args.reference_audio

        # Check file exists
        if not os.path.exists(audio_path):
            print(f"\n✗ Audio file not found: {audio_path}")
            sys.exit(1)

        transcript = args.transcript or "Hallo Test, 1 2 3. Hier ist der Alex."
        text = args.text or "Hallo Welt, das ist ein Test der Sprachausgabe."

        # Save reference if requested
        if args.save_ref:
            test_save_reference(
                audio_path=audio_path,
                transcript=transcript,
                name=args.save_ref,
                voice_name=args.voice_name,
            )

        # Clone voice
        success, output_path = test_clone_voice_direct(
            audio_path=audio_path,
            transcript=transcript,
            text=text,
            output_path=args.output,
        )

        if success:
            print(f"\n✓ Voice cloning successful!")
            print(f"  Output: {output_path}")

            # Play audio if on macOS
            if os.path.exists("/usr/bin/afplay"):
                print("\n  Playing audio...")
                os.system(f"afplay '{output_path}'")
        else:
            print("\n✗ Voice cloning failed")
            sys.exit(1)

    # Handle using saved reference
    elif args.use_ref:
        from voice_cloning.reference_store import ReferenceStore
        from voice_cloning.voice_clone import VoiceCloneEngine

        store = ReferenceStore()
        ref = store.get_reference(args.use_ref)

        if not ref:
            print(f"\n✗ Reference '{args.use_ref}' not found")
            sys.exit(1)

        transcript = store.get_transcript(args.use_ref)
        text = args.text or "Hallo Welt, das ist ein Test der Sprachausgabe."

        success, output_path = test_clone_voice_direct(
            audio_path=ref["audio_path"],
            transcript=transcript,
            text=text,
            output_path=args.output,
        )

        if success:
            print(f"\n✓ Voice cloning with saved reference successful!")
            print(f"  Output: {output_path}")
        else:
            print("\n✗ Voice cloning failed")
            sys.exit(1)

    else:
        print("\nUsage examples:")
        print("  # Clone voice from audio file")
        print(
            "  python test_voice_cloning.py -a /path/to/audio.m4a -t 'transcript' -x 'text to speak'"
        )
        print("")
        print("  # Save reference and clone")
        print(
            "  python test_voice_cloning.py -a /path/to/audio.m4a -t 'transcript' -s myvoice -x 'hello world'"
        )
        print("")
        print("  # Use saved reference")
        print("  python test_voice_cloning.py -u myvoice -x 'hello world'")
        print("")
        print("  # List saved references")
        print("  python test_voice_cloning.py --list")
        print("")
        print("  # Delete reference")
        print("  python test_voice_cloning.py -d myvoice")


if __name__ == "__main__":
    main()
