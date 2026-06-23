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
  body.textContent = text;
  bubble.appendChild(body);

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
  return { row, bubble, body };
}

function createLiveBubble() {
  const row = document.createElement("div");
  row.className = "message bot";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const tag = document.createElement("div");
  tag.className = "mode-tag hidden";
  bubble.appendChild(tag);

  const body = document.createElement("div");
  body.className = "stream-body";
  bubble.appendChild(body);

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
  return { row, tag, body };
}

function setBusy(busy) {
  sendBtn.disabled = busy;
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

async function streamChat(form) {
  const res = await fetch(`${SERVER_URL}/chat`, { method: "POST", body: form });
  if (!res.ok || !res.body) throw new Error(`Server responded ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let live = null;
  let text = "";
  let sawError = false;

  const flush = () => {
    live.body.textContent = text;
    scrollToBottom();
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop();

    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith("data:")) continue;

      let evt;
      try {
        evt = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }

      if (evt.type === "token") {
        if (!live) {
          typingEl.classList.add("hidden");
          live = createLiveBubble();
        }
        text += evt.text;
        flush();
      } else if (evt.type === "error") {
        sawError = true;
        if (!live) {
          typingEl.classList.add("hidden");
          live = createLiveBubble();
        }
        live.row.classList.remove("bot");
        live.row.classList.add("error");
        text += evt.message;
        flush();
      } else if (evt.type === "done") {
        if (!live) {
          typingEl.classList.add("hidden");
          live = createLiveBubble();
          if (evt.text) {
            text = evt.text;
            flush();
          }
        }
        if (evt.mode && !sawError) {
          live.tag.textContent = evt.mode;
          live.tag.classList.remove("hidden");
        }
      }
    }
  }
}

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
  typingEl.classList.remove("hidden");
  scrollToBottom();
  try {
    await streamChat(form);
  } catch (err) {
    typingEl.classList.add("hidden");
    addMessage(`Could not reach the server: ${err.message}`, "error");
  } finally {
    typingEl.classList.add("hidden");
    setBusy(false);
  }
});
