"""Voice Clone Engine - Zero-shot voice cloning with Orpheus"""

import os
import json
import time
import torch
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from .snac_tokenizer import SNACTokenizer
from .config import (
    ORPHEUS_PRETRAINED_MODEL,
    VOICE_CLONE_DEFAULTS,
    START_OF_HUMAN,
    END_OF_TEXT,
    END_OF_AUDIO,
    START_OF_GENERATION,
    END_OF_GENERATION,
    PAD_TOKEN,
)


@dataclass
class CloneResult:
    """Result of voice cloning operation"""

    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0


class VoiceCloneEngine:
    """Engine for zero-shot voice cloning using Orpheus pretrained model"""

    _instance: Optional["VoiceCloneEngine"] = None
    _model = None
    _tokenizer = None
    _snac = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.config = VOICE_CLONE_DEFAULTS.copy()

    @property
    def model(self):
        """Lazy load Orpheus pretrained model"""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    @property
    def tokenizer(self):
        """Lazy load tokenizer"""
        if self._tokenizer is None:
            self._tokenizer = self._load_tokenizer()
        return self._tokenizer

    @property
    def snac(self):
        """Lazy load SNAC tokenizer"""
        if self._snac is None:
            self._snac = SNACTokenizer()
        return self._snac

    def _load_tokenizer(self):
        """Load Orpheus tokenizer"""
        from transformers import AutoTokenizer

        print("Loading Orpheus tokenizer...", file=__import__("sys").stderr)
        tokenizer = AutoTokenizer.from_pretrained(ORPHEUS_PRETRAINED_MODEL)
        print("Tokenizer loaded", file=__import__("sys").stderr)
        return tokenizer

    def _load_model(self):
        """Load Orpheus pretrained model"""
        import gc
        from transformers import AutoModelForCausalLM
        from huggingface_hub import snapshot_download

        print("Loading Orpheus pretrained model...", file=__import__("sys").stderr)

        # Download if not present
        try:
            model_path = snapshot_download(
                repo_id=ORPHEUS_PRETRAINED_MODEL,
                allow_patterns=[
                    "config.json",
                    "*.safetensors",
                    "model.safetensors.index.json",
                ],
                ignore_patterns=[
                    "optimizer.pt",
                    "pytorch_model.bin",
                    "training_args.bin",
                    "scheduler.pt",
                    "tokenizer.json",
                    "tokenizer_config.json",
                    "special_tokens_map.json",
                    "vocab.json",
                    "merges.txt",
                    "tokenizer.*",
                ],
            )
        except Exception as e:
            print(f"Note: {e}", file=__import__("sys").stderr)

        # Determine dtype
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        model = AutoModelForCausalLM.from_pretrained(
            ORPHEUS_PRETRAINED_MODEL,
            torch_dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else "cpu",
        )
        model.eval()
        print("Orpheus model loaded", file=__import__("sys").stderr)
        return model

    def clone_voice(
        self,
        reference_audio_path: str,
        reference_transcript: str,
        text_to_speak: str,
        output_path: str,
        temperature: float = None,
        top_p: float = None,
        repetition_penalty: float = None,
        max_new_tokens: int = None,
    ) -> CloneResult:
        """
        Clone voice from reference audio

        Args:
            reference_audio_path: Path to reference audio (24kHz WAV)
            reference_transcript: Transcript of reference audio
            text_to_speak: Text to generate in cloned voice
            output_path: Output WAV file path
            temperature: Generation temperature (default: 0.5)
            top_p: Top-p sampling (default: 0.9)
            repetition_penalty: Repetition penalty (default: 1.1)
            max_new_tokens: Max tokens to generate (default: 990)

        Returns:
            CloneResult with output path or error
        """
        start_time = time.time()

        try:
            # Ensure audio is 24kHz
            if not reference_audio_path.endswith(".wav") or self._needs_conversion(
                reference_audio_path
            ):
                print(
                    f"Converting {reference_audio_path} to 24kHz...",
                    file=__import__("sys").stderr,
                )
                reference_audio_path = SNACTokenizer.convert_audio_to_24khz(
                    reference_audio_path
                )

            # Encode reference audio to SNAC tokens
            print("Tokenizing reference audio...", file=__import__("sys").stderr)
            audio_tokens = self._tokenize_audio(reference_audio_path)

            # Prepare input
            print("Preparing prompt...", file=__import__("sys").stderr)
            input_ids, attention_mask = self._prepare_inputs(
                reference_transcript, text_to_speak, audio_tokens
            )

            # Generate
            print("Generating speech...", file=__import__("sys").stderr)
            generated_ids = self._generate(
                input_ids,
                attention_mask,
                temperature or self.config["temperature"],
                top_p or self.config["top_p"],
                repetition_penalty or self.config["repetition_penalty"],
                max_new_tokens or self.config["max_new_tokens"],
            )

            # Decode
            print("Decoding audio...", file=__import__("sys").stderr)
            audio = self._decode_tokens(generated_ids)

            # Save output
            self._save_audio(audio, output_path)

            duration = time.time() - start_time
            print(
                f"Voice cloning completed in {duration:.1f}s",
                file=__import__("sys").stderr,
            )

            return CloneResult(
                success=True,
                output_path=output_path,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return CloneResult(
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

    def _needs_conversion(self, audio_path: str) -> bool:
        """Check if audio needs conversion to 24kHz"""
        try:
            import librosa

            info = librosa.info(audio_path)
            return info.sample_rate != 24000
        except:
            return True

    def _tokenize_audio(self, audio_path: str) -> List[int]:
        """Tokenize audio with SNAC"""
        return self.snac.encode(audio_path)

    def _prepare_inputs(
        self,
        reference_transcript: str,
        text_to_speak: str,
        audio_tokens: List[int],
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Prepare model inputs with reference prompt"""

        # Tokenize reference transcript
        transcript_tokens = self.tokenizer(reference_transcript, return_tensors="pt")

        # Tokenize text to speak
        text_tokens = self.tokenizer(text_to_speak, return_tensors="pt")

        # Build prompt:
        # [START] transcript [END_AUDIO] [audio_tokens] [END_GENERATION] [START] text [END]
        start_tokens = torch.tensor([[START_OF_HUMAN]], dtype=torch.int64)
        end_ref_tokens = torch.tensor([[END_OF_TEXT, END_OF_AUDIO]], dtype=torch.int64)
        audio_tokens_tensor = torch.tensor([audio_tokens], dtype=torch.int64)
        end_gen_tokens = torch.tensor(
            [[END_OF_GENERATION, START_OF_GENERATION]], dtype=torch.int64
        )

        # Reference prompt (optional but recommended for better cloning)
        ref_input = torch.cat(
            [
                start_tokens,
                transcript_tokens["input_ids"],
                end_ref_tokens,
                audio_tokens_tensor,
            ],
            dim=1,
        )

        # Generation prompt
        input_ids = torch.cat(
            [
                ref_input,
                end_gen_tokens,
                start_tokens,
                text_tokens["input_ids"],
                torch.tensor([[END_OF_TEXT]], dtype=torch.int64),
            ],
            dim=1,
        )

        # Attention mask
        attention_mask = torch.ones_like(input_ids)

        # Move to device
        if torch.cuda.is_available():
            input_ids = input_ids.cuda()
            attention_mask = attention_mask.cuda()

        return input_ids, attention_mask

    def _generate(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        temperature: float,
        top_p: float,
        repetition_penalty: float,
        max_new_tokens: int,
    ) -> torch.Tensor:
        """Generate audio tokens"""

        with torch.no_grad():
            generated_ids = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                num_return_sequences=1,
                eos_token_id=END_OF_GENERATION,
                pad_token_id=PAD_TOKEN,
            )

        return generated_ids

    def _decode_tokens(self, generated_ids: torch.Tensor) -> np.ndarray:
        """Decode generated tokens to audio"""

        # Find START_OF_AUDIO token and take everything after
        token_to_find = END_OF_AUDIO

        # Find the last occurrence of END_OF_AUDIO
        token_indices = (generated_ids == token_to_find).nonzero(as_tuple=True)

        if len(token_indices[1]) > 0:
            last_idx = token_indices[1][-1].item()
            cropped = generated_ids[:, last_idx + 1 :]
        else:
            cropped = generated_ids

        # Remove END_OF_GENERATION tokens
        mask = cropped != END_OF_GENERATION
        tokens = cropped[mask].cpu().tolist()

        # Redistribute and decode
        audio = self.snac.decode(tokens)

        return audio

    def _save_audio(self, audio: np.ndarray, output_path: str):
        """Save audio to file"""
        import soundfile as sf

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save as 24kHz WAV
        sf.write(output_path, audio, 24000)

    def unload_model(self):
        """Unload model to free memory"""
        if self._model is not None:
            del self._model
            self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def ensure_model_loaded():
    """Ensure all models are loaded"""
    engine = VoiceCloneEngine()
    _ = engine.model
    _ = engine.tokenizer
    _ = engine.snac
    return engine
