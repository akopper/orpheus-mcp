"""
Voice Cloning Module for Orpheus TTS

Provides zero-shot voice cloning functionality using:
- SNAC tokenizer (hubertsiuzdak/snac_24khz)
- Orpheus pretrained model (canopylabs/orpheus-3b-0.1-pretrained)
"""

from .snac_tokenizer import SNACTokenizer
from .voice_clone import VoiceCloneEngine
from .reference_store import ReferenceStore

__all__ = ["SNACTokenizer", "VoiceCloneEngine", "ReferenceStore"]
