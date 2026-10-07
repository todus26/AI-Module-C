// 화면 동작을 담당하는 스크립트.
// 서버(app.py)가 "한 줄에 JSON 하나" 형태로 조금씩 보내 주는 결과를 읽어서 화면에 바로바로 그린다.

const $ = (selector) => document.querySelector(selector);

const messagesEl = $("#messages");
const chatForm = $("#chatForm");
const chatInput = $("#chatInput");
const sendBtn = $("#sendBtn");
const ragBtn = $("#ragBtn");
const contractBtn = $("#contractBtn");
const reviewBtn = $("#reviewBtn");
const ragInput = $("#ragInput");
const contractInput = $("#contractInput");

let busy = false;      // 작업 중에는 버튼을 잠가서 동시에 여러 작업이 돌지 않게 한다
const chatHistory = []; // 일반 질문에서 LLM 에 함께 보낼 이전 대화


// ====================================================================
// 메시지 출력 도우미
// ====================================================================

/** 대화창에 말풍선을 하나 추가하고, 내용을 채울 .bubble 요소를 돌려준다. */
function addMessage(role, text = "") {
  const row = document.createElement("div");
  row.className = `msg msg-${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
  return bubble;
}

/** 사용자가 위로 스크롤해서 읽는 중이 아닐 때만 맨 아래로 내린다. */
function scrollToBottom(force = false) {
  const nearBottom =
    messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 120;
  if (force || nearBottom) messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addText(bubble, text) {
  const p = document.createElement("div");
  p.textContent = text;
  bubble.appendChild(p);
  scrollToBottom();
}

/** tqdm 진행률 이벤트를 화면의 진행 막대로 그린다. (같은 key 는 같은 막대를 갱신) */
function renderProgress(bubble, ev) {
  let block = bubble.querySelector(`.progress[data-key="${ev.key}"]`);
  if (!block) {
    block = document.createElement("div");
    block.className = "progress";
    block.dataset.key = ev.key;
    block.innerHTML =
      '<div class="progress-label"></div>' +
      '<div class="progress-bar-text"></div>' +
      '<div class="progress-track"><div class="progress-fill"></div></div>';
    bubble.appendChild(block);
  }
  block.querySelector(".progress-label").textContent = ev.label;
  block.querySelector(".progress-bar-text").textContent = ev.bar;
  block.querySelector(".progress-fill").style.width = `${ev.percent}%`;
  block.classList.toggle("finished", ev.percent >= 100);
  scrollToBottom();
}

function setBusy(value) {
  busy = value;
  [ragBtn, contractBtn, reviewBtn, sendBtn].forEach((el) => (el.disabled = value));
}


// ====================================================================
// 서버 통신
// ====================================================================

/** 서버가 흘려보내는 NDJSON 을 한 줄씩 읽어서 onEvent 로 넘긴다. */
async function streamNDJSON(url, options, onEvent) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`서버 오류 (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // 줄바꿈이 나올 때마다 한 건의 이벤트가 완성된 것이다
    let newline;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}

/** 작업 하나를 실행한다: 버튼 잠금 -> 요청 -> 결과 표시 -> 버튼 잠금 해제 */
async function runJob(url, options, bubble, onEvent) {
  setBusy(true);
  try {
    await streamNDJSON(url, options, (ev) => {
      if (ev.type === "error") {
        bubble.parentElement.classList.add("msg-error");
        addText(bubble, ev.text);
      } else {
        onEvent(ev);
      }
    });
  } catch (err) {
    bubble.parentElement.classList.add("msg-error");
    addText(bubble, `요청에 실패했습니다: ${err.message}`);
  } finally {
    setBusy(false);
  }
}


// ====================================================================
// 상태 표시 (왼쪽 메뉴)
// ====================================================================

function applyStatus({ rag, contract }) {
  if (rag) {
    $("#ragStatus").textContent = rag.files.length
      ? `${rag.files.length}개 파일 · ${rag.total_chunks}개 조각`
      : "없음";
  }
  if (contract) {
    const ready = Boolean(contract.filename);
    $("#contractStatus").textContent = ready
      ? `${contract.filename} (${contract.sentence_count}개 문장)`
      : "없음";
    reviewBtn.hidden = !ready; // 계약서 업로드가 끝나야 '계약서 검토' 버튼이 보인다
  }
}

async function loadStatus() {
  try {
    applyStatus(await (await fetch("/api/status")).json());
  } catch (_) {
    /* 상태를 못 불러와도 화면 사용에는 문제가 없다 */
  }
}


// ====================================================================
// RAG 파일 업로드
// ====================================================================

ragBtn.addEventListener("click", () => ragInput.click());

ragInput.addEventListener("change", async () => {
  const files = [...ragInput.files];
  ragInput.value = ""; // 같은 파일을 다시 선택해도 change 가 발생하도록 비운다
  if (!files.length) return;

  addMessage("user", `RAG 파일 업로드: ${files.map((f) => f.name).join(", ")}`);
  const bubble = addMessage("assistant");

  const form = new FormData();
  files.forEach((f) => form.append("files", f));

  await runJob("/api/rag/upload", { method: "POST", body: form }, bubble, (ev) => {
    if (ev.type === "info") addText(bubble, ev.text);
    else if (ev.type === "progress") renderProgress(bubble, ev);
    else if (ev.type === "done") {
      addText(bubble, ev.text);
      applyStatus({ rag: ev.rag });
    }
  });
});


// ====================================================================
// 계약서 업로드
// ====================================================================

contractBtn.addEventListener("click", () => contractInput.click());

contractInput.addEventListener("change", async () => {
  const file = contractInput.files[0];
  contractInput.value = "";
  if (!file) return;

  addMessage("user", `계약서 업로드: ${file.name}`);
  const bubble = addMessage("assistant");

  const form = new FormData();
  form.append("file", file);

  await runJob("/api/contract/upload", { method: "POST", body: form }, bubble, (ev) => {
    if (ev.type === "info") addText(bubble, ev.text);
    else if (ev.type === "progress") renderProgress(bubble, ev);
    else if (ev.type === "done") {
      addText(bubble, ev.text);
      applyStatus({ contract: ev.contract });
    }
  });
});


// ====================================================================
// 계약서 검토 (문장 하나씩 실시간 출력)
// ====================================================================

reviewBtn.addEventListener("click", async () => {
  addMessage("user", "계약서 검토");
  const bubble = addMessage("assistant");

  await runJob("/api/review", { method: "POST" }, bubble, (ev) => {
    if (ev.type === "start") {
      addText(bubble, `총 ${ev.total}개 문장을 순서대로 검토합니다.`);
    } else if (ev.type === "sentence") {
      renderReviewProgress(bubble, ev);
      bubble.appendChild(renderSentence(ev));
      scrollToBottom();
    } else if (ev.type === "done") {
      addText(bubble, ev.text);
    }
  });
});

/** 맨 위의 검토 진행 막대를 갱신한다. (진행 중이라는 걸 한눈에 볼 수 있게) */
function renderReviewProgress(bubble, ev) {
  let block = bubble.querySelector(".progress");
  if (!block) {
    // 진행 막대는 검토 결과 목록 맨 위에 고정해 둔다
    block = document.createElement("div");
    block.className = "progress";
    block.dataset.key = "review";
    block.innerHTML =
      '<div class="progress-label"></div>' +
      '<div class="progress-track"><div class="progress-fill"></div></div>';
    bubble.insertBefore(block, bubble.children[1] || null);
  }
  const percent = Math.round((ev.index / ev.total) * 100);
  block.querySelector(".progress-label").textContent = `검토 진행 ${ev.index} / ${ev.total} (${percent}%)`;
  block.querySelector(".progress-fill").style.width = `${percent}%`;
  block.classList.toggle("finished", percent >= 100);
}

/** 문장 하나의 검토 결과를 [원문] / [수정 문구] 형태로 만든다. */
function renderSentence(ev) {
  const box = document.createElement("div");
  box.className = "sentence" + (ev.revised ? " has-fix" : "");

  const orig = document.createElement("div");
  orig.className = "orig";
  orig.append(makeTag("[원문]"), ev.original);
  box.appendChild(orig);

  // 이상이 없으면 원문만 출력한다
  if (ev.revised) {
    const rev = document.createElement("div");
    rev.className = "rev";
    rev.append(makeTag("[수정 문구]"), ev.revised);
    box.appendChild(rev);

    if (ev.reason) {
      const reason = document.createElement("div");
      reason.className = "reason";
      reason.textContent = `검토 의견: ${ev.reason}`;
      box.appendChild(reason);
    }
  }
  if (ev.error) {
    const err = document.createElement("div");
    err.className = "err";
    err.textContent = ev.error;
    box.appendChild(err);
  }
  return box;
}

function makeTag(text) {
  const span = document.createElement("span");
  span.className = "tag";
  span.textContent = text;
  return span;
}


// ====================================================================
// 일반 질문 (RAG 없이 LLM 에 직접 질문)
// ====================================================================

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message || busy) return;

  chatInput.value = "";
  autoResize();
  addMessage("user", message);
  const bubble = addMessage("assistant");
  let answer = "";

  await runJob(
    "/api/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: chatHistory }),
    },
    bubble,
    (ev) => {
      if (ev.type === "token") {
        answer += ev.text;
        bubble.textContent = answer; // 토큰이 도착할 때마다 답변이 이어서 써진다
        scrollToBottom();
      }
    }
  );

  if (answer) chatHistory.push({ role: "user", content: message }, { role: "assistant", content: answer });
});

// Enter 는 전송, Shift+Enter 는 줄바꿈 (한글 입력 중 Enter 는 무시)
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

// 입력 내용이 길어지면 질문창 높이를 자동으로 늘린다
function autoResize() {
  chatInput.style.height = "auto";
  chatInput.style.height = `${chatInput.scrollHeight}px`;
}
chatInput.addEventListener("input", autoResize);


// ====================================================================
// 시작
// ====================================================================

addMessage(
  "assistant",
  "안녕하세요! 계약서 검토를 도와드립니다.\n\n" +
    "1. 왼쪽의 'RAG 파일 업로드'로 가이드라인/약관 PDF를 올려 주세요.\n" +
    "2. '계약서 업로드'로 검토할 계약서 PDF를 올려 주세요.\n" +
    "3. 업로드가 끝나면 나타나는 '계약서 검토' 버튼을 누르면 문장 하나씩 검토합니다.\n\n" +
    "일반적인 질문은 아래 입력창에 자유롭게 물어보세요."
);
loadStatus();
