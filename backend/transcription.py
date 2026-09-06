"""Provider adapter for speech-to-text.

Only this module knows about the chosen STT provider. Routes and callers use
the provider-neutral ``transcribe_audio`` function instead.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import (
    APIConnectionError,
    APIStatusError,
    AsyncGroq,
    AuthenticationError,
    RateLimitError,
)


load_dotenv(Path(__file__).with_name(".env"))


class TranscriptionServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


async def transcribe_audio(
    *, audio_bytes: bytes, filename: str, content_type: str, language: str
) -> str:
    """Send audio to Groq and return only the provider-neutral transcript text."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise TranscriptionServiceError(
            503,
            "STT_NOT_CONFIGURED",
            "Speech-to-text is not configured on this server.",
        )

    model = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
    try:
        async with AsyncGroq(api_key=api_key, timeout=60.0, max_retries=0) as client:
            response = await client.audio.transcriptions.create(
                file=(filename, audio_bytes, content_type),
                model=model,
                response_format="json",
                language=language,
            )
    except AuthenticationError as error:
        raise TranscriptionServiceError(
            502,
            "STT_AUTHENTICATION_FAILED",
            "The speech-to-text provider rejected the server credentials.",
        ) from error
    except RateLimitError as error:
        raise TranscriptionServiceError(
            503, "STT_RATE_LIMITED", "The speech-to-text service is temporarily busy."
        ) from error
    except APIConnectionError as error:
        raise TranscriptionServiceError(
            503,
            "STT_UNAVAILABLE",
            "The speech-to-text service could not be reached.",
        ) from error
    except APIStatusError as error:
        raise TranscriptionServiceError(
            502,
            "TRANSCRIPTION_FAILED",
            "The speech-to-text provider could not transcribe this audio.",
        ) from error

    text = response.text
    if not isinstance(text, str):
        raise TranscriptionServiceError(
            502,
            "TRANSCRIPTION_FAILED",
            "The speech-to-text provider returned an invalid response.",
        )

    return text
