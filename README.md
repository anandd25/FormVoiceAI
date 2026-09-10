# VoiceRecruit — AI-Powered Adaptive Voice Interviewer

> **Your AI recruiter that understands your resume, understands the job, interviews you by voice, adapts to your answers, and evaluates your job readiness.**

## Overview

**VoiceRecruit** is an AI-powered voice interview platform designed to simulate a real recruiter-driven technical interview.

Instead of presenting candidates with a fixed list of questions, VoiceRecruit first analyzes the **candidate's resume** and the **target job description**. It then generates personalized interview questions based on the candidate's actual skills, projects, experience, and the requirements of the role.

During the interview, the candidate answers naturally through their microphone. VoiceRecruit automatically detects when the candidate has finished speaking, converts the response to text using speech recognition, evaluates the answer using an LLM, and generates an appropriate follow-up question.

The next question is then spoken back to the candidate using **Rime TTS**.

This creates a continuous, recruiter-like voice conversation rather than a conventional chatbot with optional voice playback.

---

## Why VoiceRecruit?

Traditional interview-preparation platforms generally rely on:

* Static question banks
* Text-based interviews
* Fixed question sequences
* Manual answer submission
* Generic feedback

Real interviews are different.

A recruiter can see a candidate's background, ask a question, listen to the answer, identify weak areas, and immediately ask a deeper follow-up question.

**VoiceRecruit attempts to reproduce this interaction using AI and voice.**

The system follows:

```text
Resume + Job Description
          ↓
   Candidate Analysis
          ↓
 Personalized Question
          ↓
       Rime TTS
          ↓
   Candidate Speaks
          ↓
 Automatic Turn Detection
          ↓
      Speech-to-Text
          ↓
    Answer Evaluation
          ↓
 Adaptive Follow-up
          ↓
       Rime TTS
          ↓
        Continue
          ↓
     Final Assessment
```

---

# Key Features

### 1. Resume-Aware Interviewing

VoiceRecruit analyzes the candidate's resume before the interview.

It can identify:

* Technical skills
* Projects
* Work experience
* Technologies
* Education
* Relevant achievements

Questions can then be generated specifically from the candidate's background.

For example, if a candidate mentions **FastAPI and PostgreSQL**, the system can ask:

> "I noticed that you built a FastAPI application using PostgreSQL. Can you walk me through how you designed the backend architecture?"

---

### 2. Job Description-Aware Interviewing

The system also analyzes the target job description.

This allows VoiceRecruit to identify important requirements such as:

```text
Python
FastAPI
PostgreSQL
Docker
AWS
Kubernetes
System Design
```

The interview can therefore focus on skills that are actually relevant to the target role.

---

### 3. Resume × Job Matching

VoiceRecruit combines information from both sources:

```text
Candidate Resume
       +
Job Description
       ↓
Relevant Skills
       ↓
Interview Strategy
```

This prevents the interview from becoming a generic question-and-answer session.

For example, if the job requires Kubernetes but the resume does not mention it, the system can ask:

> "The role requires Kubernetes experience, but I don't see it mentioned on your resume. Have you worked with Kubernetes or any similar container orchestration technology?"

---

### 4. Adaptive Follow-Up Questions

One of the core features of VoiceRecruit is that the interview is **not completely predetermined**.

The candidate's previous answer influences the next question.

Example:

```text
Question:
Why did you choose PostgreSQL for your project?

Candidate:
I chose PostgreSQL because my application required relational
data and complex queries.

Follow-up:
You mentioned complex queries. How would you optimize the database
if the application suddenly had thousands of concurrent users?
```

The interview therefore follows a conversational path based on what the candidate actually says.

---

### 5. Voice-Native Interaction

Voice is not an optional playback feature.

The candidate interacts with the interviewer primarily through speech:

```text
Rime speaks
     ↓
Candidate listens
     ↓
Candidate answers
     ↓
System detects end of speech
     ↓
System processes answer
     ↓
Rime speaks next question
```

The goal is to minimize unnecessary button presses and make the interaction feel closer to an actual interview.

---

### 6. Automatic Turn Detection

VoiceRecruit uses browser audio processing to detect when the candidate has finished speaking.

Instead of requiring:

```text
Answer
→ Click Stop
→ Click Submit
```

the intended interaction is:

```text
Speak
→ Stop speaking
→ Silence detected
→ Automatically submit
```

This is one of the primary voice-engineering aspects of the project.

---

### 7. Speech-to-Text

Candidate responses are transcribed using:

**Groq Whisper — `whisper-large-v3-turbo`**

The transcription becomes the input for the answer-evaluation and interview-orchestration pipeline.

---

### 8. AI Answer Evaluation

The candidate's response is analyzed by the LLM.

The system can evaluate aspects such as:

* Technical correctness
* Relevance
* Completeness
* Communication
* Problem solving
* Job relevance

The evaluation is also used to determine the direction of the next question.

---

### 9. Rime Text-to-Speech

**Rime** provides the primary spoken output of the interviewer.

The LLM generates the question as text:

```text
LLM
 ↓
Next Interview Question
 ↓
Rime TTS
 ↓
Audio
 ↓
Candidate
```

Rime is therefore part of the core interview loop rather than being used only for a welcome message or optional playback.

---

### 10. Final Interview Report

After the interview, VoiceRecruit generates an assessment containing metrics such as:

```text
Technical Knowledge
Communication
Problem Solving
Grammar
Job Fit
Confidence
Overall Score
```

It can also provide:

* Strengths
* Areas for improvement
* Interview observations
* Speaking statistics
* Filler-word usage
* Speaking pace
* Recommended preparation areas

---

# Technology Stack

## Frontend

* React
* Vite
* JavaScript
* Web Audio API
* MediaRecorder API
* Browser microphone APIs

## Backend

* Python
* FastAPI
* Uvicorn
* LangChain
* Python-dotenv

## AI / Speech

### Large Language Model

**Groq**

Current configured model:

```text
openai/gpt-oss-120b
```

The model is responsible for:

* Resume/JD analysis
* Question generation
* Answer evaluation
* Follow-up question generation
* Final report generation

### Speech Recognition

**Groq Whisper**

```text
whisper-large-v3-turbo
```

Used for converting candidate speech into text.

### Text-to-Speech

**Rime**

Rime provides the primary spoken output of the interviewer.

---

# System Architecture

```text
                    ┌──────────────────────┐
                    │     Candidate        │
                    │ Resume + Job Desc.   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    React Frontend    │
                    │                      │
                    │ Upload / Interview   │
                    │ Microphone / UI      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     FastAPI          │
                    │      Backend         │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
      ┌────────────┐    ┌────────────┐    ┌────────────┐
      │   Groq     │    │   Groq     │    │   Rime     │
      │    LLM     │    │  Whisper   │    │    TTS     │
      └────────────┘    └────────────┘    └────────────┘
             │                 │                 │
             │                 ▼                 │
             │          Candidate Answer        │
             │                 │                 │
             └────────────┬────┘                 │
                          ▼                      │
                 ┌─────────────────┐             │
                 │ Answer          │             │
                 │ Evaluation      │             │
                 └────────┬────────┘             │
                          │                      │
                          ▼                      │
                 ┌─────────────────┐             │
                 │ Next Question   │─────────────┘
                 │ Generation      │
                 └─────────────────┘
```

---

# Interview Flow

### Step 1 — Upload

The candidate uploads:

```text
Resume
+
Job Description
```

### Step 2 — Analyze

The backend extracts the document text and sends the relevant information to the LLM.

The system identifies:

* Candidate skills
* Candidate projects
* Relevant experience
* Job requirements
* Skill overlap
* Potential skill gaps

### Step 3 — Start Interview

The system generates the first question.

Rime converts the question into speech.

### Step 4 — Candidate Answers

The candidate answers through the microphone.

### Step 5 — Automatic End-of-Turn Detection

The frontend monitors the audio signal.

When the candidate stops speaking for the configured silence interval, the recording is automatically submitted.

### Step 6 — Transcription

Groq Whisper converts the audio into text.

### Step 7 — Evaluation

The LLM evaluates the candidate's answer.

### Step 8 — Adaptive Question

The system generates the next question based on:

```text
Resume
+
Job Description
+
Previous Questions
+
Candidate Answers
+
Previous Evaluation
```

### Step 9 — Rime Response

The new question is converted into speech through Rime.

The cycle repeats until the interview is completed.

### Step 10 — Final Assessment

The system generates the final interview report.

---

# Voice Engineering Focus

The primary voice challenge addressed by VoiceRecruit is **conversational turn handling**.

A conventional voice application might require the user to manually control every turn:

```text
Press Start
→ Speak
→ Press Stop
→ Press Submit
→ Wait
→ Press Play
```

VoiceRecruit is designed to reduce this interaction overhead:

```text
Rime asks
     ↓
Candidate speaks
     ↓
Silence detected automatically
     ↓
Audio submitted
     ↓
STT
     ↓
LLM reasoning
     ↓
Rime asks next question
```

This is important because the candidate should be able to focus on answering interview questions rather than operating the interface.

---

# Example Interview

### Resume

```text
Python
FastAPI
PostgreSQL
Docker
LangChain

Project:
AI-powered document analysis platform
```

### Job Description

```text
Backend Engineer

Requirements:
Python
FastAPI
PostgreSQL
Docker
AWS
Kubernetes
System Design
```

### AI Interview

**Interviewer:**

> "I noticed that you built an AI-powered document analysis platform using FastAPI. Can you explain the backend architecture?"

**Candidate answers.**

The system transcribes and evaluates the answer.

**Interviewer:**

> "You mentioned using FastAPI for the API layer. How would you redesign your architecture if the application needed to support ten thousand concurrent users?"

The next question is therefore influenced by the previous answer.

---

# Project Structure

```text
VoiceRecruit/
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── ...
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── ...
│
├── demo/
│   └── demo.mp4
│
├── README.md
├── RIME_EVIDENCE.md
├── .env.example
└── .gitignore
```

---

# Installation

## Prerequisites

Make sure the following are installed:

* Python 3.10+
* Node.js
* npm
* Git

You also need API credentials for:

* Groq
* Rime

---

# Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
RIME_API_KEY=your_rime_api_key

GROQ_LLM_MODEL=openai/gpt-oss-120b
```

Start the backend:

```bash
python -m uvicorn main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

---

# Frontend Setup

Navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

If that port is occupied, Vite may automatically select another port.

---

# Environment Variables

Create `.env` locally:

```env
GROQ_API_KEY=your_groq_api_key
RIME_API_KEY=your_rime_api_key
GROQ_LLM_MODEL=openai/gpt-oss-120b
```

**Never commit the `.env` file.**

Use `.env.example` for repository configuration:

```env
GROQ_API_KEY=your_groq_api_key_here
RIME_API_KEY=your_rime_api_key_here
GROQ_LLM_MODEL=openai/gpt-oss-120b
```

---

# API Endpoints

The backend exposes endpoints for the major interview operations.

```text
GET  /
GET  /health

POST /analyze
POST /start-interview
POST /transcribe
POST /process-answer
POST /tts

GET  /interview/{interview_id}
GET/POST /interview/{interview_id}/report
```

The exact report method should match the implementation deployed in the final repository.

---

# Security

API credentials are kept on the backend and are not exposed to the frontend.

Sensitive configuration should be provided through environment variables.

The repository must never contain:

```text
.env
API keys
Rime credentials
Groq credentials
Private tokens
```

---

# Failure Handling

VoiceRecruit is designed to handle dependency and input failures gracefully.

Potential failure conditions include:

* Microphone permission denied
* Empty audio
* Speech recognition failure
* LLM request failure
* Rime synthesis failure
* Network interruption
* Invalid document
* Unsupported file format

The application should communicate failures to the user rather than silently producing an incorrect interview state.

---

# Known Limitations

* Browser microphone quality depends on the user's device and environment.
* Network conditions can affect end-to-end response latency.
* Speech recognition accuracy can vary with accent, background noise, and microphone quality.
* Rime synthesis latency depends on network and service conditions.
* Browser speaker playback can potentially be captured by the microphone; headphones are recommended for cleaner audio capture.
* The quality of adaptive questioning depends on the quality of the resume, job description, transcript, and LLM response.
* Voice interruption handling may be limited depending on the final browser implementation.

---

# Evaluation Metrics

VoiceRecruit can evaluate both **interview performance** and **voice interaction characteristics**.

### Candidate Evaluation

```text
Technical Knowledge
Communication
Problem Solving
Grammar
Job Fit
Confidence
Overall Performance
```

### Voice Metrics

```text
Speaking Rate
Words Per Minute
Filler Words
Response Duration
Pause Duration
```

### System Metrics

For the voice-engineering evaluation, the system can measure:

```text
Speech End
    ↓
Audio Submission
    ↓
STT Completion
    ↓
LLM Completion
    ↓
Rime Response
    ↓
First Audible Output
```

The final submission should report **measured values from the shipped system**, rather than estimated or fabricated latency numbers.

---

# Rime Integration

Rime is used as the **primary spoken output** of VoiceRecruit.

The interviewer's generated questions are sent to Rime for speech synthesis before being played to the candidate.

The final submission should document the exact configuration used during the demo:

```text
Rime Model ID: <EXACT_MODEL_ID>
Speaker:       <EXACT_SPEAKER>
Language:      <EXACT_LANGUAGE>
Endpoint:      <EXACT_ENDPOINT>
Audio Format:  <EXACT_AUDIO_FORMAT>
Transport:     <EXACT_TRANSPORT>
```

These values should be updated to the exact production configuration used in the final demo.

---

# Reproducibility

A judge should be able to reproduce the core flow:

```text
1. Clone repository
2. Configure environment variables
3. Install backend dependencies
4. Install frontend dependencies
5. Start FastAPI
6. Start React application
7. Upload resume
8. Upload job description
9. Start interview
10. Answer through microphone
11. Observe automatic turn detection
12. Observe adaptive questioning
13. Observe Rime spoken output
14. End interview
15. View final report
```

---

# Hackathon Demonstration

The demonstration focuses on the following flow:

```text
Resume + JD
     ↓
AI Analysis
     ↓
Personalized Interview
     ↓
Natural Voice Interaction
     ↓
Automatic Turn Detection
     ↓
Adaptive Follow-up Questions
     ↓
Rime Voice Output
     ↓
Interview Assessment
```

The demo also includes a deliberate stress/failure scenario and measurements of the voice interaction path.

---

# Future Improvements

Potential future improvements include:

* Full-duplex interruption handling
* Streaming speech recognition
* Streaming Rime audio
* More advanced voice activity detection
* Multilingual interviews
* Accent-aware speech processing
* Real-time recruiter dashboard
* Interview history
* Candidate comparison
* Skill-gap recommendations
* ATS integration
* Interview difficulty adaptation
* Cloud deployment and scalable session management

---

# Team

**Project:** VoiceRecruit
**Hackathon:** Rime Hackathon
**Category:** Voice AI / AI Interviewing

---

# Conclusion

VoiceRecruit aims to move AI interview preparation from a static question-answer experience toward a **natural, adaptive voice conversation**.

The system combines resume understanding, job-description analysis, LLM reasoning, speech recognition, automatic turn detection, adaptive questioning, and Rime-powered speech synthesis into a single interview workflow.

The key idea is simple:

> **Upload your resume and a job description, and VoiceRecruit becomes your recruiter — interviewing you by voice, adapting its questions to your answers, and evaluating your job readiness.**

---

