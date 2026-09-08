import React, { useRef, useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const initialForm = {
  name: "",
  dob: "",
  phone: "",
  email: "",
  application_id: "",
  pin: "",
  address: "",
  city: "",
  state: "",
  paragraph: "",
};

const fieldLabels = {
  name: "Full Name",
  dob: "Date of Birth",
  phone: "Phone Number",
  email: "Email Address",
  application_id: "Application ID",
  pin: "PIN Code",
  address: "Address",
  city: "City",
  state: "State",
  paragraph: "Additional Information",
};

function App() {
  const [form, setForm] = useState(initialForm);
  const [transcript, setTranscript] = useState("");
  const [message, setMessage] = useState("Ready to listen.");
  const [status, setStatus] = useState("idle");
  const [isRecording, setIsRecording] = useState(false);

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioChunksRef = useRef([]);

  // =====================================================
  // PROCESS TRANSCRIPT → QWEN → JSON
  // =====================================================

  const processVoice = async (transcriptText) => {
    try {
      setStatus("processing");
      setMessage("AI is understanding your information...");

      const response = await fetch(
        `${API_BASE_URL}/process-voice`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            transcript: transcriptText,
          }),
        }
      );

      const result = await response.json();

      console.log("Qwen response:", result);

      if (!response.ok) {
        throw new Error(
          result.detail ||
            result.error ||
            `Backend error: ${response.status}`
        );
      }

      if (!result.success) {
        throw new Error(
          result.error ||
            result.message ||
            "AI processing failed."
        );
      }

      setForm((previousForm) => ({
        ...previousForm,
        ...result.data,
      }));

      setMessage("✓ Form updated successfully.");
      setStatus("success");

    } catch (error) {
      console.error("Processing error:", error);

      setMessage(
        error.message ||
          "Could not process the transcript."
      );

      setStatus("error");
    }
  };

  // =====================================================
  // AUDIO → GROQ WHISPER → TRANSCRIPT
  // =====================================================

  const uploadRecording = async (audioBlob) => {
    try {
      setStatus("transcribing");
      setMessage("Transcribing your voice...");

      const formData = new FormData();

      // IMPORTANT:
      // Backend expects "file", NOT "audio"
      formData.append(
        "file",
        audioBlob,
        "recording.webm"
      );

      const response = await fetch(
        `${API_BASE_URL}/transcribe`,
        {
          method: "POST",
          body: formData,
        }
      );

      const result = await response.json();

      console.log("Transcription response:", result);

      if (!response.ok) {
        throw new Error(
          result.detail ||
            result.error ||
            `Transcription error: ${response.status}`
        );
      }

      if (!result.success) {
        throw new Error(
          result.error ||
            "Transcription failed."
        );
      }

      const transcriptText =
        result.transcript?.text || "";

      if (!transcriptText.trim()) {
        throw new Error(
          "No speech was detected. Please try again."
        );
      }

      setTranscript(transcriptText);

      // Send transcript to Qwen
      await processVoice(transcriptText);

    } catch (error) {
      console.error(
        "Upload/transcription error:",
        error
      );

      setMessage(
        error.message ||
          "Could not process your recording."
      );

      setStatus("error");
    }
  };

  // =====================================================
  // START RECORDING
  // =====================================================

  const startRecording = async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          "Microphone access is not supported by this browser."
        );
      }

      if (!window.MediaRecorder) {
        throw new Error(
          "MediaRecorder is not supported by this browser."
        );
      }

      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

      streamRef.current = stream;
      audioChunksRef.current = [];

      const recorder = new MediaRecorder(stream);

      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(
            event.data
          );
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(
          audioChunksRef.current,
          {
            type: "audio/webm",
          }
        );

        // Stop microphone
        if (streamRef.current) {
          streamRef.current
            .getTracks()
            .forEach((track) => track.stop());
        }

        streamRef.current = null;

        await uploadRecording(audioBlob);
      };

      recorder.start();

      setIsRecording(true);
      setStatus("recording");
      setMessage("Listening... speak naturally.");

    } catch (error) {
      console.error(
        "Microphone error:",
        error
      );

      setMessage(
        error.message ||
          "Could not access your microphone."
      );

      setStatus("error");
    }
  };

  // =====================================================
  // STOP RECORDING
  // =====================================================

  const stopRecording = () => {
    if (
      recorderRef.current &&
      recorderRef.current.state !== "inactive"
    ) {
      recorderRef.current.stop();
    }

    setIsRecording(false);
    setMessage("Processing your recording...");
  };

  // =====================================================
  // MAIN MICROPHONE
  // =====================================================

  const handleSpeak = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // =====================================================
  // MANUAL FIELD EDIT
  // =====================================================

  const handleChange = (field, value) => {
    setForm((previousForm) => ({
      ...previousForm,
      [field]: value,
    }));
  };

  // =====================================================
  // CLEAR
  // =====================================================

  const clearForm = () => {
    setForm(initialForm);
    setTranscript("");
    setMessage("Ready to listen.");
    setStatus("idle");
  };

  // =====================================================
  // SUBMIT
  // =====================================================

  const handleSubmit = (event) => {
    event.preventDefault();

    console.log(
      "Final Form:",
      form
    );

    setMessage(
      "✓ Form submitted successfully."
    );

    setStatus("success");
  };

  // =====================================================
  // PROGRESS
  // =====================================================

  const filledFields = Object.values(form).filter(
    (value) =>
      value &&
      value.toString().trim() !== ""
  ).length;

  const progress =
    (filledFields / Object.keys(form).length) * 100;

  // =====================================================
  // STATUS TEXT
  // =====================================================

  const getStatusText = () => {
    switch (status) {
      case "recording":
        return "Listening...";
      case "transcribing":
        return "Transcribing...";
      case "processing":
        return "AI processing...";
      case "success":
        return "Ready";
      case "error":
        return "Something went wrong";
      default:
        return "Ready";
    }
  };

  // =====================================================
  // UI
  // =====================================================

  return (
    <div className="app-shell">

      {/* =================================================
          HEADER
      ================================================= */}

      <header className="topbar">

        <div className="brand-row">

          <div className="brand-icon">
            FV
          </div>

          <div>
            <h1>FormVoice AI</h1>

            <p>
              Intelligent voice-powered form filling
            </p>
          </div>

        </div>

        <div className="ready-badge">

          <span className="ready-dot"></span>

          {getStatusText()}

        </div>

      </header>


      {/* =================================================
          MAIN DASHBOARD
      ================================================= */}

      <main className="dashboard">

        {/* =================================================
            LEFT PANEL
        ================================================= */}

        <section className="left-panel">

          {/* VOICE CARD */}

          <div className="voice-card">

            <div className="eyebrow">
              VOICE INPUT
            </div>

            <h2>
              Speak. We'll handle the rest.
            </h2>

            <p>
              Tell FormVoice your information naturally.
              AI will transcribe your speech and
              automatically organize it into the form.
            </p>


            {/* MICROPHONE ORB */}

            <div
              className={
                isRecording
                  ? "voice-orb listening"
                  : "voice-orb"
              }
            >

              <div className="voice-ring ring-one"></div>
              <div className="voice-ring ring-two"></div>
              <div className="voice-ring ring-three"></div>

              <div className="mic-symbol">
                🎤
              </div>

            </div>


            {/* MAIN BUTTON */}

            <button
              className={
                isRecording
                  ? "main-mic-button recording"
                  : "main-mic-button"
              }
              onClick={handleSpeak}
            >

              {isRecording
                ? "⏹ Stop Recording"
                : "🎤 Start Speaking"}

            </button>


            {/* WAVEFORM */}

            {isRecording && (
              <div className="wave-bars">

                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>

              </div>
            )}

          </div>


          {/* AI ASSISTANT CARD */}

          <div className="assistant-card">

            <div className="assistant-header">

              <div className="assistant-icon">
                ✨
              </div>

              <div>

                <span>
                  AI ASSISTANT
                </span>

                <strong>
                  Qwen Intelligence
                </strong>

              </div>

            </div>

            <p>
              Your speech is converted into structured
              information using AI instead of
              rule-based field extraction.
            </p>

          </div>


          {/* TRANSCRIPT CARD */}

          <div className="transcript-card">

            <div className="transcript-title">
              📝 Latest Transcript
            </div>

            <p>
              {transcript ||
                "Your latest voice transcription will appear here."}
            </p>

          </div>

        </section>


        {/* =================================================
            FORM PANEL
        ================================================= */}

        <section className="form-card">

          <div className="form-heading">

            <div>

              <div className="eyebrow">
                SMART FORM
              </div>

              <h2>
                Your Information
              </h2>

              <p>
                Review and edit anything before submitting.
              </p>

            </div>

            <div className="progress-count">
              {filledFields}/10
            </div>

          </div>


          {/* PROGRESS */}

          <div className="progress-track">

            <div
              className="progress-fill"
              style={{
                width: `${progress}%`,
              }}
            ></div>

          </div>

          <p className="progress-text">
            {filledFields === 0
              ? "Start speaking to fill your form"
              : `${filledFields} of 10 fields completed`}
          </p>


          {/* FORM */}

          <form onSubmit={handleSubmit}>

            <div className="form-grid">

              {/* NAME */}

              <div className="field-group">

                <label>
                  {fieldLabels.name}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) =>
                      handleChange(
                        "name",
                        e.target.value
                      )
                    }
                    placeholder="e.g. Anand Kumar"
                  />

                </div>

              </div>


              {/* DOB */}

              <div className="field-group">

                <label>
                  {fieldLabels.dob}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.dob}
                    onChange={(e) =>
                      handleChange(
                        "dob",
                        e.target.value
                      )
                    }
                    placeholder="DD/MM/YYYY"
                  />

                </div>

              </div>


              {/* PHONE */}

              <div className="field-group">

                <label>
                  {fieldLabels.phone}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) =>
                      handleChange(
                        "phone",
                        e.target.value
                      )
                    }
                    placeholder="9876543210"
                  />

                </div>

              </div>


              {/* EMAIL */}

              <div className="field-group">

                <label>
                  {fieldLabels.email}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) =>
                      handleChange(
                        "email",
                        e.target.value
                      )
                    }
                    placeholder="you@example.com"
                  />

                </div>

              </div>


              {/* APPLICATION ID */}

              <div className="field-group">

                <label>
                  {fieldLabels.application_id}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.application_id}
                    onChange={(e) =>
                      handleChange(
                        "application_id",
                        e.target.value
                      )
                    }
                    placeholder="ABX2047891"
                  />

                </div>

              </div>


              {/* PIN */}

              <div className="field-group">

                <label>
                  {fieldLabels.pin}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.pin}
                    onChange={(e) =>
                      handleChange(
                        "pin",
                        e.target.value
                      )
                    }
                    placeholder="411007"
                  />

                </div>

              </div>


              {/* ADDRESS */}

              <div className="field-group full-width">

                <label>
                  {fieldLabels.address}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.address}
                    onChange={(e) =>
                      handleChange(
                        "address",
                        e.target.value
                      )
                    }
                    placeholder="House number, street, area"
                  />

                </div>

              </div>


              {/* CITY */}

              <div className="field-group">

                <label>
                  {fieldLabels.city}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.city}
                    onChange={(e) =>
                      handleChange(
                        "city",
                        e.target.value
                      )
                    }
                    placeholder="Pune"
                  />

                </div>

              </div>


              {/* STATE */}

              <div className="field-group">

                <label>
                  {fieldLabels.state}
                </label>

                <div className="voice-input-wrapper">

                  <input
                    type="text"
                    value={form.state}
                    onChange={(e) =>
                      handleChange(
                        "state",
                        e.target.value
                      )
                    }
                    placeholder="Maharashtra"
                  />

                </div>

              </div>


              {/* PARAGRAPH */}

              <div className="field-group full-width">

                <label>
                  {fieldLabels.paragraph}
                </label>

                <div className="voice-input-wrapper">

                  <textarea
                    value={form.paragraph}
                    onChange={(e) =>
                      handleChange(
                        "paragraph",
                        e.target.value
                      )
                    }
                    placeholder="Any additional information..."
                    rows="5"
                  />

                </div>

              </div>

            </div>


            {/* ACTIONS */}

            <div className="form-actions">

              <button
                type="button"
                className="secondary-button"
                onClick={clearForm}
              >
                Clear Form
              </button>

              <button
                type="submit"
                className="submit-button"
              >
                Submit Form →
              </button>

            </div>

          </form>

        </section>

      </main>

    </div>
  );
}

export default App;