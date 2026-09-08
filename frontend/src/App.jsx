import React from "react";
import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

function App() {
  const [screen, setScreen] = useState("home");

  const [resume, setResume] = useState(null);
  const [jobDescription, setJobDescription] = useState(null);

  const [candidate, setCandidate] = useState(null);
  const [job, setJob] = useState(null);

  const [interviewStarted, setInterviewStarted] = useState(false);
  const [interviewComplete, setInterviewComplete] = useState(false);

  // NEW: backend interview ID
  const [interviewId, setInterviewId] = useState(null);

  const [currentQuestion, setCurrentQuestion] = useState("");
  const [transcript, setTranscript] = useState("");
  const [conversation, setConversation] = useState([]);

  const [status, setStatus] = useState("Ready");
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isEnding, setIsEnding] = useState(false);

  const [report, setReport] = useState(null);

  const [error, setError] = useState("");

  const audioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  // ---------------------------------------------------------
  // Upload handlers
  // ---------------------------------------------------------

  const handleResume = (e) => {
    const file = e.target.files?.[0];

    if (!file) return;

    if (file.type !== "application/pdf") {
      setError("Please upload your resume as a PDF.");
      return;
    }

    setResume(file);
    setError("");
  };

  const handleJD = (e) => {
    const file = e.target.files?.[0];

    if (!file) return;

    if (
      file.type !== "application/pdf" &&
      !file.type.includes("text")
    ) {
      setError("Please upload a PDF or text job description.");
      return;
    }

    setJobDescription(file);
    setError("");
  };

  // ---------------------------------------------------------
  // Analyze resume + JD
  // ---------------------------------------------------------

  const analyzeCandidate = async () => {
    if (!resume || !jobDescription) {
      setError("Please upload both resume and job description.");
      return;
    }

    try {
      setError("");
      setStatus("Analyzing resume and job description...");

      const formData = new FormData();

      formData.append("resume", resume);
      formData.append("job_description", jobDescription);

      const response = await fetch(`${API}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Analysis failed");
      }

      const data = await response.json();

      setCandidate(data.candidate || {});
      setJob(data.job || {});

      setScreen("analysis");
      setStatus("Analysis complete");
    } catch (err) {
      console.error(err);

      setError(
        "Could not analyze the documents. Make sure the backend is running."
      );

      setStatus("Error");
    }
  };

  // ---------------------------------------------------------
  // Start interview
  // ---------------------------------------------------------

  const startInterview = async () => {
    try {
      setError("");

      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

      streamRef.current = stream;

      setInterviewStarted(true);
      setInterviewComplete(false);
      setScreen("interview");
      setStatus("Connecting to recruiter...");

      const response = await fetch(`${API}/start-interview`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          candidate,
          job,
        }),
      });

      if (!response.ok) {
        throw new Error("Interview could not start");
      }

      const data = await response.json();

      // IMPORTANT:
      // Store interview ID returned by backend
      setInterviewId(data.interview_id || data.id || null);

      const question =
        data.question ||
        "Hello. Let's begin your interview. Please introduce yourself.";

      setCurrentQuestion(question);

      setConversation([
        {
          type: "recruiter",
          text: question,
        },
      ]);

      if (data.audio) {
        await playAudio(data.audio);
      }

      setStatus("Listening");

      setTimeout(() => {
        startRecording();
      }, 400);
    } catch (err) {
      console.error(err);

      stopMicrophone();

      setError(
        "Microphone permission is required to start the interview."
      );

      setStatus("Microphone error");
    }
  };

  // ---------------------------------------------------------
  // Rime audio
  // ---------------------------------------------------------

  const playAudio = async (base64Audio) => {
    try {
      setIsSpeaking(true);
      setStatus("Recruiter speaking");

      const audioSrc =
        `data:audio/wav;base64,${base64Audio}`;

      if (audioRef.current) {
        audioRef.current.pause();
      }

      const audio = new Audio(audioSrc);

      audioRef.current = audio;

      await audio.play();

      await new Promise((resolve) => {
        audio.onended = resolve;
      });

      setIsSpeaking(false);
    } catch (err) {
      console.error("Audio playback error:", err);

      setIsSpeaking(false);
    }
  };

  // ---------------------------------------------------------
  // Start recording
  // ---------------------------------------------------------

  const startRecording = () => {
    if (!streamRef.current) return;

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      return;
    }

    // Don't start recording after user has ended interview
    if (!interviewStarted || interviewComplete || isEnding) {
      return;
    }

    chunksRef.current = [];

    let mimeType = "audio/webm";

    if (!MediaRecorder.isTypeSupported("audio/webm")) {
      mimeType = "";
    }

    const recorder = new MediaRecorder(
      streamRef.current,
      mimeType ? { mimeType } : undefined
    );

    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    recorder.onstop = async () => {
      // Don't process an answer if interview was manually ended
      if (isEnding) {
        return;
      }

      const blob = new Blob(chunksRef.current, {
        type: "audio/webm",
      });

      await processAnswer(blob);
    };

    recorder.start();

    setIsListening(true);
    setStatus("Listening");
  };

  // ---------------------------------------------------------
  // Stop recording
  // ---------------------------------------------------------

  const stopRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.stop();

      setIsListening(false);
      setStatus("Understanding your answer...");
    }
  };

  // ---------------------------------------------------------
  // Process answer
  // ---------------------------------------------------------

  const processAnswer = async (audioBlob) => {
    try {
      // Don't process anything after manual end
      if (isEnding || !interviewStarted) {
        return;
      }

      setIsProcessing(true);

      const formData = new FormData();

      formData.append(
        "file",
        audioBlob,
        "answer.webm"
      );

      // -----------------------------------------------------
      // Speech to text
      // -----------------------------------------------------

      const transcriptionResponse = await fetch(
        `${API}/transcribe`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!transcriptionResponse.ok) {
        throw new Error("Transcription failed");
      }

      const transcription =
        await transcriptionResponse.json();

      const userText = transcription.text || "";

      // Empty answer
      if (!userText.trim()) {
        setIsProcessing(false);
        setStatus("Listening");

        setTimeout(() => {
          if (
            interviewStarted &&
            !interviewComplete &&
            !isEnding
          ) {
            startRecording();
          }
        }, 500);

        return;
      }

      setTranscript(userText);

      // Save answer locally
      setConversation((prev) => [
        ...prev,
        {
          type: "candidate",
          text: userText,
        },
      ]);

      // -----------------------------------------------------
      // Process answer
      // -----------------------------------------------------

      const response = await fetch(
        `${API}/process-answer`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            interview_id: interviewId,
            transcript: userText,
            current_question: currentQuestion,
            candidate,
            job,
            conversation,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Answer processing failed"
        );
      }

      const data = await response.json();

      // -----------------------------------------------------
      // Interview completed automatically
      // -----------------------------------------------------

      if (data.complete) {
        finishInterview(data);
        return;
      }

      // -----------------------------------------------------
      // Next question
      // -----------------------------------------------------

      const nextQuestion =
        data.question ||
        data.next_question ||
        "Thank you. Let's move to the next question.";

      setCurrentQuestion(nextQuestion);

      setConversation((prev) => [
        ...prev,
        {
          type: "recruiter",
          text: nextQuestion,
        },
      ]);

      if (data.audio) {
        await playAudio(data.audio);
      }

      setIsProcessing(false);
      setStatus("Listening");

      // Automatically listen again
      setTimeout(() => {
        if (
          interviewStarted &&
          !interviewComplete &&
          !isEnding
        ) {
          startRecording();
        }
      }, 400);
    } catch (err) {
      console.error(err);

      setError(
        "There was a problem processing your answer."
      );

      setIsProcessing(false);

      if (!isEnding) {
        setStatus("Listening");

        setTimeout(() => {
          if (
            interviewStarted &&
            !interviewComplete &&
            !isEnding
          ) {
            startRecording();
          }
        }, 700);
      }
    }
  };

  // ---------------------------------------------------------
  // FINISH INTERVIEW - automatic
  // ---------------------------------------------------------

  const finishInterview = (data) => {
    setInterviewComplete(true);
    setInterviewStarted(false);
    setIsEnding(false);

    setReport(data.report || null);

    setStatus("Interview complete");

    stopMicrophone();

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    setScreen("report");
  };

  // ---------------------------------------------------------
  // NEW: MANUALLY END INTERVIEW
  // ---------------------------------------------------------

  const handleEndInterview = async () => {
    if (isEnding) return;

    const confirmed = window.confirm(
      "Are you sure you want to end the interview?\n\nYour answers so far will be used to generate your recruiter report."
    );

    if (!confirmed) return;

    try {
      setIsEnding(true);
      setStatus("Ending interview...");
      setError("");

      // Stop audio immediately
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }

      // Stop microphone immediately
      stopMicrophone();

      setInterviewStarted(false);

      // -----------------------------------------------------
      // If we have an interview ID, ask backend for report
      // -----------------------------------------------------

      if (interviewId) {
        const response = await fetch(
          `${API}/interview/${interviewId}/report`,
          {
            method: "POST",
          }
        );

        if (!response.ok) {
          throw new Error(
            "Could not generate final report"
          );
        }

        const data = await response.json();

        setReport(
          data.report ||
          data ||
          null
        );
      } else {
        // Fallback if backend didn't return ID
        console.warn(
          "No interview_id returned by backend."
        );

        setReport({
          overall_score: 0,
          technical_knowledge: 0,
          problem_solving: 0,
          communication: 0,
          grammar: 0,
          job_fit: 0,
          confidence: 0,
          verdict: "Interview ended early",
          summary:
            "The interview was manually ended before a complete interview report could be generated.",
          strengths: [],
          improvements: [
            "Complete more interview questions for a more accurate assessment.",
          ],
        });
      }

      setInterviewComplete(true);
      setScreen("report");
      setStatus("Interview ended");
    } catch (err) {
      console.error(
        "End interview error:",
        err
      );

      setError(
        "Interview ended, but the final report could not be generated."
      );

      // Still show report screen
      setInterviewComplete(true);
      setScreen("report");
      setStatus("Interview ended");
    } finally {
      setIsEnding(false);
    }
  };

  // ---------------------------------------------------------
  // Stop microphone
  // ---------------------------------------------------------

  const stopMicrophone = () => {
    if (mediaRecorderRef.current) {
      if (
        mediaRecorderRef.current.state ===
        "recording"
      ) {
        mediaRecorderRef.current.stop();
      }

      mediaRecorderRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current
        .getTracks()
        .forEach((track) => track.stop());

      streamRef.current = null;
    }

    setIsListening(false);
  };

  // ---------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------

  useEffect(() => {
    return () => {
      stopMicrophone();

      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  // ---------------------------------------------------------
  // Reset
  // ---------------------------------------------------------

  const resetApp = () => {
    stopMicrophone();

    if (audioRef.current) {
      audioRef.current.pause();
    }

    setResume(null);
    setJobDescription(null);
    setCandidate(null);
    setJob(null);

    setInterviewStarted(false);
    setInterviewComplete(false);

    setInterviewId(null);

    setCurrentQuestion("");
    setTranscript("");
    setConversation([]);

    setReport(null);
    setError("");
    setStatus("Ready");
    setIsEnding(false);

    setScreen("home");
  };

  // =========================================================
  // HOME SCREEN
  // =========================================================

  if (screen === "home") {
    return (
      <div className="app">
        <Navbar />

        <main className="hero">
          <div className="hero-content">

            <div className="badge">
              <span className="badge-dot"></span>
              AI VOICE RECRUITER
            </div>

            <h1>
              Your next interview,
              <br />
              <span>but actually intelligent.</span>
            </h1>

            <p className="hero-subtitle">
              Upload your resume and the job description.
              VoiceRecruit studies both and conducts a
              personalized voice interview that adapts to
              your answers.
            </p>

            <div className="upload-grid">

              <UploadCard
                title="Your Resume"
                description="Upload your latest resume"
                file={resume}
                accept=".pdf"
                onChange={handleResume}
                icon="📄"
              />

              <UploadCard
                title="Job Description"
                description="Upload the role you're applying for"
                file={jobDescription}
                accept=".pdf,.txt"
                onChange={handleJD}
                icon="💼"
              />

            </div>

            {error && (
              <div className="error-message">
                ⚠️ {error}
              </div>
            )}

            <button
              className="primary-btn"
              disabled={
                !resume ||
                !jobDescription
              }
              onClick={analyzeCandidate}
            >
              Analyze & Prepare Interview
              <span>→</span>
            </button>

            <div className="trust-row">
              <span>
                🔒 Your documents stay private
              </span>

              <span>
                ⚡ Personalized questions
              </span>

              <span>
                🎙️ Natural voice interview
              </span>
            </div>

          </div>
        </main>
      </div>
    );
  }

  // =========================================================
  // ANALYSIS SCREEN
  // =========================================================

  if (screen === "analysis") {
    return (
      <div className="app">
        <Navbar />

        <main className="dashboard">

          <div className="page-heading">
            <div>

              <div className="eyebrow">
                CANDIDATE ANALYSIS
              </div>

              <h2>
                You're ready for the interview.
              </h2>

              <p>
                We've compared your resume with the job
                requirements and prepared a personalized
                interview.
              </p>

            </div>
          </div>

          <div className="analysis-grid">

            <section className="glass-card candidate-card">

              <div className="card-header">
                <span>👤</span>

                <div>
                  <h3>
                    Candidate Profile
                  </h3>

                  <p>
                    Extracted from your resume
                  </p>
                </div>
              </div>

              <div className="candidate-name">
                {candidate?.name ||
                  "Candidate"}
              </div>

              <div className="skill-list">

                {(candidate?.skills || [
                  "Python",
                  "FastAPI",
                  "React",
                  "SQL",
                ]).map(
                  (skill, index) => (
                    <span key={index}>
                      {skill}
                    </span>
                  )
                )}

              </div>

            </section>

            <section className="glass-card">

              <div className="card-header">
                <span>🎯</span>

                <div>
                  <h3>
                    Job Requirements
                  </h3>

                  <p>
                    What the recruiter is looking for
                  </p>
                </div>
              </div>

              <div className="requirement-list">

                {(job?.skills || [
                  "Backend Development",
                  "Python",
                  "FastAPI",
                  "REST APIs",
                  "SQL",
                  "Cloud",
                ]).map(
                  (skill, index) => (
                    <div
                      className="requirement"
                      key={index}
                    >
                      <span>✓</span>
                      {skill}
                    </div>
                  )
                )}

              </div>

            </section>

          </div>

          <section className="glass-card interview-preview">

            <div>

              <div className="card-header">
                <span>🧠</span>

                <div>
                  <h3>
                    Interview Strategy
                  </h3>

                  <p>
                    Questions will adapt based on your
                    answers.
                  </p>
                </div>
              </div>

              <div className="strategy-grid">

                <Strategy
                  number="01"
                  title="Resume Deep Dive"
                  text="Questions about your projects and experience."
                />

                <Strategy
                  number="02"
                  title="Technical Assessment"
                  text="Role-specific technical questions."
                />

                <Strategy
                  number="03"
                  title="Adaptive Follow-ups"
                  text="Deeper questions based on your answers."
                />

                <Strategy
                  number="04"
                  title="Communication"
                  text="Grammar, clarity and speaking quality."
                />

              </div>

            </div>

            <button
              className="primary-btn large"
              onClick={startInterview}
            >
              <span className="mic-icon">
                🎙️
              </span>

              Start Voice Interview
            </button>

          </section>

        </main>
      </div>
    );
  }

  // =========================================================
  // INTERVIEW SCREEN
  // =========================================================

  if (screen === "interview") {
    return (
      <div className="app interview-page">

        <Navbar />

        <main className="interview-layout">

          <section className="interview-main">

            <div className="interview-top">

              <div>

                <div className="eyebrow">
                  LIVE INTERVIEW
                </div>

                <h2>
                  VoiceRecruit
                </h2>

              </div>

              <div className="live-indicator">
                <span></span>
                LIVE
              </div>

            </div>

            <div className="recruiter-area">

              <div
                className={`recruiter-orb ${
                  isSpeaking
                    ? "speaking"
                    : ""
                } ${
                  isListening
                    ? "listening"
                    : ""
                }`}
              >
                <div className="orb-inner">
                  🎙️
                </div>
              </div>

              <div className="status-text">
                {status}
              </div>

              <div className="question-card">

                <div className="question-label">
                  RECRUITER
                </div>

                <h3>
                  {currentQuestion ||
                    "Preparing your question..."}
                </h3>

              </div>

              <div className="voice-status">

                {isListening && (
                  <>
                    <div className="wave">

                      <span></span>
                      <span></span>
                      <span></span>
                      <span></span>
                      <span></span>

                    </div>

                    <p>
                      Listening to your answer...
                    </p>
                  </>
                )}

                {isProcessing && (
                  <p>
                    <span className="spinner"></span>
                    Evaluating your response...
                  </p>
                )}

                {isSpeaking && (
                  <p>
                    Recruiter is speaking...
                  </p>
                )}

              </div>

              <button
                className={`record-button ${
                  isListening
                    ? "active"
                    : ""
                }`}
                onClick={() => {

                  if (isListening) {
                    stopRecording();
                  } else if (
                    !isProcessing &&
                    !isSpeaking &&
                    !isEnding
                  ) {
                    startRecording();
                  }

                }}
                disabled={
                  isProcessing ||
                  isSpeaking ||
                  isEnding
                }
              >
                <span>🎤</span>
              </button>

              <p className="record-hint">
                {isListening
                  ? "Tap to finish your answer"
                  : "Speak naturally"}
              </p>

              {/* =================================================
                  NEW END INTERVIEW BUTTON
                 ================================================= */}

              <button
                className="end-interview-btn"
                onClick={handleEndInterview}
                disabled={isEnding}
              >
                {isEnding ? (
                  <>
                    <span className="spinner"></span>
                    Ending Interview...
                  </>
                ) : (
                  <>
                    🔴 End Interview
                  </>
                )}
              </button>

              <p className="end-interview-hint">
                You can end the interview at any time.
              </p>

              {error && (
                <div className="error-message">
                  ⚠️ {error}
                </div>
              )}

            </div>

          </section>

          <aside className="conversation-panel">

            <div className="panel-header">

              <div>

                <h3>
                  Interview
                </h3>

                <p>
                  Personalized for your application
                </p>

              </div>

              <div className="question-count">

                {conversation.filter(
                  (x) =>
                    x.type ===
                    "recruiter"
                ).length}

              </div>

            </div>

            <div className="conversation">

              {conversation.map(
                (message, index) => (
                  <div
                    key={index}
                    className={`message ${
                      message.type
                    }`}
                  >

                    <div className="message-role">

                      {message.type ===
                      "recruiter"
                        ? "RECRUITER"
                        : "YOU"}

                    </div>

                    <p>
                      {message.text}
                    </p>

                  </div>
                )
              )}

            </div>

            {transcript && (
              <div className="latest-answer">

                <div className="message-role">
                  LATEST ANSWER
                </div>

                <p>
                  {transcript}
                </p>

              </div>
            )}

          </aside>

        </main>

      </div>
    );
  }

  // =========================================================
  // REPORT SCREEN
  // =========================================================

  if (screen === "report") {
    return (
      <div className="app">

        <Navbar />

        <main className="report-page">

          <div className="report-heading">

            <div className="eyebrow">
              INTERVIEW COMPLETE
            </div>

            <h2>
              Your Recruiter Report
            </h2>

            <p>
              Here's how you performed across technical
              knowledge, communication and job fit.
            </p>

          </div>

          <div className="overall-card">

            <div>

              <div className="small-label">
                OVERALL SCORE
              </div>

              <div className="overall-score">

                {report?.overall_score ?? 0}

                <span>
                  /100
                </span>

              </div>

            </div>

            <div className="verdict">

              <span>
                RECRUITER VERDICT
              </span>

              <strong>
                {report?.verdict ||
                  "Interview ended"}
              </strong>

              <p>
                {report?.summary ||
                  "Your interview has been completed."}
              </p>

            </div>

          </div>

          <div className="metrics-grid">

            <Metric
              title="Technical Knowledge"
              value={
                report?.technical_knowledge ?? 0
              }
              icon="🧠"
            />

            <Metric
              title="Problem Solving"
              value={
                report?.problem_solving ?? 0
              }
              icon="💡"
            />

            <Metric
              title="Communication"
              value={
                report?.communication ?? 0
              }
              icon="💬"
            />

            <Metric
              title="Grammar"
              value={
                report?.grammar ?? 0
              }
              icon="✍️"
            />

            <Metric
              title="Job Fit"
              value={
                report?.job_fit ?? 0
              }
              icon="🎯"
            />

            <Metric
              title="Confidence"
              value={
                report?.confidence ?? 0
              }
              icon="🎙️"
            />

          </div>

          <div className="report-grid">

            <section className="glass-card">

              <div className="card-header">

                <span>💪</span>

                <div>

                  <h3>
                    Strengths
                  </h3>

                  <p>
                    What you did well
                  </p>

                </div>

              </div>

              <div className="feedback-list positive">

                {(report?.strengths || [
                  "Complete more questions to receive detailed feedback",
                ]).map(
                  (item, index) => (
                    <div key={index}>
                      <span>✓</span>
                      {item}
                    </div>
                  )
                )}

              </div>

            </section>

            <section className="glass-card">

              <div className="card-header">

                <span>📈</span>

                <div>

                  <h3>
                    Areas to Improve
                  </h3>

                  <p>
                    Where you can get better
                  </p>

                </div>

              </div>

              <div className="feedback-list improvement">

                {(report?.improvements || [
                  "Complete more interview questions for a more accurate assessment.",
                ]).map(
                  (item, index) => (
                    <div key={index}>
                      <span>!</span>
                      {item}
                    </div>
                  )
                )}

              </div>

            </section>

          </div>

          <section className="glass-card detailed-analysis">

            <div className="card-header">

              <span>📊</span>

              <div>

                <h3>
                  Communication Analysis
                </h3>

                <p>
                  How effectively you communicated
                </p>

              </div>

            </div>

            <div className="communication-bars">

              <ScoreBar
                label="Grammar"
                value={
                  report?.grammar ?? 0
                }
              />

              <ScoreBar
                label="Clarity"
                value={
                  report?.clarity ?? 0
                }
              />

              <ScoreBar
                label="Vocabulary"
                value={
                  report?.vocabulary ?? 0
                }
              />

              <ScoreBar
                label="Professional Tone"
                value={
                  report?.professional_tone ?? 0
                }
              />

              <ScoreBar
                label="Answer Structure"
                value={
                  report?.answer_structure ?? 0
                }
              />

            </div>

          </section>

          <section className="glass-card speech-analysis">

            <div className="card-header">

              <span>🎙️</span>

              <div>

                <h3>
                  Voice Analysis
                </h3>

                <p>
                  Insights from your spoken responses
                </p>

              </div>

            </div>

            <div className="speech-stats">

              <SpeechStat
                value={
                  report?.speaking_pace ?? "—"
                }
                unit="WPM"
                label="Speaking Pace"
              />

              <SpeechStat
                value={
                  report?.filler_words ?? "—"
                }
                unit=""
                label="Filler Words"
              />

              <SpeechStat
                value={
                  report?.long_pauses ?? "—"
                }
                unit=""
                label="Long Pauses"
              />

              <SpeechStat
                value={
                  report?.answer_completion ?? "—"
                }
                unit="%"
                label="Answer Completion"
              />

            </div>

          </section>

          <div className="report-actions">

            <button
              className="secondary-btn"
              onClick={resetApp}
            >
              ← Start New Interview
            </button>

            <button
              className="primary-btn"
              onClick={() =>
                window.print()
              }
            >
              Download Report
              <span>↓</span>
            </button>

          </div>

        </main>

      </div>
    );
  }

  return null;
}

// =========================================================
// COMPONENTS
// =========================================================

function Navbar() {
  return (
    <header className="navbar">

      <div className="logo">

        <div className="logo-mark">
          V
        </div>

        <span>
          VoiceRecruit
        </span>

      </div>

      <div className="nav-right">
        <span>
          AI-Powered Recruitment
        </span>
      </div>

    </header>
  );
}

function UploadCard({
  title,
  description,
  file,
  accept,
  onChange,
  icon,
}) {
  return (
    <label className="upload-card">

      <input
        type="file"
        accept={accept}
        onChange={onChange}
        hidden
      />

      <div className="upload-icon">
        {file ? "✓" : icon}
      </div>

      <div className="upload-info">

        <h3>
          {title}
        </h3>

        <p>
          {file
            ? file.name
            : description}
        </p>

      </div>

      <span className="upload-arrow">
        {file ? "✓" : "+"}
      </span>

    </label>
  );
}

function Strategy({
  number,
  title,
  text,
}) {
  return (
    <div className="strategy-item">

      <span>
        {number}
      </span>

      <div>

        <strong>
          {title}
        </strong>

        <p>
          {text}
        </p>

      </div>

    </div>
  );
}

function Metric({
  title,
  value,
  icon,
}) {
  const safeValue = Math.max(
    0,
    Math.min(100, Number(value) || 0)
  );

  return (
    <div className="metric-card">

      <div className="metric-icon">
        {icon}
      </div>

      <div className="metric-title">
        {title}
      </div>

      <div className="metric-value">

        {safeValue}

        <span>
          /100
        </span>

      </div>

      <div className="metric-progress">

        <div
          style={{
            width: `${safeValue}%`,
          }}
        />

      </div>

    </div>
  );
}

function ScoreBar({
  label,
  value,
}) {
  const safeValue = Math.max(
    0,
    Math.min(100, Number(value) || 0)
  );

  return (
    <div className="score-row">

      <div className="score-label">

        <span>
          {label}
        </span>

        <strong>
          {safeValue}
        </strong>

      </div>

      <div className="score-track">

        <div
          style={{
            width: `${safeValue}%`,
          }}
        />

      </div>

    </div>
  );
}

function SpeechStat({
  value,
  unit,
  label,
}) {
  return (
    <div className="speech-stat">

      <strong>

        {value}

        <small>
          {unit}
        </small>

      </strong>

      <span>
        {label}
      </span>

    </div>
  );
}

export default App;