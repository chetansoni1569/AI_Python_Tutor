"""
One-Word AI Tutor - Flask backend (talks to the real Gemini API)

Run:
    pip install -r requirements.txt
    python app.py
Then open:  http://127.0.0.1:5050

Security notes:
  * The Gemini key is sent from the browser to this server ONCE, then kept
    in server memory only. It is never written to disk and never sent back
    to the browser or embedded in any JavaScript.
  * The browser only holds a random, HttpOnly session cookie.
  * The server listens on 127.0.0.1 (this computer only).
"""

import json
import os
import re
import secrets
import time

from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import errors, types

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "5050"))
MAX_QUESTION_CHARS = 1000
MAX_RETRIES = 2  # extra tries for temporary server errors

SYSTEM_PROMPT = (
    "You are a tutor that answers with exactly ONE word. "
    'Respond only with JSON of the form {"answer": "<one word>"}. '
    "The value must be a single word: no spaces, no punctuation, no explanation. "
    "If the question is yes/no, answer Yes or No. "
    "If it cannot be answered in one word, answer Unknown."
)

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"answer": {"type": "STRING"}},
    "required": ["answer"],
}

app = Flask(__name__)

# session id -> Gemini API key (kept in memory only, never persisted)
KEYS: dict[str, str] = {}
COOKIE = "tutor_sid"
ENV_KEY = os.environ.get("GEMINI_API_KEY", "").strip()  # optional default key


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def error(message: str, status: int):
    return jsonify({"error": message}), status


def current_key():
    """API key for this browser session (or the env-var fallback)."""
    return KEYS.get(request.cookies.get(COOKIE, "")) or ENV_KEY or None


def to_one_word(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9'-]+", text or "")
    return words[0].capitalize() if words else "Unknown"


def ask_gemini(api_key: str, question: str) -> str:
    """Call the real Gemini API and return ONE word."""
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0,
        # Thinking tokens would eat the output budget and could cause empty
        # replies, so turn thinking off (supported by gemini-2.5-flash).
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=question, config=config
            )
            break
        except errors.APIError as exc:
            if exc.code in (500, 502, 503, 504) and attempt < MAX_RETRIES:
                time.sleep(1.5)
                continue
            raise

    text = getattr(response, "text", None)
    if not text:  # blocked or empty reply
        return "Unknown"
    try:
        raw = json.loads(text).get("answer", "")
    except (json.JSONDecodeError, AttributeError):
        raw = text
    return to_one_word(str(raw))


@app.before_request
def basic_request_checks():
    """Block cross-site requests: state-changing calls must come from this app."""
    if request.method in ("POST", "DELETE"):
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            return error("Forbidden origin.", 403)
        if request.method == "POST" and not request.is_json:
            return error("Expected JSON request.", 415)


@app.after_request
def security_headers(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'"
    )
    return resp


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify({"has_key": current_key() is not None})


@app.post("/api/key")
def save_key():
    data = request.get_json(silent=True) or {}
    key = str(data.get("key", "")).strip()
    if not key:
        return error("Please enter your Gemini API key.", 400)
    if len(key) > 200 or re.search(r"\s", key):
        return error("That doesn't look like a valid API key.", 400)

    sid = request.cookies.get(COOKIE)
    if not sid or sid not in KEYS:
        sid = secrets.token_urlsafe(32)
    KEYS[sid] = key

    resp = jsonify({"ok": True})
    resp.set_cookie(COOKIE, sid, httponly=True, samesite="Strict")
    return resp


@app.delete("/api/key")
def delete_key():
    KEYS.pop(request.cookies.get(COOKIE, ""), None)
    return jsonify({"ok": True})


@app.post("/api/ask")
def ask():
    key = current_key()
    if not key:
        return error("Please save your Gemini API key first.", 401)

    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    if not question:
        return error("Please type a question.", 400)
    if len(question) > MAX_QUESTION_CHARS:
        return error(f"Question is too long (max {MAX_QUESTION_CHARS} characters).", 400)

    try:
        answer = ask_gemini(key, question)
    except errors.APIError as exc:
        code = exc.code
        if code in (400, 401, 403):
            return error("Gemini rejected the request. Check that your API key is valid.", 401)
        if code == 404:
            return error(f"Model '{MODEL}' was not found. Set GEMINI_MODEL to a valid model.", 502)
        if code == 429:
            return error("Rate limit or quota reached. Wait a moment and try again.", 429)
        return error("Gemini is having trouble right now. Please try again.", 502)
    except Exception:
        return error("Could not reach Gemini. Check your internet connection.", 502)

    return jsonify({"answer": answer})


if __name__ == "__main__":
    print(f"AI Tutor running at http://{HOST}:{PORT}  (press Ctrl+C to stop)")
    app.run(host=HOST, port=PORT, debug=False)
