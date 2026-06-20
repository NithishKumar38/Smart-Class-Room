# 🏫 AI Classroom Co-Pilot
### Haryana Government Schools — Smart Board AI Assistant

> **Teacher ka haath — AI ka saath.**
> A production-grade voice-controlled AI teaching assistant powered by Gemini 2.5 Flash.

---

## 📋 Features

| Feature | Description |
|---|---|
| 📚 **Live Concept Simplifier** | Speak a topic → Gemini explains in Hinglish → diagram + audio |
| 🧠 **Voice Quiz Generator** | Speak a quiz command → MCQs → student answers → score |
| 🎤 **Voice Input** | Hindi, English, and Hinglish via faster-whisper |
| 🔊 **Text-to-Speech** | Explanations and questions read aloud via gTTS |
| 📊 **Mermaid Diagrams** | Educational diagrams rendered on smart board |
| 💾 **Session History** | SQLite database tracks concepts taught and quiz scores |

---

## 🗂️ Project Structure

```
smart classroom/
├── app.py                        # Main entry point
├── requirements.txt
├── .env.example                  # Copy to .env and add your API key
│
├── pages/
│   ├── concept_simplifier.py     # Feature 1: Concept explanation
│   └── quiz_generator.py         # Feature 2: Quiz generation
│
├── services/
│   ├── gemini_service.py         # Gemini 2.5 Flash API integration
│   ├── speech_to_text.py         # faster-whisper STT service
│   ├── text_to_speech.py         # gTTS TTS service
│   └── diagram_generator.py      # Mermaid + SVG diagram rendering
│
├── database/
│   └── db.py                     # SQLite schema and queries
│
├── prompts/
│   ├── concept_prompt.txt        # Gemini concept explanation prompt
│   └── quiz_prompt.txt           # Gemini quiz generation prompt
│
├── utils/
│   └── helpers.py                # Shared utility functions
│
└── assets/
    ├── audio/                    # Generated TTS MP3 files (auto-cleaned)
    └── images/                   # Static image assets
```

---

## ⚡ Quick Start

### 1. Prerequisites

- Python 3.11 or higher
- A [Gemini API key](https://aistudio.google.com/app/apikey) (free tier available)
- Microphone (optional — text input fallback available)

### 2. Clone / Open the Project

```bash
cd "d:\projects\Projects\smart classroom"
```

### 3. Create and Activate Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

> ⏱️ **Note:** `faster-whisper` will download the Whisper model (~140MB for `base`) on first run.
> This may take 1–2 minutes depending on your internet speed.

### 5. Configure Environment Variables

```bash
# Copy the example file
copy .env.example .env
```

Open `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_actual_api_key_here
SCHOOL_NAME=Haryana Govt. Smart Classroom
WHISPER_MODEL=base
TTS_LANGUAGE=hi
```

### 6. Run the Application

```bash
streamlit run app.py
```

The app will open at **http://localhost:8501** in your browser.

---

## 🎤 Usage Guide

### Feature 1: Live Concept Simplifier

Navigate to **📚 Concept Simplifier** from the sidebar.

**Voice commands (examples):**
```
"Explain photosynthesis for Class 6"
"Water cycle samjhao Hinglish mein"
"Fractions with examples batao"
"Gravity explain karo Class 9 ke liye"
```

**What happens:**
1. Voice is transcribed by Whisper (or type directly)
2. Gemini generates a Hinglish explanation
3. A Mermaid diagram appears on the right
4. Audio explanation plays automatically

### Feature 2: Voice-Triggered Quiz Generator

Navigate to **🧠 Quiz Generator** from the sidebar.

**Voice commands (examples):**
```
"Create 5 questions on fractions"
"Generate a quiz on photosynthesis for Class 6"
"Ask students 10 MCQs on water cycle"
"Quiz on Indian history for Class 8"
```

**What happens:**
1. Command transcribed by Whisper (or type directly)
2. Gemini generates N multiple-choice questions
3. Questions display on screen (can be read aloud)
4. Students select answers
5. Submit → Score + correct answers shown

---

## 🔧 Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Google Gemini API key |
| `SCHOOL_NAME` | `Haryana Govt. Smart Classroom` | Displayed in app header |
| `WHISPER_MODEL` | `base` | STT model: `tiny`, `base`, `small`, `medium` |
| `TTS_LANGUAGE` | `hi` | TTS language code (`hi`=Hindi, `en`=English) |
| `AUDIO_CLEANUP_HOURS` | `1` | Delete old TTS audio files after N hours |
| `MAX_QUIZ_QUESTIONS` | `15` | Maximum questions per quiz |

### Whisper Model Selection

| Model | Size | Speed | Accuracy | Recommended For |
|---|---|---|---|---|
| `tiny` | ~75MB | Very fast | Basic | Very slow computers |
| `base` | ~140MB | Fast | Good | **Default — most schools** |
| `small` | ~500MB | Medium | Better | Computers with 4GB+ RAM |
| `medium` | ~1.5GB | Slow | Best | GPU-equipped systems |

---

## 🛠️ Troubleshooting

### "GEMINI_API_KEY is not set"
→ Make sure `.env` file exists and contains a valid key.
→ Get a free key at: https://aistudio.google.com/app/apikey

### Microphone not working
→ Browser must have microphone permission granted.
→ If using HTTP (not HTTPS), try allowing microphone in browser settings.
→ Use the text input fallback — all features work without a mic.

### Whisper model download stuck
→ First run downloads ~140MB. Wait for it to complete.
→ Run `python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"` to pre-download.

### Audio not playing
→ gTTS requires internet connection.
→ Check firewall rules don't block `translate.google.com`.

### Quiz JSON parse error
→ Gemini occasionally returns malformed JSON. Click "Generate" again.

---

## 📊 Technology Stack

| Component | Technology | Version |
|---|---|---|
| Frontend | Streamlit | 1.45.1 |
| AI / LLM | Google Gemini 2.5 Flash | Latest |
| SDK | google-genai | 1.16.0 |
| Speech-to-Text | faster-whisper | 1.1.1 |
| Text-to-Speech | gTTS | 2.5.3 |
| Database | SQLite3 | stdlib |
| Diagrams | Mermaid.js | 10 (CDN) |
| Language | Python | 3.11+ |

---

## 🔒 Security Notes

- API keys are loaded from `.env` — **never commit `.env` to git**
- `.env` is listed in `.gitignore`
- All user input is validated before sending to Gemini
- Generated audio files are auto-cleaned after 1 hour

---

## 📝 License

Built for Haryana Government Schools — AI-powered education for every child.
