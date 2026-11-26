// Frontend logic. The API key is only ever sent to our own Flask server;
// it is never stored in JavaScript, localStorage, or the page.

const keyInput = document.getElementById("api-key");
const saveKeyBtn = document.getElementById("save-key");
const clearKeyBtn = document.getElementById("clear-key");
const keyStatus = document.getElementById("key-status");
const questionInput = document.getElementById("question");
const askBtn = document.getElementById("ask");
const resultBox = document.getElementById("result");
const errorBox = document.getElementById("error");

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function setKeyStatus(hasKey) {
  keyStatus.textContent = hasKey
    ? "Key saved on the server (not stored in your browser)."
    : "No key saved yet.";
  keyStatus.classList.toggle("ok", hasKey);
}

async function api(path, method, body) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try {
    data = await response.json();
  } catch (_) {
    /* non-JSON response */
  }
  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status}).`);
  }
  return data;
}

async function saveKey() {
  clearError();
  const key = keyInput.value.trim();
  if (!key) return showError("Please enter your Gemini API key.");
  saveKeyBtn.disabled = true;
  try {
    await api("/api/key", "POST", { key });
    keyInput.value = ""; // clear the field right after saving
    setKeyStatus(true);
  } catch (err) {
    showError(err.message);
  } finally {
    saveKeyBtn.disabled = false;
  }
}

async function clearKey() {
  clearError();
  try {
    await api("/api/key", "DELETE");
    keyInput.value = "";
    setKeyStatus(false);
  } catch (err) {
    showError(err.message);
  }
}

async function ask() {
  clearError();
  const question = questionInput.value.trim();
  if (!question) return showError("Please type a question.");

  askBtn.disabled = true;
  resultBox.textContent = "...";
  try {
    const data = await api("/api/ask", "POST", { question });
    // Show ONLY the JSON, e.g. {"answer":"Yes"}
    resultBox.textContent = JSON.stringify({ answer: data.answer });
  } catch (err) {
    resultBox.textContent = '{"answer":""}';
    showError(err.message);
  } finally {
    askBtn.disabled = false;
  }
}

saveKeyBtn.addEventListener("click", saveKey);
clearKeyBtn.addEventListener("click", clearKey);
askBtn.addEventListener("click", ask);
keyInput.addEventListener("keydown", (e) => e.key === "Enter" && saveKey());
questionInput.addEventListener("keydown", (e) => e.key === "Enter" && ask());

// On load, ask the server whether a key is already available.
fetch("/api/status")
  .then((r) => r.json())
  .then((d) => setKeyStatus(d.has_key))
  .catch(() => {});
