import React, { useState } from "react";
import "./App.css";

type VoicePreset = {
  id: string;
  label: string;
  description: string;
  tag: string;
  gender?: "male" | "female" | "other";
  isCustom?: boolean;
};

const PRESET_VOICES: VoicePreset[] = [
  {
    id: "gentleman_deep",
    label: "Gentleman Deep",
    description: "Deep male narration voice, perfect for documentaries.",
    tag: "Male",
    gender: "male",
  },
  {
    id: "gentleman_soft",
    label: "Gentleman Soft",
    description: "Soft, warm male tone for explainers.",
    tag: "Male",
    gender: "male",
  },
  {
    id: "boy_casual",
    label: "Boy Casual",
    description: "Young casual male voice, YouTube vibe.",
    tag: "Casual",
    gender: "male",
  },
  {
    id: "boy_energy",
    label: "Boy Energy",
    description: "High-energy male for hooks and intros.",
    tag: "Hype",
    gender: "male",
  },
  {
    id: "girl_warm",
    label: "Girl Warm",
    description: "Warm female voice, soft storytelling.",
    tag: "Female",
    gender: "female",
  },
  {
    id: "girl_story",
    label: "Girl Storyteller",
    description: "Perfect for long story narration.",
    tag: "Story",
    gender: "female",
  },
  {
    id: "girl_crisp",
    label: "Girl Crisp",
    description: "Crisp, clear female announcer style.",
    tag: "Promo",
    gender: "female",
  },
  {
    id: "girl_friendly",
    label: "Girl Friendly",
    description: "Friendly female voice for tutorials.",
    tag: "Friendly",
    gender: "female",
  },
  {
    id: "radio_host",
    label: "Radio Host",
    description: "FM radio host tone.",
    tag: "Radio",
    gender: "male",
  },
  {
    id: "movie_trailer",
    label: "Movie Trailer",
    description: "Dramatic trailer-style narration.",
    tag: "Trailer",
    gender: "male",
  },
  {
    id: "soft_whisper",
    label: "Soft Whisper",
    description: "Soft, whisper-like ASMR style.",
    tag: "ASMR",
    gender: "female",
  },
  {
    id: "news_anchor",
    label: "News Anchor",
    description: "Serious news anchor tone.",
    tag: "News",
    gender: "male",
  },
];

// Must match CUSTOM_VOICES keys in main.py
const INITIAL_CUSTOM_VOICES: VoicePreset[] = [
  {
    id: "custom_deep_story_female",
    label: "Custom: Deep Story Female",
    description: "Storytelling female voice from your sample.",
    tag: "Custom",
    gender: "female",
    isCustom: true,
  },
  {
    id: "custom_deep_story_male",
    label: "Custom: Deep Story Male",
    description: "Storytelling male voice from your sample.",
    tag: "Custom",
    gender: "male",
    isCustom: true,
  },
  {
    id: "custom_jesus_voice",
    label: "Custom: Jesus Style Voice",
    description: "Voice based on jesus.mp3 sample.",
    tag: "Custom",
    gender: "male",
    isCustom: true,
  },
];

const LANGUAGE_OPTIONS = [
  { value: "en", label: "English (en)" },
  { value: "hi", label: "Hindi (hi)" },
  { value: "es", label: "Spanish (es)" },
];

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const App: React.FC = () => {
  const [text, setText] = useState(
    "Once upon a time, in a quiet town, there lived a storyteller who could turn any moment into magic."
  );
  const [language, setLanguage] = useState("en");
  const [selectedVoiceId, setSelectedVoiceId] = useState("gentleman_deep");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number }>({
    current: 0,
    total: 0,
  });

  const [customVoices, setCustomVoices] =
    useState<VoicePreset[]>(INITIAL_CUSTOM_VOICES);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");

  const allVoices = [...PRESET_VOICES, ...customVoices];
  const selectedVoice = allVoices.find((v) => v.id === selectedVoiceId);

  const handleSpeak = async () => {
    if (!text.trim()) {
      alert("Please enter some text.");
      return;
    }

    setIsLoading(true);
    setAudioUrl(null);
    setProgress({ current: 0, total: 0 });

    const intervalId = window.setInterval(async () => {
      try {
        const res = await fetch(`${BASE_URL}/tts/progress`);
        if (res.ok) {
          const data = await res.json();
          setProgress({
            current: data.current ?? 0,
            total: data.total ?? 0,
          });
        }
      } catch {
        // ignore
      }
    }, 1000);

    try {
      const res = await fetch(`${BASE_URL}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          language,
          voice_id: selectedVoiceId,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        console.error("TTS error:", err || res.statusText);
        alert(`TTS error: ${err?.detail || res.statusText}`);
        return;
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
    } catch (err) {
      console.error(err);
      alert("Failed to connect to TTS server.");
    } finally {
      window.clearInterval(intervalId);
      setIsLoading(false);
    }
  };

  const handleCloneUpload = async () => {
    if (!uploadFile) {
      alert("Please choose an audio file to upload.");
      return;
    }

    const formData = new FormData();
    formData.append("audio", uploadFile);
    if (uploadName.trim()) {
      formData.append("name", uploadName.trim());
    }

    try {
      const res = await fetch(`${BASE_URL}/voices/clone`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        alert(`Clone error: ${err?.detail || res.statusText}`);
        return;
      }

      const data = await res.json();
      const newVoice: VoicePreset = {
        id: data.voice_id,
        label: `Custom: ${data.name || data.voice_id}`,
        description: "Cloned custom voice from your upload.",
        tag: "Custom",
        gender: "other",
        isCustom: true,
      };

      setCustomVoices((prev) => [...prev, newVoice]);
      setSelectedVoiceId(newVoice.id);
      alert("Voice cloned successfully!");
    } catch (err) {
      console.error(err);
      alert("Failed to upload and clone voice.");
    }
  };

  const showProgress = progress.total > 0 && isLoading;
  const progressPercent =
    progress.total > 0
      ? Math.min(100, Math.round((progress.current / progress.total) * 100))
      : 0;

  return (
    <div className="app-root">
      <div className="app-gradient-bg" />
      <div className="app-shell">
        <header className="app-header">
          <div className="app-logo-circle">🎙</div>
          <div>
            <h1>Local Voice Studio</h1>
            <p>Beautiful voiceovers. Fully local. Your custom voices, your control.</p>
          </div>
        </header>

        <main className="app-main-grid">
          {/* LEFT PANEL */}
          <section className="panel panel-left glass">
            <div className="panel-header">
              <h2>Script & Controls</h2>
              <span className="pill pill-soft">Step 1</span>
            </div>

            <div className="field-group">
              <label>Script text</label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste your YouTube story, podcast intro, or narration script here..."
              />
            </div>

            <div className="controls-row">
              <div className="field">
                <label>Script language</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                className={`btn-primary ${isLoading ? "btn-disabled" : ""}`}
                onClick={handleSpeak}
                disabled={isLoading}
              >
                {isLoading ? "Generating..." : "🔊 Speak with this voice"}
              </button>
            </div>

            {showProgress && (
              <div className="progress-wrapper">
                <div className="progress-top-row">
                  <span>Generating audio…</span>
                  <span>
                    Chunk <strong>{progress.current}</strong> /{" "}
                    <strong>{progress.total}</strong>
                  </span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            )}

            {selectedVoice && (
              <div className="current-voice-banner">
                <span>
                  Voice: <strong>{selectedVoice.label}</strong>
                </span>
                <span>Language: {language}</span>
              </div>
            )}

            {audioUrl && (
              <div className="audio-preview">
                <div className="audio-preview-header">
                  <span className="pill pill-soft">Result</span>
                  <span className="audio-title">Preview audio</span>
                </div>
                <audio controls src={audioUrl} />
              </div>
            )}

            <div className="divider" />

            <div className="clone-section">
              <div className="panel-header">
                <h3>Clone a new custom voice</h3>
                <span className="pill pill-green">Step 2 (optional)</span>
              </div>
              <p className="muted">
                Upload 10–30 seconds of clean speech (your own, or with explicit
                permission). We&apos;ll turn it into a reusable custom voice.
              </p>
              <div className="clone-grid">
                <div className="field">
                  <label>Voice sample file</label>
                  <input
                    type="file"
                    accept=".wav,.mp3,.ogg,.flac"
                    onChange={(e) =>
                      setUploadFile(e.target.files?.[0] || null)
                    }
                  />
                </div>
                <div className="field">
                  <label>Display name (optional)</label>
                  <input
                    type="text"
                    value={uploadName}
                    onChange={(e) => setUploadName(e.target.value)}
                    placeholder="e.g. Deep Hindi Story Female"
                  />
                </div>
              </div>
              <button className="btn-secondary" onClick={handleCloneUpload}>
                🎧 Clone voice from sample
              </button>
            </div>
          </section>

          {/* RIGHT PANEL */}
          <section className="panel panel-right glass">
            <div className="panel-header">
              <h2>Choose a voice</h2>
              <span className="pill pill-soft">Step 0</span>
            </div>
            <p className="muted">
              <strong>Presets</strong> use built-in English voices.{" "}
              <strong>Custom voices</strong> (Deep Story, Jesus Voice, etc.)
              use XTTS and can speak Hindi and more.
            </p>

            <div className="voices-grid">
              {allVoices.map((voice) => {
                const isActive = voice.id === selectedVoiceId;
                return (
                  <button
                    key={voice.id}
                    className={`voice-card ${isActive ? "voice-card-active" : ""
                      }`}
                    onClick={() => setSelectedVoiceId(voice.id)}
                  >
                    <div className="voice-card-top">
                      <div className="voice-avatar">
                        {voice.gender === "female" ? "👩" : "👨"}
                      </div>
                      <div className="voice-text">
                        <div className="voice-title">{voice.label}</div>
                        <div className="voice-desc">{voice.description}</div>
                      </div>
                    </div>
                    <div className="voice-tags">
                      <span className="pill tiny">
                        {voice.isCustom ? "Custom" : "Preset"}
                      </span>
                      <span className="pill-outline tiny">{voice.tag}</span>
                      {voice.gender && (
                        <span className="pill-outline tiny">
                          {voice.gender}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default App;
