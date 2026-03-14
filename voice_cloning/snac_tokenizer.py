"""SNAC Tokenizer for audio encoding/decoding"""

import os
import torch
import numpy as np
from typing import Optional, List
from pathlib import Path

# Token offset for SNAC codes in Orpheus
SNAC_OFFSET = 128266
LAYER2_OFFSET = 4096


class SNACTokenizer:
    """SNAC audio tokenizer wrapper"""

    _instance: Optional["SNACTokenizer"] = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        pass

    @property
    def model(self):
        """Lazy load SNAC model"""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self):
        """Load SNAC model from HuggingFace"""
        try:
            from snac import SNAC

            print("Loading SNAC model...", file=__import__("sys").stderr)
            model = SNAC.from_pretrained("hubertsiuzdak/snac_24khz")
            if torch.cuda.is_available():
                model = model.cuda()
            model.eval()
            print("SNAC model loaded", file=__import__("sys").stderr)
            return model
        except ImportError:
            raise ImportError("snac package not found. Install with: pip install snac")

    def encode(self, audio_path: str) -> List[int]:
        """
        Encode audio file to SNAC tokens

        Args:
            audio_path: Path to audio file (wav, mp3, m4a, etc.)

        Returns:
            List of SNAC token IDs
        """
        import librosa
        import soundfile as sf

        # Load and convert audio
        audio_array, sr = librosa.load(audio_path, sr=24000, mono=True)

        # Convert to tensor
        waveform = torch.from_numpy(audio_array).unsqueeze(0).unsqueeze(0)
        waveform = waveform.to(dtype=torch.float32)

        if torch.cuda.is_available():
            waveform = waveform.cuda()

        # Encode
        with torch.no_grad():
            codes = self.model.encode(waveform)

        # Convert to token list (interleaving SNAC layers)
        all_codes = []
        for i in range(codes[0].shape[1]):
            # Layer 1: 1 code per frame
            all_codes.append(codes[0][0][i].item() + SNAC_OFFSET)
            # Layer 2: 2 codes per frame
            all_codes.append(codes[1][0][2 * i].item() + SNAC_OFFSET + LAYER2_OFFSET)
            all_codes.append(
                codes[1][0][2 * i + 1].item() + SNAC_OFFSET + LAYER2_OFFSET
            )
            # Layer 3: 4 codes per frame
            all_codes.append(
                codes[2][0][4 * i].item() + SNAC_OFFSET + 2 * LAYER2_OFFSET
            )
            all_codes.append(
                codes[2][0][4 * i + 1].item() + SNAC_OFFSET + 3 * LAYER2_OFFSET
            )
            all_codes.append(
                codes[2][0][4 * i + 2].item() + SNAC_OFFSET + 4 * LAYER2_OFFSET
            )
            all_codes.append(
                codes[2][0][4 * i + 3].item() + SNAC_OFFSET + 5 * LAYER2_OFFSET
            )

        return all_codes

    def decode(self, token_ids: List[int]) -> np.ndarray:
        """
        Decode SNAC tokens to audio

        Args:
            token_ids: List of SNAC token IDs

        Returns:
            Audio as numpy array (float32, 24kHz)
        """
        # Remove offsets and redistribute to layers
        codes = self._redistribute_codes(token_ids)

        # Decode
        with torch.no_grad():
            if torch.cuda.is_available():
                codes = [c.cuda() for c in codes]
            audio = self.model.decode(codes)

        # Convert to numpy
        if isinstance(audio, torch.Tensor):
            audio = audio.squeeze().cpu().numpy()

        return audio.astype(np.float32)

    def _redistribute_codes(self, token_ids: List[int]):
        """Redistribute flat token list to SNAC layer structure"""
        # Remove padding and convert back
        codes = [t - SNAC_OFFSET for t in token_ids]

        layer_1 = []
        layer_2 = []
        layer_3 = []

        for i in range((len(codes) + 1) // 7):
            layer_1.append(codes[7 * i])
            layer_2.append(codes[7 * i + 1] - LAYER2_OFFSET)
            layer_3.append(codes[7 * i + 2] - 2 * LAYER2_OFFSET)
            layer_3.append(codes[7 * i + 3] - 3 * LAYER2_OFFSET)
            layer_2.append(codes[7 * i + 4] - 4 * LAYER2_OFFSET)
            layer_3.append(codes[7 * i + 5] - 5 * LAYER2_OFFSET)
            layer_3.append(codes[7 * i + 6] - 6 * LAYER2_OFFSET)

        return [
            torch.tensor(layer_1).unsqueeze(0),
            torch.tensor(layer_2).unsqueeze(0),
            torch.tensor(layer_3).unsqueeze(0),
        ]

    @staticmethod
    def convert_audio_to_24khz(
        input_path: str, output_path: Optional[str] = None
    ) -> str:
        """
        Convert audio file to 24kHz WAV

        Args:
            input_path: Input audio file path
            output_path: Output path (optional, auto-generated)

        Returns:
            Path to converted audio file
        """
        import librosa
        import soundfile as sf

        # Load audio
        audio, sr = librosa.load(input_path, sr=24000, mono=True)

        # Determine output path
        if output_path is None:
            input_p = Path(input_path)
            output_path = input_p.parent / f"{input_p.stem}_24khz.wav"

        # Save as 24kHz WAV
        sf.write(output_path, audio, 24000)

        return str(output_path)


def ensure_model_downloaded():
    """Ensure SNAC model is downloaded"""
    tokenizer = SNACTokenizer()
    # Just accessing .model triggers download
    _ = tokenizer.model
    return tokenizer
