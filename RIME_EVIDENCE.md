# Rime Evidence — VoiceRecruit

## 1. Hard Voice Problem

### Conversational Turn Handling

VoiceRecruit addresses the problem of making an AI interview feel like a natural voice conversation rather than a chatbot with optional audio playback.

In a conventional interview interface, the candidate may need to repeatedly press buttons to start, stop, submit, and play responses.

VoiceRecruit is designed to reduce this interaction overhead.

The intended voice interaction is:

Candidate listens to Rime
        ↓
Candidate answers naturally
        ↓
Candidate stops speaking
        ↓
Automatic silence detection
        ↓
Audio is submitted automatically
        ↓
Speech-to-text
        ↓
AI answer evaluation
        ↓
Adaptive follow-up question
        ↓
Rime speaks the next question

Rime is therefore part of the core interview loop and provides the
primary spoken output of the AI interviewer.

---

## 2. Hard Voice Claim

> VoiceRecruit can automatically detect the end of a candidate's
> spoken response, process the response, generate an adaptive
> follow-up question, and deliver the next question through Rime
> without requiring the candidate to manually submit every answer.

This capability is important because the product is designed to simulate
a recruiter-style spoken interview rather than a text chatbot with
voice playback.

---

## 3. Acceptance Test

### Test Name

Automatic Voice Turn Handling Test

### Preconditions

- VoiceRecruit frontend and backend are running locally.
- A valid Groq API key is configured.
- A valid Rime API key is configured.
- Browser microphone permission is enabled.
- Headphones or a quiet environment are recommended.
- A resume and job description are available.

### Test Procedure

1. Open the VoiceRecruit web application.
2. Upload a candidate resume.
3. Upload a target job description.
4. Start the interview.
5. Wait for the first question to be spoken through Rime.
6. Answer the question naturally using the microphone.
7. Do not manually press a submit button after answering.
8. Stop speaking.
9. Allow the configured silence-detection interval to expire.
10. Verify that the recording stops automatically.
11. Verify that the audio is sent for transcription.
12. Verify that the candidate's response is evaluated by the LLM.
13. Verify that a follow-up question is generated.
14. Verify that the follow-up question is spoken through Rime.
15. Verify that the next interview turn can begin.

### Acceptance Criteria

The test passes if:

- The candidate can answer without manually submitting the response.
- Silence after the candidate's speech triggers the next processing step.
- The response is transcribed successfully.
- The response is evaluated successfully.
- A follow-up question is generated.
- Rime speaks the generated question.
- The interview state remains consistent.

---

## 4. Normal Test Result

### Test Environment

Browser:
Chrome / Edge

Frontend:
React + Vite

Backend:
FastAPI + Python

Speech Recognition:
Groq Whisper (`whisper-large-v3-turbo`)

LLM:
Groq (`openai/gpt-oss-120b`)

TTS:
Rime

Microphone:
Local computer microphone

### Result

Status: PASS / FAIL

Replace the status above with the actual result from the final
submitted version.

Observed behavior:

- Rime successfully generated the interviewer question.
- Candidate speech was captured through the browser microphone.
- Silence detection ended the candidate's turn.
- Candidate audio was sent to the backend.
- Whisper generated the transcript.
- The LLM evaluated the response.
- The next question was generated adaptively.
- Rime generated the spoken follow-up question.

Only retain statements above that were actually observed during the
final test.

---

## 5. Stress Test

### Test Name

Long Candidate Response Test

### Purpose

The purpose of this test is to verify that the automatic turn-handling
pipeline continues to work when the candidate gives a longer,
multi-sentence response.

### Procedure

1. Start a normal interview.
2. Wait for a Rime-generated question.
3. Give a deliberately long spoken response of approximately
   20–30 seconds.
4. Stop speaking.
5. Do not press a manual submit button.
6. Wait for automatic silence detection.
7. Observe the complete processing pipeline.
8. Verify that the next question is generated and spoken.

### Expected Result

The system should:

```text
Long candidate response
        ↓
Speech capture
        ↓
Silence detection
        ↓
Audio submission
        ↓
Whisper transcription
        ↓
LLM evaluation
        ↓
Follow-up generation
        ↓
Rime TTS
        ↓
Next spoken question