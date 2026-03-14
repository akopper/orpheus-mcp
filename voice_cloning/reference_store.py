"""Reference Voice Store - manage saved reference voices"""

import os
import json
import shutil
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from .config import get_reference_dir


class ReferenceStore:
    """Manages stored reference voices for voice cloning"""

    def __init__(self, reference_dir: str = None):
        self.reference_dir = Path(reference_dir or get_reference_dir())
        self.reference_dir.mkdir(parents=True, exist_ok=True)

    def save_reference(
        self,
        name: str,
        audio_path: str,
        transcript: str,
        voice_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Save a reference voice

        Args:
            name: Unique identifier for the reference
            audio_path: Path to audio file (will be converted to 24kHz)
            transcript: Transcript of the audio
            voice_name: Optional display name

        Returns:
            Dict with paths to saved files
        """
        from .snac_tokenizer import SNACTokenizer

        # Create reference directory
        ref_dir = self.reference_dir / name
        ref_dir.mkdir(parents=True, exist_ok=True)

        # Convert audio to 24kHz if needed
        audio_24k_path = str(ref_dir / "audio.wav")
        SNACTokenizer.convert_audio_to_24khz(audio_path, audio_24k_path)

        # Save transcript
        transcript_path = str(ref_dir / "transcript.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript)

        # Save manifest
        manifest = {
            "name": name,
            "voice_name": voice_name or name,
            "created_at": datetime.now().isoformat(),
            "audio_file": "audio.wav",
            "transcript_file": "transcript.txt",
        }
        manifest_path = str(ref_dir / "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return {
            "reference_dir": str(ref_dir),
            "audio_path": audio_24k_path,
            "transcript_path": transcript_path,
            "manifest_path": manifest_path,
        }

    def get_reference(self, name: str) -> Optional[Dict]:
        """
        Get reference voice by name

        Args:
            name: Reference name

        Returns:
            Dict with reference info or None if not found
        """
        ref_dir = self.reference_dir / name

        if not ref_dir.exists():
            return None

        manifest_path = ref_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Add full paths
        manifest["audio_path"] = str(ref_dir / manifest["audio_file"])
        manifest["transcript_path"] = str(ref_dir / manifest["transcript_file"])
        manifest["reference_dir"] = str(ref_dir)

        return manifest

    def list_references(self) -> List[Dict]:
        """
        List all stored reference voices

        Returns:
            List of reference manifests
        """
        references = []

        for ref_dir in self.reference_dir.iterdir():
            if ref_dir.is_dir():
                ref = self.get_reference(ref_dir.name)
                if ref:
                    references.append(ref)

        return sorted(references, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_reference(self, name: str) -> bool:
        """
        Delete a reference voice

        Args:
            name: Reference name to delete

        Returns:
            True if deleted, False if not found
        """
        ref_dir = self.reference_dir / name

        if not ref_dir.exists():
            return False

        shutil.rmtree(ref_dir)
        return True

    def reference_exists(self, name: str) -> bool:
        """Check if reference exists"""
        return (self.reference_dir / name).exists()

    def get_audio_path(self, name: str) -> Optional[str]:
        """Get full path to reference audio"""
        ref = self.get_reference(name)
        return ref["audio_path"] if ref else None

    def get_transcript(self, name: str) -> Optional[str]:
        """Get transcript for reference"""
        ref = self.get_reference(name)
        if not ref:
            return None

        with open(ref["transcript_path"], "r", encoding="utf-8") as f:
            return f.read()
