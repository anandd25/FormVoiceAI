import React, { useState } from "react";
import "./App.css";

function App() {
  const [message, setMessage] = useState(
    "Click the microphone and speak your details."
  );

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
          onClick={() => setMessage("🎙 Microphone clicked!")}
        >
          🎙 Speak
        </button>

        <div className="assistant">
          🤖 {message}
        </div>

      </div>
    </div>
  );
}

export default App;