"""Gemini integration: explains static-analysis findings in plain English."""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY from a .env file

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip().strip('"').strip("'")
FALLBACK_MODEL = "gemini-flash-lite-latest"  # tried if the main model is busy
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
RETRY_CODES = (429, 500, 503)  # temporary problems worth retrying
ATTEMPTS = 2  # tries per model
WAIT_SECONDS = 2
TOTAL_SECONDS = 25  # give up on the AI after this long (static results still show)
REQUEST_SECONDS = 20  # longest we wait for a single reply


class LLMError(Exception):
    """Raised for any problem getting an explanation (missing key, network, API)."""


def explain_issues(issues, source):
    """Return a plain-English explanation and fix suggestions as text."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise LLMError("GEMINI_API_KEY not set (add it to a .env file).")

    findings = "\n".join(f"- Line {i.line} [{i.severity}] {i.kind}: {i.description}"
                         for i in issues)
    prompt = (
        "You are a friendly code reviewer helping a beginner.\n"
        "Below is a Python file and issues found by static analysis. For each issue, "
        "explain in simple English why it is a problem and suggest a short fix "
        "(with a tiny code example if useful). Format as Markdown with one short "
        "section per issue, titled with its line number. Be concise.\n\n"
        f"Issues:\n{findings}\n\nCode:\n```python\n{source}\n```"
    )

    deadline = time.monotonic() + TOTAL_SECONDS
    models = [MODEL] if MODEL == FALLBACK_MODEL else [MODEL, FALLBACK_MODEL]
    last_error = "No response."
    for model in models:
        for attempt in range(ATTEMPTS):
            remaining = deadline - time.monotonic()
            if remaining < 3:
                raise LLMError(f"Gemini took too long (over {TOTAL_SECONDS}s). Last status: {last_error}")
            try:
                response = requests.post(
                    f"{BASE_URL}/{model}:generateContent",
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=min(REQUEST_SECONDS, remaining),
                )
            except requests.Timeout:
                last_error = f"Model '{model}' did not answer in time."
                break  # too slow: try the next model instead of waiting again
            except requests.RequestException as exc:
                raise LLMError(f"Could not reach Gemini API ({type(exc).__name__}).") from exc

            if response.status_code == 200:
                try:
                    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                except (KeyError, IndexError, ValueError) as exc:
                    raise LLMError("Unexpected response from Gemini API.") from exc

            try:
                detail = response.json()["error"]["message"]
            except Exception:
                detail = response.text[:200]
            last_error = f"HTTP {response.status_code} for model '{model}': {detail}"

            if response.status_code in RETRY_CODES:
                if attempt < ATTEMPTS - 1:
                    time.sleep(WAIT_SECONDS)  # wait a moment, then try again
                continue
            if response.status_code == 404:
                break  # model not available to this key: try the next model
            raise LLMError(last_error)  # bad key, bad request, etc.: no point retrying

    raise LLMError(last_error)