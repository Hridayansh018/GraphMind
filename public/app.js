const SERVER_URL = (window.SERVER_URL || "http://localhost:8000").replace(/\/$/, "");

const USER_ID = (() => {
  let id = localStorage.getItem("chatbot_user_id");
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
    localStorage.setItem("chatbot_user_id", id);
  }
  return id;
})();

const messagesEl = document.getElementById("messages");
const typingEl = document.getElementById("typing");
const composerEl = document.getElementById("composer");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const fileInput = document.getElementById("fileInput");
const fileChip = document.getElementById("fileChip");
const fileNameEl = document.getElementById("fileName");
const removeFileBtn = document.getElementById("removeFile");
const jdField = document.getElementById("jdField");
const jobDescriptionInput = document.getElementById("jobDescription");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

function scrollToBottom() {
  messagesEl.parentElement.scrollTop = messagesEl.parentElement.scrollHeight;
}

function addMessage(text, role, modeLabel) {
  const row = document.createElement("div");
  row.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (modeLabel) {
    const tag = document.createElement("div");
    tag.className = "mode-tag";
    tag.textContent = modeLabel;
    bubble.appendChild(tag);
  }

  const body = document.createElement("div");
  if (typeof text === "string") {
    body.textContent = text;
  } else {
    const pre = document.createElement("pre");
    pre.style.margin = "0";
    pre.style.whiteSpace = "pre-wrap";
    pre.textContent = JSON.stringify(text, null, 2);
    body.appendChild(pre);
  }
  bubble.appendChild(body);

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  typingEl.classList.toggle("hidden", !busy);
  if (busy) scrollToBottom();
}

async function checkHealth() {
  try {
    const res = await fetch(`${SERVER_URL}/health`);
    if (!res.ok) throw new Error();
    statusDot.className = "status-dot online";
    statusText.textContent = "Online";
  } catch {
    statusDot.className = "status-dot offline";
    statusText.textContent = "Offline";
  }
}

checkHealth();
setInterval(checkHealth, 30000);

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) {
    fileChip.classList.add("hidden");
    jdField.classList.add("hidden");
    return;
  }
  fileNameEl.textContent = file.name;
  fileChip.classList.remove("hidden");
  jdField.classList.remove("hidden");
});

removeFileBtn.addEventListener("click", () => {
  fileInput.value = "";
  fileChip.classList.add("hidden");
  jdField.classList.add("hidden");
  jobDescriptionInput.value = "";
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = `${messageInput.scrollHeight}px`;
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composerEl.requestSubmit();
  }
});

composerEl.addEventListener("submit", async (e) => {
  e.preventDefault();

  const message = messageInput.value.trim();
  if (!message) return;

  const file = fileInput.files[0];
  const jobDescription = jobDescriptionInput.value.trim();

  addMessage(message, "user");
  messageInput.value = "";
  messageInput.style.height = "auto";

  const form = new FormData();
  form.append("message", message);
  form.append("user_id", USER_ID);
  if (file) form.append("file", file);
  if (jobDescription) form.append("job_description", jobDescription);

  fileInput.value = "";
  fileChip.classList.add("hidden");
  jdField.classList.add("hidden");
  jobDescriptionInput.value = "";

  setBusy(true);
  try {
    const res = await fetch(`${SERVER_URL}/chat`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    const data = await res.json();
    const role = data.mode === "error" ? "error" : "bot";
    addMessage(data.reply, role, data.mode);
  } catch (err) {
    addMessage(`Could not reach the server: ${err.message}`, "error");
  } finally {
    setBusy(false);
  }
});
