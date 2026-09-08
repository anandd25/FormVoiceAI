import os
import json
import re
import uuid
import tempfile
from typing import Optional

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not HF_TOKEN:
    print("WARNING: HF_TOKEN is not set.")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set.")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="FormVoice AI API",
    description="Voice-native form filling using Groq Whisper and Qwen",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HUGGING FACE + QWEN
# ============================================================

if HF_TOKEN:

    llm = HuggingFaceEndpoint(
        repo_id="Qwen/Qwen2.5-72B-Instruct",
        huggingfacehub_api_token=HF_TOKEN,
        temperature=0.1,
        max_new_tokens=4096
    )

    model = ChatHuggingFace(
        llm=llm
    )

else:
    llm = None
    model = None


# ============================================================
# FORM STRUCTURE
# ============================================================

FORM_FIELDS = [
    "name",
    "dob",
    "phone",
    "email",
    "application_id",
    "pin",
    "address",
    "city",
    "state",
    "paragraph"
]


# ============================================================
# REQUEST MODELS
# ============================================================

class VoiceRequest(BaseModel):
    transcript: str


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "FormVoice AI backend is running",
        "services": {
            "transcription": "Groq Whisper",
            "structured_extraction": "Qwen/Qwen2.5-72B-Instruct"
        }
    }


# ============================================================
# TRANSCRIPTION
# ============================================================

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Receives microphone audio and converts it into text.

    Frontend:
        audio file
            ↓
        /transcribe
            ↓
        transcript
    """

    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured."
        )

    if not file:
        raise HTTPException(
            status_code=400,
            detail="No audio file received."
        )

    # --------------------------------------------------------
    # Save uploaded audio temporarily
    # --------------------------------------------------------

    extension = ".webm"

    if file.filename:
        original_extension = os.path.splitext(file.filename)[1]

        if original_extension:
            extension = original_extension

    temp_path = None

    try:

        audio_bytes = await file.read()

        if not audio_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded audio file is empty."
            )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension
        ) as temp_file:

            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        # ----------------------------------------------------
        # Groq Whisper
        # ----------------------------------------------------

        from groq import Groq

        client = Groq(
            api_key=GROQ_API_KEY
        )

        with open(temp_path, "rb") as audio_file:

            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3-turbo",
                response_format="verbose_json"
            )

        # ----------------------------------------------------
        # Extract transcript
        # ----------------------------------------------------

        transcript_text = getattr(
            transcription,
            "text",
            ""
        )

        if not transcript_text:
            transcript_text = ""

        request_id = str(uuid.uuid4())

        return {
            "success": True,
            "request_id": request_id,
            "transcript": {
                "text": transcript_text,
                "language": getattr(
                    transcription,
                    "language",
                    None
                ),
                "duration": getattr(
                    transcription,
                    "duration",
                    None
                )
            }
        }

    except Exception as e:

        print("TRANSCRIPTION ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

    finally:

        # ----------------------------------------------------
        # Delete temporary audio file
        # ----------------------------------------------------

        if temp_path and os.path.exists(temp_path):

            try:
                os.remove(temp_path)

            except Exception:
                pass


# ============================================================
# QWEN PROMPT
# ============================================================

def create_extraction_prompt(transcript: str) -> str:

    return f"""
You are the structured information extraction engine for FormVoice AI.

Your task is to convert a user's spoken transcript into a JSON object
for a form.

IMPORTANT:
- Return ONLY valid JSON.
- Do NOT use Markdown.
- Do NOT use ```json.
- Do NOT add explanations.
- Do NOT invent information.
- If a field is not mentioned, return an empty string.
- Preserve the information given by the user.
- Correct obvious speech-to-text artifacts when the intended value is clear.
- For phone numbers, preserve all digits.
- For PIN codes, preserve all digits.
- For application IDs, preserve letters and numbers exactly as intended.
- For email addresses, convert spoken forms such as "at" and "dot"
  into a normal email address when the intended email is obvious.
- For dates, use a consistent readable format such as DD/MM/YYYY
  when the date is clear.
- Do not guess missing values.
-give fields in english only

The JSON must contain EXACTLY these fields:

{{
    "name": "",
    "dob": "",
    "phone": "",
    "email": "",
    "application_id": "",
    "pin": "",
    "address": "",
    "city": "",
    "state": "",
    "paragraph": ""
}}

FIELD DEFINITIONS:

name:
The person's full name.

dob:
Date of birth.

phone:
Phone/mobile number.

email:
Email address.

application_id:
Application/reference/registration ID containing letters and/or numbers.

pin:
PIN code or postal PIN code.

address:
Street/building/house address.

city:
City name.

state:
State name.

paragraph:
Any additional long-form information that does not clearly belong
to another field.

IMPORTANT FOR NUMBERS AND IDENTIFIERS:

If the user says:

"my application number is A B X 2 0 4 7 8 9 1"

return:

"application_id": "ABX2047891"

If the user says:

"my phone number is nine eight seven six five four three two one zero"

return:

"phone": "9876543210"

If the user says:

"PIN is four one one zero zero seven"

return:

"pin": "411007"

Do NOT omit or modify digits.

USER TRANSCRIPT:

{transcript}

Now return ONLY the JSON object.
"""


# ============================================================
# CLEAN MODEL RESPONSE
# ============================================================

def clean_model_json(raw_output: str) -> dict:
    """
    Converts Qwen's response into a Python dictionary.

    Handles cases where the model accidentally returns:

    ```json
    {...}
    ```

    or additional text around the JSON.
    """

    if not raw_output:
        raise ValueError("Model returned an empty response.")

    text = raw_output.strip()

    # --------------------------------------------------------
    # Remove Markdown code fences
    # --------------------------------------------------------

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    # --------------------------------------------------------
    # Direct JSON parsing
    # --------------------------------------------------------

    try:

        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Try extracting JSON object from surrounding text
    # --------------------------------------------------------

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

        possible_json = text[start:end + 1]

        try:

            data = json.loads(possible_json)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not parse model response as JSON: {raw_output}"
    )


# ============================================================
# NORMALIZE OUTPUT STRUCTURE
# ============================================================

def ensure_form_fields(data: dict) -> dict:
    """
    Ensures the response contains exactly the fields expected
    by the React frontend.
    """

    result = {}

    for field in FORM_FIELDS:

        value = data.get(field, "")

        if value is None:
            value = ""

        # Convert numbers to strings so React form fields
        # receive consistent values.
        if not isinstance(value, str):
            value = str(value)

        result[field] = value.strip()

    return result


# ============================================================
# PROCESS VOICE
# ============================================================

@app.post("/process-voice")
async def process_voice(request: VoiceRequest):
    """
    Takes transcript text and uses Qwen to convert it into
    structured form JSON.
    """

    transcript = request.transcript.strip()

    if not transcript:

        raise HTTPException(
            status_code=400,
            detail="Transcript cannot be empty."
        )

    if model is None:

        raise HTTPException(
            status_code=500,
            detail="HF_TOKEN is not configured."
        )

    try:

        # ----------------------------------------------------
        # Create prompt
        # ----------------------------------------------------

        prompt = create_extraction_prompt(
            transcript
        )

        # ----------------------------------------------------
        # Send transcript to Qwen
        # ----------------------------------------------------

        response = model.invoke(prompt)

        # ----------------------------------------------------
        # Extract model text
        # ----------------------------------------------------

        if hasattr(response, "content"):

            raw_output = response.content

        else:

            raw_output = str(response)

        print("\n================ QWEN OUTPUT ================\n")
        print(raw_output)
        print("\n=============================================\n")

        # ----------------------------------------------------
        # Convert model output → JSON
        # ----------------------------------------------------

        extracted_data = clean_model_json(
            raw_output
        )

        # ----------------------------------------------------
        # Ensure correct form fields
        # ----------------------------------------------------

        form_data = ensure_form_fields(
            extracted_data
        )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "success": True,
            "data": form_data,
            "message": "Form information extracted successfully."
        }

    except Exception as e:

        print("QWEN PROCESSING ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Structured extraction failed: {str(e)}"
        )