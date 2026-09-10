# ============================================================
# VOICERECRUIT - FINAL MAIN.PY
# ============================================================
#
# LLM       : Groq - Llama 3.3 70B
# STT       : Groq - Whisper Large V3 Turbo
# TTS       : Rime - Coda
# FRAMEWORK : FastAPI
# ORCHESTRATION : LangChain
#
# ENVIRONMENT:
#
# GROQ_API_KEY=...
# RIME_API_KEY=...
#
# NO HUGGING FACE REQUIRED
#
# ============================================================

import os
import re
import json
import base64
import uuid
import tempfile
from typing import Any, Dict, List, Optional

import requests

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from pypdf import PdfReader

from groq import Groq

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RIME_API_KEY = os.getenv("RIME_API_KEY")


# ============================================================
# CONFIGURATION
# ============================================================

# Groq LLM
GROQ_LLM_MODEL = os.getenv(
    "GROQ_LLM_MODEL",
    "openai/gpt-oss-120b"
)

# Groq Speech-to-Text
WHISPER_MODEL = "whisper-large-v3-turbo"

# Rime
RIME_MODEL = "coda"
RIME_SPEAKER = "celeste"

RIME_URL = "https://users.rime.ai/v1/rime-tts"

# Interview length
MAX_QUESTIONS = 8


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="VoiceRecruit",
    description=(
        "AI Voice Recruiter powered by "
        "Groq, LangChain and Rime"
    ),
    version="6.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# CLIENTS
# ============================================================

groq_client = None


if GROQ_API_KEY:

    try:

        groq_client = Groq(
            api_key=GROQ_API_KEY
        )

        print(
            "Groq client initialized."
        )

    except Exception as e:

        print(
            "Groq initialization error:",
            e
        )


# ============================================================
# INTERVIEW MEMORY
# ============================================================

INTERVIEWS: Dict[
    str,
    Dict[str, Any]
] = {}


# ============================================================
# STARTUP
# ============================================================

print()
print("=" * 70)
print("                    VOICERECRUIT")
print("=" * 70)

print(
    "LLM       :",
    GROQ_LLM_MODEL
)

print(
    "STT       :",
    WHISPER_MODEL
)

print(
    "TTS       :",
    RIME_MODEL
)

print(
    "Speaker   :",
    RIME_SPEAKER
)

print(
    "Groq      :",
    "READY" if GROQ_API_KEY else "MISSING"
)

print(
    "Rime      :",
    "READY" if RIME_API_KEY else "MISSING"
)

print("=" * 70)
print()


# ============================================================
# PYDANTIC MODELS
# ============================================================

class StartInterviewRequest(BaseModel):

    candidate: Dict[str, Any] = Field(
        default_factory=dict
    )

    job: Dict[str, Any] = Field(
        default_factory=dict
    )


class ProcessAnswerRequest(BaseModel):

    transcript: str

    current_question: str

    candidate: Dict[str, Any] = Field(
        default_factory=dict
    )

    job: Dict[str, Any] = Field(
        default_factory=dict
    )

    conversation: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    interview_id: Optional[str] = None

    audio_duration: Optional[float] = None

    filler_words: Optional[int] = None

    wpm: Optional[float] = None


class TTSRequest(BaseModel):

    text: str


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_text_from_file(
    content: bytes,
    filename: str
) -> str:

    extension = os.path.splitext(
        filename.lower()
    )[1]

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if extension == ".pdf":

        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf"
            ) as temp:

                temp.write(content)

                temp_path = temp.name

            reader = PdfReader(
                temp_path
            )

            pages = []

            for page in reader.pages:

                text = page.extract_text()

                if text:

                    pages.append(text)

            return "\n".join(
                pages
            ).strip()

        except Exception as e:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Could not read PDF: {str(e)}"
                )
            )

        finally:

            if temp_path:

                try:

                    os.unlink(
                        temp_path
                    )

                except Exception:
                    pass

    # --------------------------------------------------------
    # TXT / MD
    # --------------------------------------------------------

    if extension in [
        ".txt",
        ".md"
    ]:

        return content.decode(
            "utf-8",
            errors="ignore"
        ).strip()

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported file type. "
            "Use PDF, TXT or MD."
        )
    )


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_llm_output(
    text: str
) -> str:

    if not text:

        return ""

    text = str(
        text
    ).strip()

    text = re.sub(
        r"^```(?:json|text)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


def extract_json(
    text: str
) -> Dict[str, Any]:

    text = clean_llm_output(
        text
    )

    # Direct JSON
    try:

        result = json.loads(
            text
        )

        if isinstance(
            result,
            dict
        ):

            return result

    except Exception:
        pass

    # JSON embedded in text
    start = text.find("{")

    end = text.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):

        candidate = text[
            start:end + 1
        ]

        try:

            result = json.loads(
                candidate
            )

            if isinstance(
                result,
                dict
            ):

                return result

        except Exception:
            pass

    raise ValueError(
        "Invalid JSON returned by Groq."
    )


def count_words(
    text: str
) -> int:

    return len(
        re.findall(
            r"\b[\w'-]+\b",
            text or ""
        )
    )


def count_fillers(
    text: str
) -> int:

    if not text:

        return 0

    pattern = re.compile(
        r"\b("
        r"um+|uh+|erm|hmm|"
        r"like|you know|basically|"
        r"actually|literally|"
        r"sort of|kind of"
        r")\b",
        re.IGNORECASE
    )

    return len(
        pattern.findall(
            text
        )
    )


def calculate_wpm(
    text: str,
    duration_seconds: Optional[float]
) -> Optional[float]:

    if (
        duration_seconds is None
        or duration_seconds <= 0
    ):

        return None

    words = count_words(
        text
    )

    if words == 0:

        return 0.0

    return round(
        words / (
            duration_seconds / 60
        ),
        1
    )


def conversation_to_text(
    conversation: List[
        Dict[str, Any]
    ]
) -> str:

    lines = []

    for item in conversation:

        role = item.get(
            "role",
            "unknown"
        )

        content = item.get(
            "content",
            ""
        )

        lines.append(
            f"{role.upper()}: {content}"
        )

    return "\n".join(
        lines
    )


# ============================================================
# GROQ LLM
# ============================================================
#
# This completely replaces Hugging Face.
#
# Groq official usage:
#
# client.chat.completions.create(...)
#
# ============================================================

def groq_generate(
    prompt: str,
    max_tokens: int = 1200,
    temperature: float = 0.1
) -> str:

    if groq_client is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "GROQ_API_KEY is missing."
            )
        )

    try:

        print()
        print("-" * 70)
        print("GROQ LLM REQUEST")
        print("MODEL:", GROQ_LLM_MODEL)
        print("-" * 70)

        completion = (
            groq_client
            .chat
            .completions
            .create(

                model=GROQ_LLM_MODEL,

                messages=[
                    {
                        "role":
                            "user",

                        "content":
                            prompt
                    }
                ],

                temperature=
                    temperature,

                max_completion_tokens=
                    max_tokens,

                stream=False
            )
        )

        if not completion.choices:

            raise RuntimeError(
                "Groq returned no choices."
            )

        content = (
            completion
            .choices[0]
            .message
            .content
        )

        if not content:

            raise RuntimeError(
                "Groq returned empty content."
            )

        print(
            "Groq response received."
        )

        return str(
            content
        ).strip()

    except HTTPException:

        raise

    except Exception as e:

        print()
        print("=" * 70)
        print("GROQ LLM ERROR")
        print("=" * 70)
        print(str(e))
        print("=" * 70)

        raise HTTPException(
            status_code=500,
            detail=(
                f"Groq LLM error: {str(e)}"
            )
        )


# ============================================================
# LANGCHAIN
# ============================================================

groq_runnable = RunnableLambda(
    lambda prompt:
        groq_generate(
            prompt,
            max_tokens=1200,
            temperature=0.1
        )
)


def run_langchain_prompt(
    prompt_template: ChatPromptTemplate,
    variables: Dict[str, Any]
) -> str:

    try:

        messages = (
            prompt_template
            .format_messages(
                **variables
            )
        )

        prompt_text = "\n\n".join(

            message.content

            for message in messages
        )

        result = (
            groq_runnable
            .invoke(
                prompt_text
            )
        )

        return clean_llm_output(
            result
        )

    except HTTPException:

        raise

    except Exception as e:

        print(
            "LangChain error:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"LangChain error: {str(e)}"
            )
        )


# ============================================================
# ANALYSIS PROMPT
# ============================================================

analysis_prompt = ChatPromptTemplate.from_messages(
    [

        (
            "system",

            """
You are VoiceRecruit, an expert technical recruiter.

Analyze the candidate resume against the job description.

Extract:

CANDIDATE:
- name
- email
- phone
- skills
- projects
- experience
- education
- summary

JOB:
- title
- skills
- responsibilities

MATCH:
- matching_skills
- missing_skills

INTERVIEW:
- interview_focus

Do not invent information.

Only use information present in the
resume and job description.

Return ONLY valid JSON.

The JSON must contain these top-level keys:

candidate
job
matching_skills
missing_skills
interview_focus

The candidate object should contain:

name
email
phone
skills
projects
experience
education
summary

The job object should contain:

title
skills
responsibilities

matching_skills must be an array.

missing_skills must be an array.

interview_focus must be an array.

Do not use markdown.
Do not use code fences.
Do not write anything outside the JSON.
"""
        ),

        (
            "human",

            """
RESUME:

{resume}

JOB DESCRIPTION:

{job}
"""
        )
    ]
)


# ============================================================
# ANSWER EVALUATION PROMPT
# ============================================================

evaluation_prompt = ChatPromptTemplate.from_messages(
    [

        (
            "system",

            """
You are an expert technical interviewer.

Evaluate the candidate's answer.

Score from 0 to 100:

technical_score
depth_score
relevance_score
problem_solving_score
grammar_score
communication_score
vocabulary_score
professional_tone_score
confidence_score

Also provide:

strengths
weaknesses
feedback
next_topic
follow_up_needed

Return ONLY valid JSON.

Required keys:

technical_score
depth_score
relevance_score
problem_solving_score
grammar_score
communication_score
vocabulary_score
professional_tone_score
confidence_score
strengths
weaknesses
feedback
next_topic
follow_up_needed

All scores must be integers from 0 to 100.

strengths must be an array.

weaknesses must be an array.

follow_up_needed must be true or false.

Evaluate only the candidate's actual answer.

Do not invent experience.

Do not use markdown.
Do not use code fences.
Do not write anything outside the JSON.

"""
        ),

        (
            "human",

            """
CANDIDATE:

{candidate}

JOB:

{job}

INTERVIEW QUESTION:

{question}

CANDIDATE ANSWER:

{answer}

PREVIOUS CONVERSATION:

{conversation}
"""
        )
    ]
)


# ============================================================
# NEXT QUESTION PROMPT
# ============================================================

question_prompt = ChatPromptTemplate.from_messages(
    [

        (
            "system",

            """
You are VoiceRecruit, an AI technical recruiter.

Generate exactly ONE next interview question.

Use:

1. Candidate resume
2. Job description
3. Current question
4. Candidate's latest answer
5. Evaluation of the answer
6. Previous conversation

Rules:

- Personalize the question.
- Ask about actual candidate experience.
- Test technical depth.
- Probe weak reasoning.
- Ask follow-up questions when appropriate.
- Ask about important missing job requirements.
- Gradually increase difficulty.
- Never repeat an earlier question.
- Ask only ONE question.
- Make it natural for spoken conversation.
- Do not number it.
- Do not explain your reasoning.
and make sure that you keep it diverse you should not be stucked on single project or skill 
also ask personal preferences keep it real like interview 
do not include "can you walk me through" in every question

Return ONLY the question.
"""
        ),

        (
            "human",

            """
CANDIDATE:

{candidate}

JOB:

{job}

CURRENT QUESTION:

{current_question}

LATEST ANSWER:

{answer}

LATEST EVALUATION:

{evaluation}

PREVIOUS CONVERSATION:

{conversation}
"""
        )
    ]
)


# ============================================================
# FINAL REPORT PROMPT
# ============================================================

final_report_prompt = ChatPromptTemplate.from_messages(
    [

        (
            "system",

            """
You are a senior technical recruiter.

Create a final interview assessment.

Evaluate:

technical knowledge
problem solving
communication
grammar
job fit
confidence
clarity
vocabulary
professional tone
answer structure
answer completion

Also provide:

verdict
summary
strengths
improvements
technical_summary
communication_summary
grammar_summary
job_fit_summary
recommendation

Return ONLY valid JSON.

Required keys:

overall_score
technical_knowledge
problem_solving
communication
grammar
job_fit
confidence
clarity
vocabulary
professional_tone
answer_structure
answer_completion
verdict
summary
strengths
improvements
technical_summary
communication_summary
grammar_summary
job_fit_summary
recommendation

All scores must be integers from 0 to 100.

strengths must be an array.

improvements must be an array.

Do not invent information.

Confidence must be based only on observable
communication characteristics such as hesitation,
fluency and clarity.

Do not make psychological or medical claims.

Do not use markdown.
Do not use code fences.
Do not write anything outside JSON.
"""
        ),

        (
            "human",

            """
CANDIDATE:

{candidate}

JOB:

{job}

INTERVIEW CONVERSATION:

{conversation}

ANSWER EVALUATIONS:

{evaluations}

VOICE METRICS:

{voice_metrics}
"""
        )
    ]
)


# ============================================================
# GENERATE JSON
# ============================================================

def generate_json(
    prompt_template: ChatPromptTemplate,
    variables: Dict[str, Any]
) -> Dict[str, Any]:

    raw = run_langchain_prompt(
        prompt_template,
        variables
    )

    try:

        return extract_json(
            raw
        )

    except Exception as e:

        print(
            "Initial JSON parsing failed:",
            e
        )

        # ----------------------------------------------------
        # Groq retry
        # ----------------------------------------------------

        retry_prompt = f"""
You are a JSON repair system.

Convert the following response into
valid JSON.

Return ONLY valid JSON.

Do not explain anything.

MODEL RESPONSE:

{raw}
"""

        retry = groq_generate(
            retry_prompt,
            max_tokens=1600,
            temperature=0
        )

        try:

            return extract_json(
                retry
            )

        except Exception as second_error:

            print(
                "JSON retry failed:",
                second_error
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Groq returned invalid JSON."
                )
            )


# ============================================================
# RIME TTS
# ============================================================

def text_to_speech(
    text: str
) -> str:

    if not RIME_API_KEY:

        print(
            "RIME_API_KEY is missing."
        )

        return ""

    text = (
        text
        .strip()
    )

    if not text:

        return ""

    print()
    print("-" * 70)
    print("RIME TTS")
    print("TEXT:", text)
    print("MODEL:", RIME_MODEL)
    print("SPEAKER:", RIME_SPEAKER)
    print("-" * 70)

    headers = {

        "Authorization":
            f"Bearer {RIME_API_KEY}",

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav, audio/*, application/json"
    }

    payload = {

        "text":
            text,

        "speaker":
            RIME_SPEAKER,

        "modelId":
            RIME_MODEL
    }

    try:

        response = requests.post(

            RIME_URL,

            headers=headers,

            json=payload,

            timeout=60
        )

        print(
            "Rime status:",
            response.status_code
        )

        if not response.ok:

            print(
                "Rime response:",
                response.text
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Rime TTS failed: "
                    f"{response.status_code} "
                    f"{response.text}"
                )
            )

        content_type = (
            response
            .headers
            .get(
                "content-type",
                ""
            )
            .lower()
        )

        # ----------------------------------------------------
        # RAW AUDIO
        # ----------------------------------------------------

        if (
            "audio" in content_type
            or "octet-stream" in content_type
        ):

            return base64.b64encode(
                response.content
            ).decode(
                "utf-8"
            )

        # ----------------------------------------------------
        # JSON RESPONSE
        # ----------------------------------------------------

        try:

            data = response.json()

        except Exception:

            return base64.b64encode(
                response.content
            ).decode(
                "utf-8"
            )

        for key in [

            "audio",

            "audioContent",

            "audio_content",

            "data"

        ]:

            value = data.get(
                key
            )

            if value:

                return str(
                    value
                )

        raise HTTPException(
            status_code=500,
            detail=(
                "Rime returned no audio."
            )
        )

    except HTTPException:

        raise

    except Exception as e:

        print(
            "Rime exception:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Rime TTS error: {str(e)}"
            )
        )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "name":
            "VoiceRecruit",

        "status":
            "running",

        "llm":
            GROQ_LLM_MODEL,

        "stt":
            WHISPER_MODEL,

        "tts":
            RIME_MODEL,

        "speaker":
            RIME_SPEAKER
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "status":
            "ok",

        "llm":
            groq_client is not None,

        "llm_provider":
            "Groq",

        "llm_model":
            GROQ_LLM_MODEL,

        "langchain":
            True,

        "stt":
            groq_client is not None,

        "stt_provider":
            "Groq Whisper",

        "stt_model":
            WHISPER_MODEL,

        "tts":
            bool(RIME_API_KEY),

        "tts_provider":
            "Rime",

        "tts_model":
            RIME_MODEL,

        "tts_speaker":
            RIME_SPEAKER
    }


# ============================================================
# ANALYZE RESUME + JOB
# ============================================================

@app.post("/analyze")
async def analyze(

    resume: UploadFile = File(...),

    job_description: UploadFile = File(...)
):

    resume_bytes = await resume.read()

    job_bytes = await job_description.read()

    resume_text = extract_text_from_file(

        resume_bytes,

        resume.filename
        or "resume.pdf"
    )

    job_text = extract_text_from_file(

        job_bytes,

        job_description.filename
        or "job.pdf"
    )

    if not resume_text:

        raise HTTPException(
            status_code=400,
            detail="Resume is empty."
        )

    if not job_text:

        raise HTTPException(
            status_code=400,
            detail="Job description is empty."
        )

    print()
    print("=" * 70)
    print("ANALYZING RESUME + JOB")
    print("=" * 70)

    result = generate_json(

        analysis_prompt,

        {

            "resume":
                resume_text[:30000],

            "job":
                job_text[:20000]
        }
    )

    return {

        "success":
            True,

        "resume_text":
            resume_text,

        "job_description":
            job_text,

        "analysis":
            result,

        "candidate":
            result.get(
                "candidate",
                {}
            ),

        "job":
            result.get(
                "job",
                {}
            ),

        "matching_skills":
            result.get(
                "matching_skills",
                []
            ),

        "missing_skills":
            result.get(
                "missing_skills",
                []
            ),

        "interview_focus":
            result.get(
                "interview_focus",
                []
            )
    }


# ============================================================
# START INTERVIEW
# ============================================================

@app.post("/start-interview")
async def start_interview(

    request: StartInterviewRequest
):

    interview_id = str(
        uuid.uuid4()
    )

    candidate = request.candidate

    job = request.job

    # --------------------------------------------------------
    # Generate first question using GROQ
    # --------------------------------------------------------

    prompt = f"""
You are a professional technical recruiter.

Start a personalized technical interview.

CANDIDATE:

{json.dumps(
    candidate,
    indent=2,
    ensure_ascii=False
)}

JOB DESCRIPTION:

{json.dumps(
    job,
    indent=2,
    ensure_ascii=False
)}

Ask ONE strong opening question.

The question should:

- relate to the candidate's actual experience
- relate to the job
- be natural when spoken
- encourage the candidate to explain something

Return ONLY the question.

Do not number it.
Do not explain anything.
"""

    first_question = groq_generate(
        prompt,
        max_tokens=300,
        temperature=0.3
    )

    first_question = clean_llm_output(
        first_question
    )

    # --------------------------------------------------------
    # RIME
    # --------------------------------------------------------

    audio = text_to_speech(
        first_question
    )

    # --------------------------------------------------------
    # STORE
    # --------------------------------------------------------

    INTERVIEWS[
        interview_id
    ] = {

        "candidate":
            candidate,

        "job":
            job,

        "conversation": [

            {

                "role":
                    "recruiter",

                "content":
                    first_question
            }
        ],

        "evaluations":
            [],

        "voice_metrics":
            [],

        "question_count":
            1,

        "report":
            None
    }

    return {

        "success":
            True,

        "interview_id":
            interview_id,

        "question":
            first_question,

        "next_question":
            first_question,

        "audio":
            audio,

        "question_number":
            1,

        "complete":
            False
    }


# ============================================================
# TRANSCRIBE AUDIO
# ============================================================

@app.post("/transcribe")
async def transcribe(

    file: UploadFile = File(...)
):

    if groq_client is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "GROQ_API_KEY is missing."
            )
        )

    audio_bytes = await file.read()

    if not audio_bytes:

        raise HTTPException(
            status_code=400,
            detail="Audio is empty."
        )

    filename = (
        file.filename
        or "answer.webm"
    )

    try:

        transcription = (

            groq_client
            .audio
            .transcriptions
            .create(

                file=(
                    filename,
                    audio_bytes
                ),

                model=
                    WHISPER_MODEL,

                response_format=
                    "verbose_json",

                temperature=
                    0.0,

                language=
                    "en"
            )
        )

        transcript = (
            getattr(
                transcription,
                "text",
                ""
            )
            or ""
        ).strip()

        duration = getattr(
            transcription,
            "duration",
            None
        )

        filler_words = count_fillers(
            transcript
        )

        word_count = count_words(
            transcript
        )

        wpm = calculate_wpm(
            transcript,
            duration
        )

        return {

            "success":
                True,

            "transcript":
                transcript,

            "text":
                transcript,

            "duration":
                duration,

            "word_count":
                word_count,

            "filler_words":
                filler_words,

            "wpm":
                wpm
        }

    except Exception as e:

        print(
            "Whisper error:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Whisper transcription failed: {str(e)}"
            )
        )


# ============================================================
# EVALUATE ANSWER
# ============================================================

def evaluate_answer(

    candidate: Dict[str, Any],

    job: Dict[str, Any],

    question: str,

    answer: str,

    conversation:
        List[Dict[str, Any]]
) -> Dict[str, Any]:

    return generate_json(

        evaluation_prompt,

        {

            "candidate":
                json.dumps(
                    candidate,
                    indent=2,
                    ensure_ascii=False
                ),

            "job":
                json.dumps(
                    job,
                    indent=2,
                    ensure_ascii=False
                ),

            "question":
                question,

            "answer":
                answer,

            "conversation":
                conversation_to_text(
                    conversation
                )
        }
    )


# ============================================================
# GENERATE NEXT QUESTION
# ============================================================

def generate_next_question(

    candidate: Dict[str, Any],

    job: Dict[str, Any],

    current_question: str,

    answer: str,

    evaluation: Dict[str, Any],

    conversation:
        List[Dict[str, Any]]
) -> str:

    question = run_langchain_prompt(

        question_prompt,

        {

            "candidate":
                json.dumps(
                    candidate,
                    indent=2,
                    ensure_ascii=False
                ),

            "job":
                json.dumps(
                    job,
                    indent=2,
                    ensure_ascii=False
                ),

            "current_question":
                current_question,

            "answer":
                answer,

            "evaluation":
                json.dumps(
                    evaluation,
                    indent=2,
                    ensure_ascii=False
                ),

            "conversation":
                conversation_to_text(
                    conversation
                )
        }
    )

    question = clean_llm_output(
        question
    )

    question = re.sub(

        r"^(question\s*\d*\s*[:.\-]\s*)",

        "",

        question,

        flags=re.IGNORECASE
    )

    return question.strip()


# ============================================================
# FINAL REPORT
# ============================================================

def generate_final_report(

    candidate: Dict[str, Any],

    job: Dict[str, Any],

    conversation:
        List[Dict[str, Any]],

    evaluations:
        List[Dict[str, Any]],

    voice_metrics:
        List[Dict[str, Any]]
) -> Dict[str, Any]:

    report = generate_json(

        final_report_prompt,

        {

            "candidate":
                json.dumps(
                    candidate,
                    indent=2,
                    ensure_ascii=False
                ),

            "job":
                json.dumps(
                    job,
                    indent=2,
                    ensure_ascii=False
                ),

            "conversation":
                conversation_to_text(
                    conversation
                ),

            "evaluations":
                json.dumps(
                    evaluations,
                    indent=2,
                    ensure_ascii=False
                ),

            "voice_metrics":
                json.dumps(
                    voice_metrics,
                    indent=2,
                    ensure_ascii=False
                )
        }
    )

    score_fields = [

        "overall_score",

        "technical_knowledge",

        "problem_solving",

        "communication",

        "grammar",

        "job_fit",

        "confidence",

        "clarity",

        "vocabulary",

        "professional_tone",

        "answer_structure",

        "answer_completion"
    ]

    for field in score_fields:

        if field in report:

            try:

                report[field] = max(
                    0,
                    min(
                        100,
                        int(
                            float(
                                report[field]
                            )
                        )
                    )
                )

            except Exception:

                report[field] = 0

    # --------------------------------------------------------
    # Voice statistics
    # --------------------------------------------------------

    wpms = [

        x.get("wpm")

        for x in voice_metrics

        if x.get("wpm") is not None
    ]

    average_wpm = None

    if wpms:

        average_wpm = round(

            sum(wpms)
            /
            len(wpms),

            1
        )

    total_fillers = sum(

        int(
            x.get(
                "filler_words",
                0
            ) or 0
        )

        for x in voice_metrics
    )

    report["voice_metrics"] = {

        "average_wpm":
            average_wpm,

        "total_filler_words":
            total_fillers,

        "answers_analyzed":
            len(
                voice_metrics
            )
    }

    return report


# ============================================================
# PROCESS ANSWER
# ============================================================
#
# END ANSWER
#      |
#      v
# Groq Whisper
#      |
#      v
# Evaluate answer
#      |
#      v
# Generate next question
#      |
#      v
# Rime speaks next question
#      |
#      v
# Return next_question + audio
#
# ============================================================

@app.post("/process-answer")
async def process_answer(

    request: ProcessAnswerRequest
):

    transcript = (
        request.transcript
        or ""
    ).strip()

    if not transcript:

        raise HTTPException(
            status_code=400,
            detail="Transcript is empty."
        )

    # --------------------------------------------------------
    # LOAD INTERVIEW
    # --------------------------------------------------------

    interview = None

    if request.interview_id:

        interview = INTERVIEWS.get(
            request.interview_id
        )

    if interview:

        candidate = interview[
            "candidate"
        ]

        job = interview[
            "job"
        ]

        conversation = interview[
            "conversation"
        ]

        evaluations = interview[
            "evaluations"
        ]

        voice_metrics = interview[
            "voice_metrics"
        ]

    else:

        candidate = request.candidate

        job = request.job

        conversation = list(
            request.conversation
            or []
        )

        evaluations = []

        voice_metrics = []

    # --------------------------------------------------------
    # EVALUATE ANSWER
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("EVALUATING CANDIDATE ANSWER")
    print("=" * 70)

    evaluation = evaluate_answer(

        candidate=
            candidate,

        job=
            job,

        question=
            request.current_question,

        answer=
            transcript,

        conversation=
            conversation
    )

    # --------------------------------------------------------
    # STORE ANSWER
    # --------------------------------------------------------

    conversation.append(

        {

            "role":
                "candidate",

            "content":
                transcript
        }
    )

    # --------------------------------------------------------
    # VOICE METRICS
    # --------------------------------------------------------

    filler_words = (

        request.filler_words

        if request.filler_words
        is not None

        else count_fillers(
            transcript
        )
    )

    wpm = request.wpm

    if wpm is None:

        wpm = calculate_wpm(

            transcript,

            request.audio_duration
        )

    voice_metric = {

        "duration":
            request.audio_duration,

        "word_count":
            count_words(
                transcript
            ),

        "filler_words":
            filler_words,

        "wpm":
            wpm
    }

    voice_metrics.append(
        voice_metric
    )

    evaluations.append(
        evaluation
    )

    # --------------------------------------------------------
    # QUESTION COUNT
    # --------------------------------------------------------

    recruiter_questions = sum(

        1

        for item in conversation

        if item.get(
            "role"
        ) == "recruiter"
    )

    should_finish = (

        recruiter_questions
        >= MAX_QUESTIONS
    )

    # --------------------------------------------------------
    # FINISH AFTER QUESTION 7 IF
    # NO FOLLOW-UP IS NEEDED
    # --------------------------------------------------------

    if (

        recruiter_questions >= 7

        and not evaluation.get(
            "follow_up_needed",
            False
        )
    ):

        should_finish = True

    # ========================================================
    # FINAL REPORT
    # ========================================================

    if should_finish:

        print()
        print("=" * 70)
        print("GENERATING FINAL REPORT")
        print("=" * 70)

        report = generate_final_report(

            candidate=
                candidate,

            job=
                job,

            conversation=
                conversation,

            evaluations=
                evaluations,

            voice_metrics=
                voice_metrics
        )

        if interview:

            interview[
                "conversation"
            ] = conversation

            interview[
                "evaluations"
            ] = evaluations

            interview[
                "voice_metrics"
            ] = voice_metrics

            interview[
                "report"
            ] = report

        return {

            "success":
                True,

            "complete":
                True,

            "completed":
                True,

            "evaluation":
                evaluation,

            "report":
                report,

            "conversation":
                conversation,

            "next_question":
                "",

            "question":
                "",

            "audio":
                ""
        }

    # ========================================================
    # GENERATE NEXT QUESTION
    # ========================================================

    print()
    print("=" * 70)
    print("GENERATING NEXT QUESTION")
    print("=" * 70)

    next_question = generate_next_question(

        candidate=
            candidate,

        job=
            job,

        current_question=
            request.current_question,

        answer=
            transcript,

        evaluation=
            evaluation,

        conversation=
            conversation
    )

    if not next_question:

        raise HTTPException(
            status_code=500,
            detail=(
                "Groq failed to generate next question."
            )
        )

    # --------------------------------------------------------
    # SAVE NEXT QUESTION
    # --------------------------------------------------------

    conversation.append(

        {

            "role":
                "recruiter",

            "content":
                next_question
        }
    )

    # --------------------------------------------------------
    # UPDATE INTERVIEW
    # --------------------------------------------------------

    if interview:

        interview[
            "conversation"
        ] = conversation

        interview[
            "evaluations"
        ] = evaluations

        interview[
            "voice_metrics"
        ] = voice_metrics

        interview[
            "question_count"
        ] = recruiter_questions + 1

    # ========================================================
    # RIME
    # ========================================================

    print()
    print("=" * 70)
    print("GENERATING RIME AUDIO")
    print("=" * 70)

    audio = text_to_speech(
        next_question
    )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {

        "success":
            True,

        "complete":
            False,

        "completed":
            False,

        # Evaluation of previous answer
        "evaluation":
            evaluation,

        # NEW QUESTION
        "next_question":
            next_question,

        # Compatibility
        "question":
            next_question,

        # RIME AUDIO
        "audio":
            audio,

        "question_number":
            recruiter_questions + 1,

        "conversation":
            conversation,

        "voice_metric":
            voice_metric
    }


# ============================================================
# DIRECT RIME TTS TEST
# ============================================================

@app.post("/tts")
async def tts(
    request: TTSRequest
):

    text = (
        request.text
        or ""
    ).strip()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty."
        )

    audio = text_to_speech(
        text
    )

    return {

        "success":
            True,

        "text":
            text,

        "audio":
            audio
    }


# ============================================================
# GET INTERVIEW
# ============================================================

@app.get(
    "/interview/{interview_id}"
)
async def get_interview(

    interview_id: str
):

    interview = INTERVIEWS.get(
        interview_id
    )

    if not interview:

        raise HTTPException(
            status_code=404,
            detail="Interview not found."
        )

    return {

        "success":
            True,

        "interview":
            interview
    }


# ============================================================
# FINAL REPORT ENDPOINT
# ============================================================

@app.post(
    "/interview/{interview_id}/report"
)
async def interview_report(

    interview_id: str
):

    interview = INTERVIEWS.get(
        interview_id
    )

    if not interview:

        raise HTTPException(
            status_code=404,
            detail="Interview not found."
        )

    if interview.get(
        "report"
    ):

        return {

            "success":
                True,

            "report":
                interview["report"]
        }

    report = generate_final_report(

        candidate=
            interview["candidate"],

        job=
            interview["job"],

        conversation=
            interview["conversation"],

        evaluations=
            interview["evaluations"],

        voice_metrics=
            interview["voice_metrics"]
    )

    interview[
        "report"
    ] = report

    return {

        "success":
            True,

        "report":
            report
    }


# ============================================================
# SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "main:app",

        host="0.0.0.0",

        port=8000,

        reload=True
    )