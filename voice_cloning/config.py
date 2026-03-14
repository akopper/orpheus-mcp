"""Voice Cloning Configuration"""

import os

# Default settings for voice cloning
VOICE_CLONE_DEFAULTS = {
    "temperature": 0.5,
    "top_p": 0.9,
    "repetition_penalty": 1.1,
    "max_new_tokens": 990,
    "sample_rate": 24000,
}

# Model configurations
ORPHEUS_PRETRAINED_MODEL = "canopylabs/orpheus-3b-0.1-pretrained"
SNAC_MODEL = "hubertsiuzdak/snac_24khz"


# Reference voice storage
def get_reference_dir() -> str:
    """Get reference voices directory"""
    base = os.path.expanduser("~/Documents/tts")
    return os.path.join(base, "references")


# Timeout settings (seconds)
TIMEOUT_CLONE_DIRECT = 180
TIMEOUT_CLONE_REFERENCE = 120
TIMEOUT_LIST = 10
TIMEOUT_DELETE = 10

# Special tokens for Orpheus
START_OF_HUMAN = 128259  # SOH
END_OF_HUMAN = 128260  # EOH
END_OF_TEXT = 128009  # EOT
START_OF_AUDIO = 128257  # SOA
END_OF_AUDIO = 128261  # EOA
START_OF_GENERATION = 128262  # SOG
END_OF_GENERATION = 128258  # EOG
PAD_TOKEN = 128263  # PAD
