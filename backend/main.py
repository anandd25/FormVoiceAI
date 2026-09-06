# =========================================================
# IMPORTS
# =========================================================


from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import re
import os
from uuid import uuid4

from transcription import TranscriptionServiceError, transcribe_audio


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(title="FormVoice API")


# =========================================================
# CORS CONFIGURATION
# =========================================================


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODEL
# =========================================================
# Defines the data expected by /process-voice.
#
# text:
#   Transcript received from STT.
#
# current_form:
#   Current values already present in the form.
#
# target_field:
#   Identifies which field the user selected.
#   Example: "name", "phone", "email".
#
# This target_field is what allows an individual microphone
# to fill only the field it belongs to.

class VoiceRequest(BaseModel):
    text: str
    current_form: dict
    target_field: str | None = None


# =========================================================
# STT ERROR HANDLING
# =========================================================
# Creates a consistent JSON error response when something
# goes wrong during speech-to-text.
#
# Examples:
#   audio missing
#   unsupported audio
#   empty audio
#   Groq authentication failure
#   transcription service failure

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


# =========================================================
# SPEECH-TO-TEXT ENDPOINT
# =========================================================
# Receives the audio recorded by the browser.
#
# Working:
#
# Browser microphone
#       ↓
# Audio file
#       ↓
# /transcribe
#       ↓
# transcription.py
#       ↓
# Groq Whisper
#       ↓
# Transcript
#       ↓
# JSON response to frontend
#
# This endpoint is responsible ONLY for converting speech
# into text. It does not decide which form field to fill.

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile | None = File(default=None),
    language: str = Form(default="en"),
):
    request_id = str(uuid4())

    # Check whether an audio file was provided.
    if audio is None:
        return transcription_error(
            request_id, 400, "AUDIO_REQUIRED", "Include an audio file in the 'audio' field."
        )

    # Check that the uploaded file is actually an audio file.
    content_type = audio.content_type or "application/octet-stream"

    if not content_type.startswith("audio/"):
        return transcription_error(
            request_id, 415, "AUDIO_UNSUPPORTED", "Upload a supported audio file."
        )

    # Read the recorded audio.
    audio_bytes = await audio.read()

    # Reject empty recordings.
    if not audio_bytes:
        return transcription_error(
            request_id, 400, "AUDIO_EMPTY", "The audio file is empty."
        )

    try:
        # Send the audio to transcription.py.
        # transcription.py handles the actual Groq Whisper call.
        text = await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            content_type=content_type,
            language=language,
        )

    except TranscriptionServiceError as error:
        # Convert STT service errors into our standard response.
        return transcription_error(
            request_id, error.status_code, error.code, error.message
        )

    # Send the transcript back to the frontend.
    return {
        "request_id": request_id,
        "transcript": {
            "text": text,
            "language": language,
            "confidence": None,
        },
    }


# =========================================================
# SPOKEN DIGIT CONVERSION
# =========================================================
# Converts individually spoken numbers into digits.
#
# Example:
#
# "nine eight seven six"
#          ↓
#       "9876"
#
# This is especially useful for phone numbers and PINs.

def spoken_digits(text):
    digit_words = {
        "zero": "0",
        "oh": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
    }

    tokens = re.findall(r"\d+|[a-z]+", text.lower())

    return "".join(
        token if token.isdigit() else digit_words.get(token, "")
        for token in tokens
    )


# =========================================================
# PHONE NUMBER EXTRACTION
# =========================================================
# Uses spoken_digits() to convert spoken numbers into digits.
#
# If 10 or more digits are found, the last 10 digits are
# treated as the phone number.
#
# Example:
# "nine eight seven six five four three two one zero"
#                         ↓
#                  "9876543210"

def extract_phone(text):
    digits = spoken_digits(text)

    if len(digits) >= 10:
        return digits[-10:]

    return None


# =========================================================
# APPLICATION ID EXTRACTION
# =========================================================
# Searches the transcript for an application-ID pattern.
#
# Expected general pattern:
#   2–5 letters + 4–12 digits
#
# Example:
#   AB123456
#   APP-123456
#
# Spaces and hyphens are removed and the result is converted
# to uppercase.

def extract_application_id(text):
    match = re.search(
        r"\b[A-Za-z]{2,5}[- ]?\d{4,12}\b",
        text
    )

    if match:
        return match.group().replace(" ", "").replace("-", "").upper()

    return None


# =========================================================
# SUPPORTED FORM FIELDS
# =========================================================
# These are the fields that FormVoice currently supports.
#
# The target_field received from the frontend must be one
# of these values.

FORM_FIELDS = {
    "name",
    "dob",
    "phone",
    "email",
    "application_id",
    "pin",
    "address",
    "city",
    "state",
    "paragraph",
}


# =========================================================
# GENERAL TEXT CLEANING
# =========================================================
# Removes unnecessary spaces and punctuation from captured
# text before putting it into a form field.

def clean_text(value):
    return re.sub(r"\s+", " ", value).strip(" ,.:;-")


# =========================================================
# REMOVE SPOKEN FIELD PREFIX
# =========================================================
# Removes phrases that users naturally say when speaking.
#
# Examples:
#   "my name is Rahul Sharma" → "Rahul Sharma"
#   "my city is Pune"         → "Pune"
#   "address is Pune..."      → "Pune..."
#
# This allows the user to speak naturally instead of having
# to say only the raw value.

def strip_field_prefix(value, prefixes):
    prefix_pattern = "|".join(re.escape(prefix) for prefix in prefixes)

    return re.sub(
        rf"^\s*(?:my\s+)?(?:{prefix_pattern})(?:\s+is|\s*:)?\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )


# =========================================================
# FIELD-SPECIFIC NORMALIZATION
# =========================================================
# Each form field has its own normalization function.
#
# The purpose is to convert the transcript into a value that
# is appropriate for that particular field.
#
# Examples:
#   Name  → proper capitalization
#   DOB   → standard date format
#   Email → convert "at" and "dot"
#   PIN   → spoken numbers to digits
#   City  → clean + capitalization


def normalize_name(value):
    return clean_text(strip_field_prefix(value, ["full name", "name"])).title()


def normalize_dob(value):
    value = clean_text(strip_field_prefix(value, ["date of birth", "dob"]))

    value = re.sub(
        r"(\d+)(st|nd|rd|th)\b",
        r"\1",
        value,
        flags=re.IGNORECASE
    )

    normalized = re.sub(r"[.-]", "/", value)

    for format_string in (
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d %B %Y",
        "%B %d %Y",
        "%d %b %Y",
        "%b %d %Y",
    ):
        try:
            return datetime.strptime(
                normalized,
                format_string
            ).strftime("%d/%m/%Y")

        except ValueError:
            pass

    return value


def normalize_email(value):
    value = strip_field_prefix(
        value,
        ["email address", "email", "e-mail"]
    )

    # Converts spoken "at" → @
    value = re.sub(
        r"\s+(?:at)\s+",
        "@",
        value,
        flags=re.IGNORECASE
    )

    # Converts spoken "dot" → .
    value = re.sub(
        r"\s+(?:dot)\s+",
        ".",
        value,
        flags=re.IGNORECASE
    )

    return re.sub(r"\s+", "", value).lower()


def normalize_application_id(value):
    extracted = extract_application_id(value)

    return extracted or clean_text(
        strip_field_prefix(
            value,
            ["application id", "application number"]
        )
    ).replace(" ", "").replace("-", "").upper()


def normalize_pin(value):
    value = strip_field_prefix(
        value,
        ["pin code", "pin"]
    )

    digits = spoken_digits(value)

    return digits or clean_text(value)


def normalize_address(value):
    return clean_text(
        strip_field_prefix(value, ["address"])
    ).title()


def normalize_city(value):
    return clean_text(
        strip_field_prefix(value, ["city"])
    ).title()


def normalize_state(value):
    return clean_text(
        strip_field_prefix(value, ["state"])
    ).title()


def normalize_paragraph(value):
    return clean_text(
        strip_field_prefix(
            value,
            ["paragraph", "description"]
        )
    )


# =========================================================
# FIELD NORMALIZER SELECTOR
# =========================================================
# Connects each field name to the correct normalization
# function.
#
# Example:
#
# target_field = "name"
#       ↓
# normalize_name()
#
# target_field = "phone"
#       ↓
# extract_phone()

def normalize_field(field, text):
    normalizers = {
        "name": normalize_name,
        "dob": normalize_dob,
        "phone": extract_phone,
        "email": normalize_email,
        "application_id": normalize_application_id,
        "pin": normalize_pin,
        "address": normalize_address,
        "city": normalize_city,
        "state": normalize_state,
        "paragraph": normalize_paragraph,
    }

    return normalizers[field](text)


# =========================================================
# FIELD EXTRACTION
# =========================================================
# This is the main part responsible for putting the spoken
# value into the correct form field.
#
# There are two modes:
#
# 1. FIELD-SPECIFIC MODE
#    Used when the user clicks an individual mic.
#
#    Example:
#    Name mic → "Rahul Sharma"
#             → target_field = "name"
#             → normalize_name()
#             → name = "Rahul Sharma"
#
# 2. WHOLE-FORM MODE
#    Used when the main Speak button is used.
#    The backend tries to detect fields from the transcript.

def extract_fields(text, current, target_field=None):

    # Copy the current form so we can update it.
    updated = current.copy()

    # -----------------------------------------------------
    # FIELD-SPECIFIC MODE
    # -----------------------------------------------------
    # If target_field exists, process ONLY that field.

    if target_field:

        # Make sure the requested field is supported.
        if target_field not in FORM_FIELDS:
            raise ValueError(
                f"Unsupported target field: {target_field}"
            )

        # Select the appropriate normalizer.
        value = normalize_field(
            target_field,
            text
        )

        # Put the result into the selected field.
        if value:
            updated[target_field] = value

        return updated

    # -----------------------------------------------------
    # WHOLE-FORM MODE
    # -----------------------------------------------------
    # If no target field was provided, the system tries to
    # detect different fields from the transcript.

    lower = text.lower()

    # Phone number detection.
    phone = extract_phone(text)

    if phone:
        updated["phone"] = phone

    # Application ID detection.
    application_id = extract_application_id(text)

    if application_id:
        updated["application_id"] = application_id

    # These fields are detected using spoken labels.
    labelled_fields = {
        "name": ("name is", "my name"),
        "dob": ("date of birth", "dob"),
        "email": ("email", "e-mail"),
        "pin": ("pin",),
        "address": ("address is", "my address"),
        "city": ("city",),
        "state": ("state",),
        "paragraph": ("paragraph", "description"),
    }

    # Check whether any field-specific marker exists
    # in the transcript.
    for field, markers in labelled_fields.items():

        if any(marker in lower for marker in markers):

            # Normalize the detected field.
            value = normalize_field(
                field,
                text
            )

            if value:
                updated[field] = value

    return updated


# =========================================================
# SPEECH-SAFE IDENTIFIER
# =========================================================
# Adds spaces between characters so identifiers are easier
# to pronounce clearly if they are later sent to TTS.
#
# Example:
#   APP123
#       ↓
#   A P P 1 2 3

def speech_safe_id(value):

    if not value:
        return ""

    return " ".join(value)


# =========================================================
# RESPONSE / CONFIRMATION MESSAGE
# =========================================================
# Creates a message that can be displayed to the user.
#
# Currently it gives special messages for:
#   Application ID
#   Phone
#   Name
#
# This is separate from the actual field-filling logic.

def generate_message(form):

    if form.get("application_id"):

        spoken_id = speech_safe_id(
            form["application_id"]
        )

        return (
            f"I heard application ID "
            f"{spoken_id}. "
            f"Is that correct?"
        )

    if form.get("phone"):

        spoken_phone = speech_safe_id(
            form["phone"]
        )

        return (
            f"I heard phone number "
            f"{spoken_phone}. "
            f"Is that correct?"
        )

    if form.get("name"):

        return (
            f"I heard your name as "
            f"{form['name']}. "
            f"Is that correct?"
        )

    return "Please tell me your details."


# =========================================================
# PROCESS-VOICE ENDPOINT
# =========================================================
# This endpoint receives the transcript from the frontend
# and converts it into form values.
#
# Field mic flow:
#
# /transcribe
#      ↓
# transcript
#      ↓
# /process-voice
#      ↓
# target_field
#      ↓
# normalize selected field
#      ↓
# updated form
#
# If target_field is missing, whole-form processing is used.

@app.post("/process-voice")
async def process_voice(request: VoiceRequest):

    # Validate the requested field.
    if (
        request.target_field
        and request.target_field not in FORM_FIELDS
    ):
        raise HTTPException(
            status_code=422,
            detail="Unsupported target field."
        )

    # Extract and normalize the transcript.
    form = extract_fields(
        request.text,
        request.current_form,
        request.target_field,
    )

    # Create the response message.
    message = generate_message(form)


    # =====================================================
    # TEXT-TO-SPEECH PLACEHOLDER
    # =====================================================
    # TTS has not been connected yet.
    # Currently audio_url is therefore None.
    #
    # Future:
    # audio_url = await generate_rime_audio(message)

    audio_url = None


    # Return the updated form and response message.
    return {
        "form": form,
        "message": message,
        "audio_url": audio_url
    }


# =========================================================
# ROOT / HEALTH CHECK
# =========================================================
# Simple endpoint used to confirm that the backend is
# running correctly.

@app.get("/")
def root():

    return {
        "status": "FormVoice backend running"
    }