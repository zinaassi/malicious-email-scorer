# Malicious Email Scorer

A Gmail Add-on that analyzes any open email for phishing and malicious intent. It surfaces a 0–100 risk score, a plain-English verdict, and a list of specific red flags — directly inside Gmail, as a sidebar card.

---

## Overview

Phishing emails are the most common entry point for account takeovers and data breaches, yet most email clients offer no per-message security signal. This tool fills that gap: when a user opens an email, the add-on silently reads the message, sends it to a FastAPI backend, and returns an AI-powered analysis in under two seconds.

The system is designed around two principles:

- **Explainability** — a score alone is not useful. Every result includes reasoning and specific flags so the user understands *why* an email was flagged.
- **Safety by default** — the backend never logs email content, never exposes internal errors, and truncates input before forwarding it to any external API.

---

## Architecture

```
Gmail (user opens email)
        │
        ▼
Google Apps Script          ← reads email fields, renders result card
        │  HTTP POST /analyze
        ▼
FastAPI backend             ← validates input, builds prompt, calls Gemini
        │
        ▼
Gemini 2.5 Flash API        ← returns structured JSON analysis
```

The backend is exposed to the internet via **ngrok**, which tunnels the local server to a public HTTPS URL that Apps Script can reach. This avoids any cloud deployment requirement for a local demo.

---

## Scoring Model

Gemini is instructed to score each email 0–100 across seven signals:

| Signal | What it detects |
|--------|----------------|
| Sender/domain mismatch | Display name claims one company; sending domain is another |
| Urgency language | Pressure phrases designed to bypass judgment |
| Credential or money requests | Explicit asks for passwords, card numbers, wire transfers |
| Suspicious links | Shortened URLs, domains that misspell known brands |
| Grammar anomalies | Machine-translated or unusual phrasing |
| Brand impersonation | Visual or textual mimicry of known companies |
| Reply-to mismatch | Reply address differs from the sender domain |

| Score | Verdict |
|-------|---------|
| 0–39 | Safe |
| 40–69 | Suspicious |
| 70–100 | Malicious |

---

## Repository Structure

```
malicious-email-scorer/
├── backend/
│   ├── main.py              # FastAPI app — endpoints, prompt, error handling
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│       ├── conftest.py      # sets dummy API key before import so tests collect cleanly
│       └── test_main.py     # 5 tests, Gemini client fully mocked
└── addon/
    ├── Code.gs              # Apps Script — trigger, backend call, card rendering
    └── appsscript.json      # OAuth scopes and contextual trigger declaration
```

---

## Key Design Decisions

**Input truncation at 3000 characters**
The email body is capped before it reaches the prompt. This prevents prompt injection via email content, controls token cost, and avoids forwarding arbitrarily large payloads to an external API.

**Pydantic validation at the boundary**
All request fields are declared in a `BaseModel`. FastAPI rejects malformed requests with 422 before any application logic runs — no manual field checking required.

**Sanitized error responses**
The backend has three distinct error paths: JSON parse failure (502), rate limit (429), and everything else (500). In all cases the client receives a human-readable message. Stack traces and exception types are logged server-side only and never returned to the caller.

**Fence-stripping before JSON parse**
Despite prompt instructions to return only valid JSON, Gemini occasionally wraps its response in markdown code fences. The backend strips any leading/trailing fence before calling `json.loads()`, making the parser robust to this inconsistency.

**No email content in logs**
`logger.info` records only the score and verdict. The email subject, sender, and body are never written to any log output — a deliberate privacy constraint.

**Gemini model selection**
The Gemini 1.5 family returns 404 on the new SDK's v1beta endpoint (deprecated). `gemini-2.0-flash` and `gemini-2.0-flash-lite` were exhausted during development. `gemini-2.5-flash` was selected as the stable, quota-separate option with the best response quality.

---

## Running the Project

### Prerequisites
- Python 3.11+
- A free Gemini API key from [aistudio.google.com](https://aistudio.google.com) (no credit card required)
- A free [ngrok](https://ngrok.com) account

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Paste your Gemini API key into .env
```

Verify before starting:

```bash
ruff check .                          # lint
mypy main.py --ignore-missing-imports # type check
pytest tests/ -v                      # 5 tests, all must pass
uvicorn main:app --reload             # start server
```

### 2. Public tunnel

```bash
ngrok http 8000
# Copy the https://xxxx.ngrok-free.app URL printed to the terminal
```

Update `addon/Code.gs`:

```javascript
var BACKEND_URL = "https://xxxx.ngrok-free.app/analyze";
```

> The free ngrok tier assigns a new URL on every restart. Update `Code.gs` before each session.

### 3. Gmail Add-on

1. Open [script.google.com](https://script.google.com) → New project
2. Paste the contents of `addon/Code.gs` and `addon/appsscript.json`
3. Deploy → Test deployments → Install for yourself
4. Open Gmail — the sidebar appears when you open any email

### Smoke test

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Urgent: Verify your account now",
    "sender": "security@paypa1.com",
    "reply_to": "harvester@randomdomain.ru",
    "body": "Your account has been suspended. Click here immediately to restore access."
  }'
# Expected: score >= 70, verdict "Malicious", flags not empty
```

---

## Test Suite

```bash
cd backend && pytest tests/ -v
```

The Gemini client is fully mocked — no API key required to run tests.

| Test | Coverage |
|------|----------|
| `test_health_returns_ok` | GET /health returns 200 with correct body |
| `test_analyze_missing_fields_returns_422` | Pydantic rejects incomplete requests before handler runs |
| `test_analyze_body_truncated` | Bodies over 3000 chars are trimmed in the prompt |
| `test_analyze_returns_expected_shape` | Response fields exist and have correct types |
| `test_analyze_invalid_json_from_gemini` | Malformed AI output returns 502, not an unhandled 500 |

---

## Security Properties

| Property | Implementation |
|----------|---------------|
| No secrets in code | API key loaded from `.env`, excluded from git |
| Input truncation | Body capped at 3000 chars before any external call |
| No PII in logs | Email content never written to log output |
| Sanitized errors | Clients never see stack traces or exception types |
| Input validation | Pydantic rejects malformed requests at the framework level |
