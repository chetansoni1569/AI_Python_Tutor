"""
One-Word AI Tutor (Gemini)  -  complete, runnable version

Ask any question, get exactly one word back as JSON:
    {"answer": "Yes"}

Run in the terminal:   python tutor.py
Run with a window:     python tutor.py --gui

API key: read from the GEMINI_API_KEY environment variable if set,
otherwise you are asked for it (hidden input / password field).
The key is kept in memory only and is never written to disk.
"""

import argparse
import json
import os
import re
import sys
import time
from getpass import getpass

from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3          # tries per question for temporary errors
RETRY_DELAY_SECONDS = 2  # wait between tries

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


# --------------------------------------------------------------------------
# Core logic (shared by the CLI and the GUI)
# --------------------------------------------------------------------------

def to_one_word(text: str) -> str:
    """Keep only the first word, strip punctuation, capitalize it."""
    words = re.findall(r"[A-Za-z0-9'-]+", text or "")
    return words[0].capitalize() if words else "Unknown"


def make_client(api_key: str) -> "genai.Client":
    return genai.Client(api_key=api_key)


def ask(client, question: str) -> str:
    """
    Send the question to Gemini and return a JSON string that is always
    exactly like {"answer": "Word"}. Raises an exception on hard failures.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return _build_json(response)
        except Exception as exc:
            last_error = exc
            if not _is_temporary(exc) or attempt == MAX_RETRIES:
                break
            time.sleep(RETRY_DELAY_SECONDS)
    raise last_error


def _build_json(response) -> str:
    """Parse the model reply and rebuild the JSON so the format is guaranteed."""
    text = getattr(response, "text", None)  # None if the reply was blocked/empty
    if not text:
        return json.dumps({"answer": "Unknown"})
    try:
        raw_answer = json.loads(text).get("answer", "")
    except (json.JSONDecodeError, AttributeError):
        raw_answer = text
    return json.dumps({"answer": to_one_word(str(raw_answer))})


def _is_temporary(exc: Exception) -> bool:
    """Rate limits and server hiccups are worth retrying; bad keys are not."""
    code = getattr(exc, "code", None)
    return code in (429, 500, 502, 503, 504)


def error_json(exc: Exception) -> str:
    """Friendly, still-JSON error output."""
    code = getattr(exc, "code", None)
    if code in (400, 401, 403):
        message = "InvalidKeyOrRequest"
    elif code == 429:
        message = "RateLimited"
    elif isinstance(exc, (ConnectionError, TimeoutError)):
        message = "NetworkError"
    else:
        message = type(exc).__name__
    return json.dumps({"error": message})


def get_api_key_cli() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        key = getpass("Enter your Gemini API key (input hidden): ").strip()
    if not key:
        sys.exit("No API key provided. Exiting.")
    return key


# --------------------------------------------------------------------------
# Command-line interface
# --------------------------------------------------------------------------

def run_cli() -> None:
    client = make_client(get_api_key_cli())
    print("One-Word AI Tutor ready. Type a question (or 'quit' to exit).\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue

        try:
            print(ask(client, question))
        except Exception as exc:
            print(error_json(exc))
            print(f"({exc})", file=sys.stderr)


# --------------------------------------------------------------------------
# Simple window (Tkinter - ships with Python, nothing extra to install)
# --------------------------------------------------------------------------

def run_gui() -> None:
    import threading
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("One-Word AI Tutor")
    root.geometry("460x300")
    root.resizable(False, False)

    state = {"client": None}

    # --- API key row (password field hides what you type) ---
    tk.Label(root, text="Gemini API key:").pack(anchor="w", padx=12, pady=(12, 0))
    key_row = tk.Frame(root)
    key_row.pack(fill="x", padx=12)
    key_entry = tk.Entry(key_row, show="*")
    key_entry.pack(side="left", fill="x", expand=True)
    key_entry.insert(0, os.environ.get("GEMINI_API_KEY", ""))

    def save_key():
        key = key_entry.get().strip()
        if not key:
            messagebox.showwarning("Missing key", "Please enter your API key.")
            return
        state["client"] = make_client(key)
        key_status.config(text="Key set (kept in memory only).", fg="green")

    tk.Button(key_row, text="Set key", command=save_key).pack(side="left", padx=(6, 0))
    key_status = tk.Label(root, text="No key set yet.", fg="gray")
    key_status.pack(anchor="w", padx=12)

    # --- Question row ---
    tk.Label(root, text="Your question:").pack(anchor="w", padx=12, pady=(12, 0))
    q_row = tk.Frame(root)
    q_row.pack(fill="x", padx=12)
    q_entry = tk.Entry(q_row)
    q_entry.pack(side="left", fill="x", expand=True)

    # --- Output ---
    output = tk.Label(root, text='{"answer": ""}', font=("Courier", 16), pady=24)
    output.pack()

    def do_ask(event=None):
        question = q_entry.get().strip()
        if state["client"] is None:
            messagebox.showwarning("Missing key", "Set your API key first.")
            return
        if not question:
            return
        ask_button.config(state="disabled")
        output.config(text="...")

        def worker():
            try:
                result = ask(state["client"], question)
            except Exception as exc:
                result = error_json(exc)
            # Update the window from the main thread.
            root.after(0, lambda: (output.config(text=result),
                                   ask_button.config(state="normal")))

        threading.Thread(target=worker, daemon=True).start()

    ask_button = tk.Button(q_row, text="Ask", command=do_ask)
    ask_button.pack(side="left", padx=(6, 0))
    q_entry.bind("<Return>", do_ask)

    if key_entry.get().strip():
        save_key()

    root.mainloop()


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="One-word AI tutor powered by Gemini.")
    parser.add_argument("--gui", action="store_true", help="open a simple window instead of the terminal")
    args = parser.parse_args()
    run_gui() if args.gui else run_cli()


if __name__ == "__main__":
    main()
