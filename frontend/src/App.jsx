import React, { useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [message, setMessage] = useState(
    "Click the microphone and speak your details."
  );
  const [status, setStatus] = useState("Ready");
  const [transcript, setTranscript] = useState("");
  const [rawSttJson, setRawSttJson] = useState("");
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const stopMicrophone = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const uploadRecording = async (audioBlob) => {
    if (audioBlob.size === 0) {
      setStatus("Error");
      setMessage("No audio was recorded. Please try again.");
      return;
    }

    setStatus("Processing...");
    setMessage("Converting your speech to text...");

    const formData = new FormData();
    const extension = audioBlob.type.includes("ogg")
      ? "ogg"
      : audioBlob.type.includes("mp4")
        ? "mp4"
        : "webm";
    formData.append("audio", audioBlob, `recording.${extension}`);
    formData.append("language", "en");

    try {
      const response = await fetch(`${API_BASE_URL}/transcribe`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      setRawSttJson(JSON.stringify(payload, null, 2));

      if (!response.ok) {
        throw new Error(payload.error?.message || "Unable to transcribe the audio.");
      }

      setTranscript(payload.transcript.text);
      setStatus("Success");
      setMessage("Transcript received. It has not been applied to the form.");
    } catch (error) {
      setStatus("Error");
      setMessage(error.message || "Unable to contact the speech-to-text service.");
    }
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus("Error");
      setMessage("This browser does not support microphone recording.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : undefined;
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      streamRef.current = stream;
      recorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        stopMicrophone();
        setStatus("Error");
        setMessage("Recording failed. Please try again.");
      };
      recorder.onstop = async () => {
        stopMicrophone();
        const audioBlob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        await uploadRecording(audioBlob);
      };

      recorder.start();
      setTranscript("");
      setRawSttJson("");
      setStatus("Listening...");
      setMessage("Listening... Click Speak again when you are finished.");
    } catch (error) {
      setStatus("Error");
      setMessage("Microphone permission was denied or unavailable.");
    }
  };

  const handleSpeak = () => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
      return;
    }
    startRecording();
  };

  return (
    <div className="app">
      <div className="card">

        <h1>FormVoice</h1>

        <p className="subtitle">
          Fill your form using your voice
        </p>

        <label>Name</label>
        <input placeholder="Your name" />

        <label>Phone Number</label>
        <input placeholder="Phone number" />

        <label>Application ID</label>
        <input placeholder="Application ID" />

        <label>Address</label>
        <textarea placeholder="Address"></textarea>

        <button
          className="mic"
          onClick={handleSpeak}
          disabled={status === "Processing..."}
        >
          🎙 {status === "Listening..." ? "Stop recording" : "Speak"}
        </button>

        <div className="assistant">
          <strong>Status: {status}</strong>
          <div>🤖 {message}</div>
        </div>

        {transcript && (
          <div className="transcript">
            <strong>Transcript</strong>
            <p>{transcript}</p>
          </div>
        )}

        {rawSttJson && (
          <div className="transcript">
            <strong>Raw STT JSON</strong>
            <pre>{rawSttJson}</pre>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
