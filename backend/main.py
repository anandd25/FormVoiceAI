from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import re
import os
from uuid import uuid4

from transcription import TranscriptionServiceError, transcribe_audio

app = FastAPI(title="FormVoice API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Request Models
# -----------------------------

class VoiceRequest(BaseModel):
    text: str
    current_form: dict


def transcription_error(request_id: str, status_code: int, code: str, message: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


# -----------------------------
# Speech-to-text endpoint
# -----------------------------

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile | None = File(default=None),
    language: str = Form(default="en"),
):
    """Transcribe one browser-recorded audio file without processing form fields."""
    request_id = str(uuid4())

    if audio is None:
        return transcription_error(
            request_id, 400, "AUDIO_REQUIRED", "Include an audio file in the 'audio' field."
        )

    content_type = audio.content_type or "application/octet-stream"
    if not content_type.startswith("audio/"):
        return transcription_error(
            request_id, 415, "AUDIO_UNSUPPORTED", "Upload a supported audio file."
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        return transcription_error(
            request_id, 400, "AUDIO_EMPTY", "The audio file is empty."
        )

    try:
        text = await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            content_type=content_type,
            language=language,
        )
    except TranscriptionServiceError as error:
        return transcription_error(request_id, error.status_code, error.code, error.message)

    return {
        "request_id": request_id,
        "transcript": {
            "text": text,
            "language": language,
            "confidence": None,
        },
    }


# -----------------------------
# Extract phone number
# -----------------------------

def extract_phone(text):

    digits = re.sub(r"\D", "", text)

    if len(digits) >= 10:
        return digits[-10:]

    return None


# -----------------------------
# Extract application ID
# -----------------------------

def extract_application_id(text):

    match = re.search(
        r"\b[A-Za-z]{2,5}[- ]?\d{4,12}\b",
        text
    )

    if match:
        return match.group().replace(" ", "").replace("-", "").upper()

    return None


# -----------------------------
# Detect fields
# -----------------------------

def extract_fields(text, current):

    updated = current.copy()

    lower = text.lower()

    # Phone
    phone = extract_phone(text)

    if phone:
        updated["phone"] = phone


    # Application ID
    application_id = extract_application_id(text)

    if application_id:
        updated["application_id"] = application_id


    # Name
    if "name is" in lower:

        name = text.lower().split("name is", 1)[1]

        if name:
            updated["name"] = name.strip().title()


    # Address
    if "address is" in lower:

        address = text.lower().split("address is", 1)[1]

        if address:
            updated["address"] = address.strip().title()


    return updated


# -----------------------------
# Speech-safe identifier
# -----------------------------

def speech_safe_id(value):

    if not value:
        return ""

    return " ".join(value)


# -----------------------------
# Generate confirmation
# -----------------------------

def generate_message(form):

    if form["application_id"]:

        spoken_id = speech_safe_id(
            form["application_id"]
        )

        return (
            f"I heard application ID "
            f"{spoken_id}. "
            f"Is that correct?"
        )

    if form["phone"]:

        spoken_phone = speech_safe_id(
            form["phone"]
        )

        return (
            f"I heard phone number "
            f"{spoken_phone}. "
            f"Is that correct?"
        )

    if form["name"]:

        return (
            f"I heard your name as "
            f"{form['name']}. "
            f"Is that correct?"
        )

    return "Please tell me your details."


# -----------------------------
# Main endpoint
# -----------------------------

@app.post("/process-voice")
async def process_voice(request: VoiceRequest):

    form = extract_fields(
        request.text,
        request.current_form
    )

    message = generate_message(form)


    # -----------------------------------
    # Rime TTS will be called here
    # -----------------------------------

    audio_url = None

    # TODO:
    # audio_url = await generate_rime_audio(message)


    return {
        "form": form,
        "message": message,
        "audio_url": audio_url
    }


@app.get("/")
def root():

    return {
        "status": "FormVoice backend running"
    }
