# One-Word AI Tutor (Flask + Gemini)

A local web app. Type any question, get exactly one word back as JSON:

    {"answer":"Yes"}

## 1. Get a Gemini API key
Create one at https://aistudio.google.com/apikey (keep it private).

## 2. Install and run
    pip install -r requirements.txt
    python app.py

## 3. Open the app
    http://127.0.0.1:5050

Paste your key, click **Save key**, type a question, click **Ask**.

## Optional settings (environment variables)
| Variable         | Purpose                                   | Default            |
|------------------|-------------------------------------------|--------------------|
| GEMINI_API_KEY   | Preload a key so you don't paste it       | (none)             |
| GEMINI_MODEL     | Gemini model to use                       | gemini-2.5-flash   |
| PORT             | Port for the local server                 | 5050               |

Examples:
- macOS/Linux: `GEMINI_API_KEY="your-key" python app.py`
- Windows PowerShell: `$env:GEMINI_API_KEY="your-key"; python app.py`

## How the key stays safe
- The key goes from the page to the Flask server once, over localhost.
- It is held in server memory only: never written to disk, never sent back
  to the browser, never present in the JavaScript.
- The browser keeps only a random HttpOnly session cookie.
- The server listens on 127.0.0.1, so only your computer can reach it.
- Stopping the server (Ctrl+C) forgets the key.

## Files
    app.py               Flask backend + Gemini call
    templates/index.html Page layout
    static/style.css     Styling
    static/script.js     Browser logic (talks only to this server)
    requirements.txt     Dependencies

## Troubleshooting
- "Check that your API key is valid": re-paste the key and save again.
- "Rate limit or quota reached": wait a minute (free tier has limits).
- "Model not found": set GEMINI_MODEL to a model available to your key.
- Port in use: `PORT=5051 python app.py`.
