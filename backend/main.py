import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from google import genai
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Allow empty key at import time so tests can patch without a real credential.
# A missing key will fail at the first real API call, not at startup.
_api_key = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=_api_key)

app = FastAPI()

MAX_BODY_CHARS = 3000
GEMINI_MODEL = "gemini-2.5-flash"


class EmailRequest(BaseModel):
    subject: str
    sender: str
    reply_to: Optional[str] = None
    body: str
    date: Optional[str] = None


class AnalysisResponse(BaseModel):
    score: int
    verdict: str
    reasoning: str
    flags: list[str]


def build_prompt(email: EmailRequest) -> str:
    truncated_body = email.body[:MAX_BODY_CHARS]
    reply_to_line = f"Reply-To: {email.reply_to}" if email.reply_to else ""
    date_line = f"Date: {email.date}" if email.date else ""
    headers = "\n".join(filter(None, [
        f"Subject: {email.subject}",
        f"From: {email.sender}",
        reply_to_line,
        date_line,
    ]))

    return f"""Analyze this email for phishing. Return ONLY valid JSON, no markdown.

{headers}
Body: {truncated_body}

Check: sender/domain mismatch, urgency language, credential/money requests, suspicious links, grammar issues, brand impersonation, reply-to mismatch.
Score 0-100 (0=safe,100=malicious). Verdict: 0-39="Safe", 40-69="Suspicious", 70-100="Malicious".

{{"score":<int>,"verdict":"<Safe|Suspicious|Malicious>","reasoning":"<2-3 sentences>","flags":["<red flag>"]}}"""


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(email: EmailRequest) -> JSONResponse:
    try:
        prompt = build_prompt(email)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        if response.text is None:
            raise ValueError("Empty response from Gemini")
        raw = response.text.strip()
        # Gemini sometimes wraps JSON in markdown fences despite instructions
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # drop the opening fence line
            raw = raw.rsplit("```", 1)[0]  # drop the closing fence
        result = json.loads(raw)

        score = int(result["score"])
        verdict = result["verdict"]
        reasoning = result["reasoning"]
        flags = result.get("flags", [])

        logger.info("Analysis complete: score=%d verdict=%s", score, verdict)

        return JSONResponse(
            content={
                "score": score,
                "verdict": verdict,
                "reasoning": reasoning,
                "flags": flags,
            }
        )
    except json.JSONDecodeError:
        logger.error("Gemini returned non-JSON response")
        return JSONResponse(
            status_code=502,
            content={"error": "AI returned an unexpected response format. Please try again."},
        )
    except Exception as e:
        # Surface rate-limit errors clearly rather than hiding them as generic 500s
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            logger.warning("Gemini rate limit hit")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit reached. Please wait a moment and try again."},
            )
        logger.error("Unexpected error during analysis: %s", type(e).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "An internal error occurred. Please try again."},
        )
