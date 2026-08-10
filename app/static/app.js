const elements = {
  composer: document.querySelector("#composer"),
  input: document.querySelector("#question-input"),
  sendButton: document.querySelector("#send-button"),
  characterCount: document.querySelector("#character-count"),
  welcome: document.querySelector("#welcome"),
  messageList: document.querySelector("#message-list"),
  conversation: document.querySelector("#conversation"),
  settingsDialog: document.querySelector("#settings-dialog"),
  settingsForm: document.querySelector("#settings-form"),
  apiKeyInput: document.querySelector("#api-key-input"),
  userIdInput: document.querySelector("#user-id-input"),
  toggleKey: document.querySelector("#toggle-key"),
  profileUser: document.querySelector("#profile-user"),
  avatarLabel: document.querySelector("#avatar-label"),
  keyState: document.querySelector("#key-state"),
  serviceStatus: document.querySelector("#service-status"),
  redisStatus: document.querySelector("#redis-status"),
  serviceDot: document.querySelector("#service-dot"),
  redisDot: document.querySelector("#redis-dot"),
  refreshStatus: document.querySelector("#refresh-status"),
  newChatButton: document.querySelector("#new-chat-button"),
  toast: document.querySelector("#toast"),
  sidebar: document.querySelector("#sidebar"),
  sidebarBackdrop: document.querySelector("#sidebar-backdrop"),
  menuButton: document.querySelector("#menu-button"),
  modelName: document.querySelector("#model-name"),
  modelState: document.querySelector("#model-state"),
  modelDisclaimer: document.querySelector("#model-disclaimer"),
};

const storageKeys = {
  apiKey: "day12_agent_api_key",
  userId: "day12_agent_user_id",
};

const state = {
  apiKey: sessionStorage.getItem(storageKeys.apiKey) || "",
  userId: sessionStorage.getItem(storageKeys.userId) || createUserId(),
  busy: false,
  toastTimer: null,
};

function createUserId() {
  const suffix = crypto.randomUUID?.().slice(0, 8) || Math.random().toString(36).slice(2, 10);
  return `web-${suffix}`;
}

function updateProfile() {
  elements.profileUser.textContent = state.userId;
  elements.avatarLabel.textContent = state.userId.charAt(0) || "U";
  elements.keyState.textContent = state.apiKey ? "API key đã cấu hình" : "Chưa cấu hình API key";
  elements.apiKeyInput.value = state.apiKey;
  elements.userIdInput.value = state.userId;
}

function openSettings() {
  updateProfile();
  elements.settingsDialog.showModal();
  window.setTimeout(() => (state.apiKey ? elements.userIdInput : elements.apiKeyInput).focus(), 50);
}

function saveSettings(event) {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();

  const apiKey = elements.apiKeyInput.value.trim();
  const userId = elements.userIdInput.value.trim();
  if (!apiKey || !userId) {
    showToast("Vui lòng nhập cả API key và User ID.", true);
    return;
  }

  state.apiKey = apiKey;
  state.userId = userId;
  sessionStorage.setItem(storageKeys.apiKey, apiKey);
  sessionStorage.setItem(storageKeys.userId, userId);
  updateProfile();
  elements.settingsDialog.close();
  showToast("Đã lưu kết nối trong session hiện tại.");
  elements.input.focus();
}

function setStatus(kind, online, label) {
  const status = kind === "service" ? elements.serviceStatus : elements.redisStatus;
  const dot = kind === "service" ? elements.serviceDot : elements.redisDot;
  status.textContent = label;
  dot.className = `status-dot ${online ? "online" : "offline"}`;
}

async function refreshSystemStatus() {
  elements.serviceDot.className = "status-dot pending";
  elements.redisDot.className = "status-dot pending";
  elements.serviceStatus.textContent = "Đang kiểm tra";
  elements.redisStatus.textContent = "Đang kiểm tra";

  const [health, ready] = await Promise.allSettled([
    fetch("/health", { cache: "no-store" }),
    fetch("/ready", { cache: "no-store" }),
  ]);

  const healthOnline = health.status === "fulfilled" && health.value.ok;
  const redisOnline = ready.status === "fulfilled" && ready.value.ok;
  setStatus("service", healthOnline, healthOnline ? "Online" : "Unavailable");
  setStatus("redis", redisOnline, redisOnline ? "Connected" : "Disconnected");
}

async function refreshCapabilities() {
  try {
    const response = await fetch("/capabilities", { cache: "no-store" });
    if (!response.ok) throw new Error("capabilities unavailable");
    const data = await response.json();
    elements.modelName.textContent = data.provider === "groq" ? "Groq · Cloud Copilot" : "Mock LLM";
    elements.modelState.textContent = data.provider === "groq" ? data.model : "offline";
    const modes = [
      data.rag ? "Local RAG" : null,
      data.web_search ? "Web Search" : null,
      data.web_scrape ? "Deep Scrape" : null,
    ].filter(Boolean);
    elements.modelDisclaimer.textContent = `${data.model} · ${modes.join(" + ") || "Không dùng retrieval"} · Luôn kiểm tra các nguồn quan trọng.`;
  } catch (_error) {
    elements.modelName.textContent = "Cloud Copilot";
    elements.modelState.textContent = "unavailable";
    elements.modelDisclaimer.textContent = "Không đọc được cấu hình model. Hãy kiểm tra trạng thái service.";
  }
}

function resizeComposer() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 160)}px`;
  const length = elements.input.value.length;
  elements.characterCount.textContent = `${length} / 2000`;
  elements.sendButton.disabled = state.busy || !elements.input.value.trim();
}

function showConversation() {
  elements.welcome.hidden = true;
  elements.messageList.classList.add("active");
}

function formatTime() {
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(new Date());
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInlineMarkdown(value) {
  const codeTokens = [];
  let rendered = escapeHtml(value).replace(/`([^`\n]+)`/g, (_match, code) => {
    const token = `@@INLINE_CODE_${codeTokens.length}@@`;
    codeTokens.push(`<code>${code}</code>`);
    return token;
  });
  rendered = rendered
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  codeTokens.forEach((code, index) => {
    rendered = rendered.replace(`@@INLINE_CODE_${index}@@`, code);
  });
  return rendered;
}

function tableCells(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function isTableDivider(line) {
  const cells = tableCells(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderMarkdown(markdown) {
  const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
  const output = [];
  let paragraph = [];
  let index = 0;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p>${paragraph.map(renderInlineMarkdown).join("<br>")}</p>`);
    paragraph = [];
  };

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      flushParagraph();
      const language = trimmed.slice(3).trim().match(/^[a-z0-9_+-]+/i)?.[0] || "";
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      output.push(`<pre><code${language ? ` class="language-${language}"` : ""}>${escapeHtml(code.join("\n"))}</code></pre>`);
      index += 1;
      continue;
    }

    if (trimmed.includes("|") && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      flushParagraph();
      const headers = tableCells(trimmed);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }
      const head = headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("");
      const body = rows.map((row) => `<tr>${headers.map((_header, cellIndex) => `<td>${renderInlineMarkdown(row[cellIndex] || "")}</td>`).join("")}</tr>`).join("");
      output.push(`<div class="markdown-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`);
      continue;
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      const level = Math.min(heading[1].length + 2, 6);
      output.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      index += 1;
      continue;
    }

    const unordered = trimmed.match(/^[-*+]\s+(.+)$/);
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      flushParagraph();
      const tag = ordered ? "ol" : "ul";
      const items = [];
      while (index < lines.length) {
        const match = lines[index].trim().match(tag === "ol" ? /^\d+[.)]\s+(.+)$/ : /^[-*+]\s+(.+)$/);
        if (!match) break;
        items.push(`<li>${renderInlineMarkdown(match[1])}</li>`);
        index += 1;
      }
      output.push(`<${tag}>${items.join("")}</${tag}>`);
      continue;
    }

    if (/^>{1}\s?/.test(trimmed)) {
      flushParagraph();
      const quotes = [];
      while (index < lines.length && /^>{1}\s?/.test(lines[index].trim())) {
        quotes.push(lines[index].trim().replace(/^>{1}\s?/, ""));
        index += 1;
      }
      output.push(`<blockquote>${quotes.map(renderInlineMarkdown).join("<br>")}</blockquote>`);
      continue;
    }

    if (/^([-*_])\1{2,}$/.test(trimmed)) {
      flushParagraph();
      output.push("<hr>");
      index += 1;
      continue;
    }

    if (!trimmed) {
      flushParagraph();
    } else {
      paragraph.push(trimmed);
    }
    index += 1;
  }
  flushParagraph();
  return output.join("");
}

function addMessage(role, text, metrics = null) {
  showConversation();
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? state.userId.charAt(0) || "U" : "✦";

  const content = document.createElement("div");
  const heading = document.createElement("div");
  heading.className = "message-heading";
  const name = document.createElement("span");
  name.textContent = role === "user" ? "Bạn" : "Day 12 Agent";
  const time = document.createElement("time");
  time.textContent = formatTime();
  heading.append(name, time);

  const body = document.createElement("div");
  body.className = "message-body";
  if (role === "assistant") {
    body.innerHTML = renderMarkdown(text);
  } else {
    body.textContent = text;
  }
  content.append(heading, body);

  if (metrics) {
    const metricRow = document.createElement("div");
    metricRow.className = "message-metrics";
    const values = [
      `${metrics.tokens.in} input tokens`,
      `${metrics.tokens.out} output tokens`,
      `$${Number(metrics.cost_usd).toFixed(8)}`,
      `${metrics.history_length} previous messages`,
      metrics.provider ? `${metrics.provider} · ${metrics.model}` : null,
      metrics.knowledge_mode ? `knowledge: ${metrics.knowledge_mode}` : null,
      metrics.routing?.reason ? `route: ${metrics.routing.reason}` : null,
    ].filter(Boolean);
    values.forEach((value) => {
      const chip = document.createElement("span");
      chip.textContent = value;
      metricRow.append(chip);
    });
    content.append(metricRow);

    if (metrics.sources?.length) {
      const sources = document.createElement("div");
      sources.className = "message-sources";
      const label = document.createElement("strong");
      label.textContent = "Nguồn";
      sources.append(label);
      metrics.sources.forEach((source, index) => {
        const item = document.createElement(source.type === "web" ? "a" : "span");
        item.textContent = `[${index + 1}] ${source.title}`;
        if (source.type === "web") {
          item.href = source.uri;
          item.target = "_blank";
          item.rel = "noopener noreferrer";
        } else {
          item.title = source.uri;
        }
        sources.append(item);
      });
      content.append(sources);
    }

    if (metrics.warning) {
      const warning = document.createElement("p");
      warning.className = "message-warning";
      warning.textContent = metrics.warning;
      content.append(warning);
    }

    if (metrics.trace?.steps?.length) {
      const trace = document.createElement("details");
      trace.className = "message-trace";
      const summary = document.createElement("summary");
      summary.textContent = `Trace ${metrics.trace.id} · ${Number(metrics.trace.total_ms).toFixed(0)} ms`;
      trace.append(summary);

      const steps = document.createElement("ol");
      metrics.trace.steps.forEach((step) => {
        const item = document.createElement("li");
        item.className = `trace-step ${step.status || "ok"}`;
        const label = document.createElement("strong");
        label.textContent = step.label;
        const meta = document.createElement("span");
        const duration = step.duration_ms == null ? "verified" : `${Number(step.duration_ms).toFixed(1)} ms`;
        meta.textContent = step.detail ? `${duration} · ${step.detail}` : duration;
        item.append(label, meta);
        steps.append(item);
      });
      trace.append(steps);
      content.append(trace);
    }
  }

  article.append(avatar, content);
  elements.messageList.append(article);
  scrollToLatest();
  return article;
}

function addTypingIndicator() {
  const article = addMessage("assistant", "");
  article.dataset.typing = "true";
  const body = article.querySelector(".message-body");
  body.innerHTML = '<span class="typing-dots"><i></i><i></i><i></i></span>';
  return article;
}

function scrollToLatest() {
  requestAnimationFrame(() => {
    elements.conversation.scrollTo({ top: elements.conversation.scrollHeight, behavior: "smooth" });
  });
}

function errorMessage(status, detail) {
  const messages = {
    400: "Yêu cầu chưa đúng định dạng. Hãy thử nhập lại câu hỏi.",
    401: "API key chưa đúng hoặc chưa được cấu hình.",
    402: "User này đã vượt ngân sách tháng.",
    422: "Câu hỏi không hợp lệ hoặc đang để trống.",
    429: "Bạn gửi quá nhanh. Hãy chờ khoảng một phút rồi thử lại.",
    503: "Agent đang tạm ngừng nhận traffic hoặc Redis chưa sẵn sàng.",
  };
  return messages[status] || detail || "Không thể kết nối tới agent lúc này.";
}

async function askQuestion(question) {
  if (!state.apiKey) {
    showToast("Hãy cấu hình API key trước khi bắt đầu.", true);
    openSettings();
    return;
  }

  state.busy = true;
  resizeComposer();
  addMessage("user", question);
  const typing = addTypingIndicator();

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": state.apiKey,
        "X-User-Id": state.userId,
      },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json().catch(() => ({}));
    typing.remove();

    if (!response.ok) {
      addMessage("assistant", errorMessage(response.status, payload.detail));
      if (response.status === 401) openSettings();
      return;
    }

    addMessage("assistant", payload.answer, payload);
  } catch (error) {
    typing.remove();
    addMessage("assistant", "Không thể kết nối tới service. Hãy kiểm tra trạng thái cloud và thử lại.");
    setStatus("service", false, "Unavailable");
  } finally {
    state.busy = false;
    resizeComposer();
    elements.input.focus();
  }
}

function submitQuestion(event) {
  event.preventDefault();
  const question = elements.input.value.trim();
  if (!question || state.busy) return;
  elements.input.value = "";
  resizeComposer();
  askQuestion(question);
}

function resetConversation() {
  elements.messageList.replaceChildren();
  elements.messageList.classList.remove("active");
  elements.welcome.hidden = false;
  state.userId = createUserId();
  sessionStorage.setItem(storageKeys.userId, state.userId);
  updateProfile();
  elements.input.value = "";
  resizeComposer();
  closeSidebar();
  elements.input.focus();
  showToast("Đã bắt đầu một cuộc trò chuyện mới.");
}

function showToast(message, isError = false) {
  window.clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast visible${isError ? " error" : ""}`;
  state.toastTimer = window.setTimeout(() => {
    elements.toast.className = "toast";
  }, 3200);
}

function openSidebar() {
  elements.sidebar.classList.add("open");
  elements.sidebarBackdrop.classList.add("visible");
}

function closeSidebar() {
  elements.sidebar.classList.remove("open");
  elements.sidebarBackdrop.classList.remove("visible");
}

elements.composer.addEventListener("submit", submitQuestion);
elements.input.addEventListener("input", resizeComposer);
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});
elements.settingsForm.addEventListener("submit", saveSettings);
elements.toggleKey.addEventListener("click", () => {
  const reveal = elements.apiKeyInput.type === "password";
  elements.apiKeyInput.type = reveal ? "text" : "password";
  elements.toggleKey.textContent = reveal ? "Ẩn" : "Hiện";
});
document.querySelectorAll("#open-settings, #top-settings").forEach((button) => button.addEventListener("click", openSettings));
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.input.value = button.dataset.prompt;
    resizeComposer();
    elements.input.focus();
  });
});
elements.refreshStatus.addEventListener("click", refreshSystemStatus);
elements.newChatButton.addEventListener("click", resetConversation);
elements.menuButton.addEventListener("click", openSidebar);
elements.sidebarBackdrop.addEventListener("click", closeSidebar);

sessionStorage.setItem(storageKeys.userId, state.userId);
updateProfile();
resizeComposer();
refreshSystemStatus();
refreshCapabilities();
window.setInterval(refreshSystemStatus, 30000);
