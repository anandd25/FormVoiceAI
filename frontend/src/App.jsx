import React, { useEffect, useMemo, useRef, useState } from "react";
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
  email: "Email",
  application_id: "Application ID",
  pin: "PIN Code",
  address: "Address",
  city: "City",
  state: "State",
  paragraph: "Paragraph / Description",
};

function App() {
  const [form, setForm] = useState(initialForm);
  const [message, setMessage] = useState(
    "Click the microphone and speak your details."
  );
  const [status, setStatus] = useState("Ready");
  const [transcript, setTranscript] = useState("");
  const [activeField, setActiveField] = useState(null);

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const completedFields = useMemo(() => {
    return Object.values(form).filter(
      (value) => String(value).trim() !== ""
    ).length;
  }, [form]);

  const progressPercent = (completedFields / 10) * 100;

  const stopMicrophone = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const handleChange = (event) => {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const processVoice = async (transcriptText, targetField = null) => {
    setStatus("Processing");

    if (targetField) {
      setMessage(`Understanding your ${fieldLabels[targetField]}...`);
    } else {
      setMessage("Understanding your details...");
    }

    try {
      const response = await fetch(`${API_BASE_URL}/process-voice`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: transcriptText,
          current_form: form,
          target_field: targetField,
        }),
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ||
            payload.error?.message ||
            "Unable to process your voice input."
        );
      }

      if (targetField) {
        const returnedValue =
          payload.form?.[targetField] ??
          payload.value ??
          transcriptText;

        setForm((previous) => ({
          ...previous,
          [targetField]: returnedValue,
        }));
      } else if (payload.form) {
        setForm((previous) => ({
          ...previous,
          ...payload.form,
        }));
      }

      setMessage(
        payload.message ||
          (targetField
            ? `${fieldLabels[targetField]} updated successfully.`
            : "Your details have been added to the form.")
      );

      setStatus("Success");
    } catch (error) {
      setStatus("Error");
      setMessage(error.message || "Unable to process voice input.");
    }
  };

  const uploadRecording = async (audioBlob, targetField = null) => {
    if (!audioBlob || audioBlob.size === 0) {
      setStatus("Error");
      setMessage("No audio was recorded. Please try again.");
      return;
    }

    setStatus("Processing");
    setMessage("Converting your speech to text...");

    const formData = new FormData();

    const extension = audioBlob.type.includes("ogg")
      ? "ogg"
      : audioBlob.type.includes("mp4")
      ? "mp4"
      : "webm";

    formData.append(
      "audio",
      audioBlob,
      `recording.${extension}`
    );

    formData.append("language", "en");

    try {
      const response = await fetch(`${API_BASE_URL}/transcribe`, {
        method: "POST",
        body: formData,
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.error?.message ||
            payload.detail ||
            "Unable to transcribe the audio."
        );
      }

      const transcriptText = payload.transcript?.text || "";

      if (!transcriptText.trim()) {
        throw new Error("No speech was detected.");
      }

      setTranscript(transcriptText);

      await processVoice(transcriptText, targetField);
    } catch (error) {
      setStatus("Error");
      setMessage(
        error.message ||
          "Unable to contact the speech-to-text service."
      );
    }
  };

  const startRecording = async (targetField = null) => {
    if (
      !navigator.mediaDevices?.getUserMedia ||
      !window.MediaRecorder
    ) {
      setStatus("Error");
      setMessage(
        "This browser does not support microphone recording."
      );
      return;
    }

    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

      const mimeType =
        MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : undefined;

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorderRef.current = recorder;
      streamRef.current = stream;
      audioChunksRef.current = [];
      setActiveField(targetField);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        stopMicrophone();
        setActiveField(null);
        setStatus("Error");
        setMessage("Recording failed. Please try again.");
      };

      recorder.onstop = async () => {
        stopMicrophone();

        const audioBlob = new Blob(
          audioChunksRef.current,
          {
            type:
              recorder.mimeType || "audio/webm",
          }
        );

        const savedField = targetField;

        setActiveField(null);

        await uploadRecording(
          audioBlob,
          savedField
        );
      };

      recorder.start();

      setTranscript("");
      setStatus("Listening");

      if (targetField) {
        setMessage(
          `Listening for ${fieldLabels[targetField]}... Click the microphone again when finished.`
        );
      } else {
        setMessage(
          "Listening... Speak your details and click Stop recording when finished."
        );
      }
    } catch {
      setStatus("Error");
      setActiveField(null);
      setMessage(
        "Microphone permission was denied or unavailable."
      );
    }
  };

  const handleMainSpeak = () => {
    if (
      recorderRef.current?.state === "recording"
    ) {
      recorderRef.current.stop();
      return;
    }

    startRecording(null);
  };

  const handleFieldSpeak = (fieldName) => {
    if (
      recorderRef.current?.state === "recording"
    ) {
      recorderRef.current.stop();
      return;
    }

    startRecording(fieldName);
  };

  const clearForm = () => {
    setForm(initialForm);
    setTranscript("");
    setStatus("Ready");
    setActiveField(null);
    setMessage(
      "Form cleared. Click the microphone and speak your details."
    );
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    setMessage(
      "Your form is ready to be submitted."
    );

    setStatus("Ready");
  };

  const renderInput = (
    name,
    placeholder,
    type = "text"
  ) => {
    const isListening =
      activeField === name &&
      status === "Listening";

    return (
      <div className="field-group">
        <label htmlFor={name}>
          {fieldLabels[name]}
        </label>

        <div
          className={`voice-input-wrapper ${
            isListening ? "field-listening" : ""
          }`}
        >
          <input
            id={name}
            name={name}
            type={type}
            value={form[name]}
            onChange={handleChange}
            placeholder={placeholder}
          />

          <button
            type="button"
            className={`field-mic ${
              isListening ? "active" : ""
            }`}
            onClick={() =>
              handleFieldSpeak(name)
            }
            aria-label={`Speak for ${fieldLabels[name]}`}
            title={`Speak for ${fieldLabels[name]}`}
          >
            {isListening ? "●" : "🎙"}
          </button>
        </div>
      </div>
    );
  };

  const renderTextarea = (
    name,
    placeholder,
    rows
  ) => {
    const isListening =
      activeField === name &&
      status === "Listening";

    return (
      <div className="field-group full-width">
        <label htmlFor={name}>
          {fieldLabels[name]}
        </label>

        <div
          className={`voice-input-wrapper textarea-wrapper ${
            isListening ? "field-listening" : ""
          }`}
        >
          <textarea
            id={name}
            name={name}
            value={form[name]}
            onChange={handleChange}
            placeholder={placeholder}
            rows={rows}
          />

          <button
            type="button"
            className={`field-mic textarea-mic ${
              isListening ? "active" : ""
            }`}
            onClick={() =>
              handleFieldSpeak(name)
            }
            aria-label={`Speak for ${fieldLabels[name]}`}
            title={`Speak for ${fieldLabels[name]}`}
          >
            {isListening ? "●" : "🎙"}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand-row">
            <div className="brand-icon">FV</div>

            <div>
              <h1>FormVoice</h1>
              <p>Voice-powered form filling</p>
            </div>
          </div>
        </div>

        <div className="ready-badge">
          <span className="ready-dot" />
          AI Ready
        </div>
      </header>

      <main className="dashboard">
        <section className="left-panel">
          <div className="voice-card">
            <div
              className={`voice-orb ${
                status === "Listening"
                  ? "listening"
                  : ""
              }`}
            >
              <div className="voice-ring ring-one" />
              <div className="voice-ring ring-two" />
              <div className="voice-ring ring-three" />

              <div className="mic-symbol">
                🎙️
              </div>
            </div>

            <span className="eyebrow">
              VOICE INPUT
            </span>

            <h2>Tell me your details</h2>

            <p>
              Speak naturally and FormVoice will
              fill the form for you.
            </p>

            <button
              type="button"
              className={`main-mic-button ${
                status === "Listening" &&
                activeField === null
                  ? "recording"
                  : ""
              }`}
              onClick={handleMainSpeak}
              disabled={status === "Processing"}
            >
              {status === "Listening" &&
              activeField === null
                ? "■ Stop Recording"
                : "🎙 Speak"}
            </button>

            {status === "Listening" &&
              activeField === null && (
                <div className="wave-bars">
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              )}
          </div>

          <div className="assistant-card">
            <div className="assistant-header">
              <div className="assistant-icon">
                🤖
              </div>

              <div>
                <span>AI ASSISTANT</span>
                <strong>{status}</strong>
              </div>
            </div>

            <p>{message}</p>
          </div>

          {transcript && (
            <div className="transcript-card">
              <div className="transcript-title">
                <span>🎧</span>
                Transcript
              </div>

              <p>"{transcript}"</p>
            </div>
          )}
        </section>

        <section className="form-card">
          <div className="form-heading">
            <div>
              <span className="eyebrow">
                FORM DETAILS
              </span>
              <h2>Your Details</h2>
              <p>
                Review and edit the information
                captured from your voice.
              </p>
            </div>

            <div className="progress-count">
              {completedFields} / 10
            </div>
          </div>

          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${progressPercent}%`,
              }}
            />
          </div>

          <p className="progress-text">
            {completedFields} of 10 fields
            completed
          </p>

          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              {renderInput(
                "name",
                "Your full name"
              )}

              {renderInput(
                "dob",
                "DD/MM/YYYY"
              )}

              {renderInput(
                "phone",
                "Phone number"
              )}

              {renderInput(
                "email",
                "Email address",
                "email"
              )}

              {renderInput(
                "application_id",
                "Application ID"
              )}

              {renderInput(
                "pin",
                "PIN code"
              )}

              {renderInput(
                "city",
                "City"
              )}

              {renderInput(
                "state",
                "State"
              )}

              {renderTextarea(
                "address",
                "Your address",
                3
              )}

              {renderTextarea(
                "paragraph",
                "Speak or type your description...",
                5
              )}
            </div>

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
                Submit Form
              </button>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;