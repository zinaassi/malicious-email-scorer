# Malicious Email Scorer

A Gmail Add-on that analyzes any open email for phishing and malicious intent, returning a score, verdict, and plain-English explanation
powered by Gemini AI.

---

## How It Works

```
Gmail (open email)
  → Apps Script reads email fields
  → HTTP POST to FastAPI backend (via ngrok)
  → Backend prompts Gemini AI
  → Gemini returns structured JSON analysis
  → Add-on renders a card with score, verdict, and red flags
```

---

## Components

### Backend (`backend/`)
- **FastAPI** REST API with two endpoints: `GET /health` and `POST /analyze`
- Validates input with **Pydantic** — malformed requests are rejected with 422 before reaching any business logic
- Truncates email body to 3000 characters before sending to Gemini (security + cost control)
- Returns sanitized error responses — no stack traces exposed to clients
- Logs only score and verdict, never email content

### Gmail Add-on (`addon/`)
- **Google Apps Script** contextual trigger that fires when the user opens an email
- Reads subject, sender, reply-to, body, and date via the Gmail API
- POSTs to the backend and renders a `CardService` UI card
- Color-coded verdict: 🟢 Safe · 🟡 Suspicious · 🔴 Malicious

---

## Scoring

| Score | Verdict |
|-------|---------|
| 0–39 | Safe |
| 40–69 | Suspicious |
| 70–100 | Malicious |

Gemini analyzes for: sender/domain mismatch, urgency language, credential or money requests, suspicious links, grammar anomalies, brand impersonation, and reply-to mismatch.

---

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your Gemini API key to .env
# Get a free key at https://aistudio.google.com (no credit card required)
```

Run verification before starting:

```bash
ruff check .
mypy main.py --ignore-missing-imports
pytest tests/ -v
uvicorn main:app --reload
```

### 2. Expose the backend with ngrok

```bash
ngrok http 8000
# Copy the https://xxxx.ngrok-free.app URL
```

Update `BACKEND_URL` in `addon/Code.gs` with the new URL + `/analyze`:

```javascript
var BACKEND_URL = "https://xxxx.ngrok-free.app/analyze";
```

> The ngrok URL changes on every restart (free tier). Update `Code.gs` before each session.

### 3. Gmail Add-on

1. Open [script.google.com](https://script.google.com) and create a new project
2. Copy the contents of `addon/Code.gs` and `addon/appsscript.json` into the editor
3. Deploy as a Gmail Add-on (Deploy → Test deployments)
4. Open Gmail — the add-on appears in the right sidebar when you open any email

---

## Environment Variables

```
GEMINI_API_KEY=your_key_here
```

Never commit `.env` — it is in `.gitignore`.

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

Tests mock the Gemini client so no real API calls are made.

| Test | What it checks |
|------|---------------|
| `test_health_returns_ok` | GET /health returns 200 |
| `test_analyze_missing_fields_returns_422` | Pydantic rejects incomplete input |
| `test_analyze_body_truncated` | Body > 3000 chars is trimmed in the prompt |
| `test_analyze_returns_expected_shape` | Response has correct fields and types |
| `test_analyze_invalid_json_from_gemini` | Bad AI output returns 502, not a crash |

---

## Repository Structure

```
malicious-email-scorer/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│       ├── conftest.py
│       └── test_main.py
└── addon/
    ├── Code.gs
    └── appsscript.json
```
