(() => {
  const $ = (id) => document.getElementById(id);
  const els = {
    sidebar: $("sidebar"),
    fileInput: $("fileInput"),
    uploadBtn: $("uploadBtn"),
    newChatBtn: $("newChatBtn"),
    docList: $("docList"),
    docEmpty: $("docEmpty"),
    docCount: $("docCount"),
    menuBtn: $("menuBtn"),
    chat: $("chat"),
    emptyState: $("emptyState"),
    messages: $("messages"),
    composer: $("composer"),
    input: $("questionInput"),
    sendBtn: $("sendBtn"),
    toastStack: $("toastStack"),
  };

  const BOT_ICON =
    '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4M9 12h.01M15 12h.01M9 16h6"/></svg>';
  const TRASH_ICON =
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>';

  let busy = false;
  let uploading = false;
  let summaryRun = 0;
  const summaryQueue = [];

  // ── 유틸 ───────────────────────────────────────────────
  const escapeHtml = (s) =>
    s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function renderMarkdown(text) {
    const lines = escapeHtml(text.trim()).split("\n");
    const html = [];
    let list = null;
    let para = [];
    const inline = (s) =>
      s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const flushPara = () => {
      if (para.length) html.push(`<p>${inline(para.join("<br>"))}</p>`);
      para = [];
    };
    const closeList = () => {
      if (list) html.push(`</${list}>`);
      list = null;
    };
    for (const raw of lines) {
      const line = raw.trim();
      const ul = line.match(/^[-*•]\s+(.*)/);
      const ol = line.match(/^\d+[.)]\s+(.*)/);
      if (ul || ol) {
        flushPara();
        const tag = ul ? "ul" : "ol";
        if (list !== tag) { closeList(); html.push(`<${tag}>`); list = tag; }
        html.push(`<li>${inline((ul || ol)[1])}</li>`);
      } else if (!line) {
        flushPara();
        closeList();
      } else {
        closeList();
        para.push(line);
      }
    }
    flushPara();
    closeList();
    return html.join("");
  }

  function toast(message, type = "") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    els.toastStack.appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }

  const scrollToBottom = () => { els.chat.scrollTop = els.chat.scrollHeight; };

  function updateEmptyState() {
    els.emptyState.style.display = els.messages.children.length ? "none" : "";
  }

  function updateSendState() {
    els.sendBtn.disabled = busy || !els.input.value.trim();
  }

  // ── 문서 목록 ──────────────────────────────────────────
  function renderDocs(docs) {
    els.docList.querySelectorAll(".doc-item:not(.pending)").forEach((n) => n.remove());
    for (const d of docs) {
      const li = document.createElement("li");
      li.className = "doc-item";
      li.innerHTML = `
        <div class="doc-icon">PDF</div>
        <div class="doc-body">
          <div class="doc-name" title="${escapeHtml(d.name)}">${escapeHtml(d.name)}</div>
          <div class="doc-meta">${d.pages}페이지 · ${d.chunks}개 chunk</div>
        </div>
        <button class="doc-del" type="button" title="문서 삭제">${TRASH_ICON}</button>`;
      li.querySelector(".doc-del").addEventListener("click", () => deleteDoc(d));
      els.docList.appendChild(li);
    }
    els.docCount.textContent = docs.length;
    els.docEmpty.style.display = els.docList.children.length ? "none" : "";
  }

  async function loadDocs() {
    const res = await fetch("/api/documents");
    renderDocs((await res.json()).documents);
  }

  async function deleteDoc(doc) {
    if (!confirm(`'${doc.name}' 문서를 삭제할까요?\n벡터 DB에서 해당 문서의 chunk가 모두 제거됩니다.`)) return;
    const res = await fetch(`/api/documents/${doc.doc_id}`, { method: "DELETE" });
    if (res.ok) toast(`'${doc.name}' 문서를 삭제했습니다.`, "success");
    else toast((await res.json()).error || "삭제에 실패했습니다.", "error");
    loadDocs();
  }

  // ── 업로드 ─────────────────────────────────────────────
  function pendingItem(name) {
    const li = document.createElement("li");
    li.className = "doc-item pending";
    li.innerHTML = `
      <div class="doc-icon"><div class="spinner"></div></div>
      <div class="doc-body">
        <div class="doc-name">${escapeHtml(name)}</div>
        <div class="doc-meta">대기 중…</div>
      </div>`;
    els.docList.prepend(li);
    els.docEmpty.style.display = "none";
    return li;
  }

  async function uploadFiles(fileList) {
    const files = Array.from(fileList);
    if (!files.length) return;

    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const rejected = files.filter((f) => !pdfs.includes(f));
    if (rejected.length) {
      toast(`PDF 파일만 업로드할 수 있습니다: ${rejected.map((f) => f.name).join(", ")}`, "error");
    }
    if (!pdfs.length) return;

    uploading = true;
    els.uploadBtn.disabled = true;
    const items = pdfs.map((f) => pendingItem(f.name));
    let okCount = 0;

    for (let i = 0; i < pdfs.length; i++) {
      const item = items[i];
      item.querySelector(".doc-meta").textContent = "텍스트 추출 · 임베딩 중…";
      const form = new FormData();
      form.append("files", pdfs[i]);
      try {
        const res = await fetch("/api/upload", { method: "POST", body: form });
        const data = await res.json();
        const r = data.results ? data.results[0] : { ok: false, error: data.error };
        if (r.ok) {
          okCount++;
          if (r.duplicate) toast(`'${r.name}'은(는) 이미 업로드된 문서입니다.`);
          item.remove();
          if (data.documents) renderDocs(data.documents);
        } else {
          item.classList.remove("pending");
          item.classList.add("failed");
          item.querySelector(".doc-icon").textContent = "!";
          item.querySelector(".doc-meta").textContent = r.error;
          toast(`${pdfs[i].name}: ${r.error}`, "error");
          setTimeout(() => { item.remove(); loadDocs(); }, 6000);
        }
      } catch (e) {
        item.remove();
        toast(`${pdfs[i].name}: 업로드 중 네트워크 오류가 발생했습니다.`, "error");
      }
    }

    if (okCount) toast(`${okCount}개 문서를 벡터 DB에 저장했습니다.`, "success");
    uploading = false;
    els.uploadBtn.disabled = false;
    els.fileInput.value = "";
    loadDocs();
  }

  els.uploadBtn.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", (e) => uploadFiles(e.target.files));

  let dragDepth = 0;
  els.sidebar.addEventListener("dragenter", (e) => { e.preventDefault(); dragDepth++; els.sidebar.classList.add("dragging"); });
  els.sidebar.addEventListener("dragover", (e) => e.preventDefault());
  els.sidebar.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; els.sidebar.classList.remove("dragging"); } });
  els.sidebar.addEventListener("drop", (e) => {
    e.preventDefault();
    dragDepth = 0;
    els.sidebar.classList.remove("dragging");
    if (uploading) return toast("업로드가 진행 중입니다. 잠시 후 다시 시도해 주세요.");
    uploadFiles(e.dataTransfer.files);
  });

  // ── 메시지 렌더링 ──────────────────────────────────────
  function addUserMessage(text) {
    const el = document.createElement("div");
    el.className = "msg user";
    el.innerHTML = `<div class="bubble"></div>`;
    el.querySelector(".bubble").textContent = text;
    els.messages.appendChild(el);
    updateEmptyState();
    scrollToBottom();
  }

  function addBotMessage() {
    const el = document.createElement("div");
    el.className = "msg bot";
    el.innerHTML = `
      <div class="avatar">${BOT_ICON}</div>
      <div class="content">
        <div class="status"><span class="dots"><span></span><span></span><span></span></span><span class="status-text">질문을 처리하는 중…</span></div>
        <div class="answer" hidden></div>
      </div>`;
    els.messages.appendChild(el);
    updateEmptyState();
    scrollToBottom();
    return el;
  }

  function setAnswer(msgEl, text, { streaming = false, noInfo = false, error = false } = {}) {
    const status = msgEl.querySelector(".status");
    const answer = msgEl.querySelector(".answer");
    if (status) status.remove();
    answer.hidden = false;
    answer.className = "answer" + (streaming ? " cursor" : "") + (noInfo ? " no-info" : "") + (error ? " error" : "");
    if (noInfo || error) answer.textContent = text;
    else answer.innerHTML = renderMarkdown(text) || "&nbsp;";
    if (streaming) {
      const last = answer.lastElementChild || answer;
      last.classList.add("cursor");
      answer.classList.remove("cursor");
    }
  }

  function renderSources(msgEl, sources, run) {
    if (!sources.length) return;
    const wrap = document.createElement("div");
    wrap.className = "sources";
    wrap.innerHTML = `
      <div class="sources-title">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        참고한 문서 조각 (${sources.length}개)
      </div>
      <div class="sources-grid"></div>`;
    const grid = wrap.querySelector(".sources-grid");

    sources.forEach((s, i) => {
      const card = document.createElement("div");
      card.className = "source-card";
      card.innerHTML = `
        <div class="source-head">
          <span class="source-idx">${i + 1}</span>
          <span class="source-name" title="${escapeHtml(s.source)}">${escapeHtml(s.source)}</span>
          <span class="badge page">p.${s.page}</span>
          <span class="badge score" title="질문과의 코사인 유사도">${Math.round(s.score * 100)}%</span>
        </div>
        <div class="source-summary"></div>
        <button class="source-toggle" type="button">원문 보기</button>
        <div class="source-raw"></div>`;
      card.querySelector(".source-raw").textContent = s.content;
      const summaryEl = card.querySelector(".source-summary");
      if (s.summary) {
        summaryEl.innerHTML = `<span class="label">요약</span>${escapeHtml(s.summary)}`;
      } else {
        summaryEl.classList.add("loading");
        summaryEl.innerHTML = `<span class="label">요약</span>${escapeHtml(s.preview)} <em>(요약 생성 중…)</em>`;
        summaryQueue.push({ id: s.id, el: summaryEl, preview: s.preview, run });
      }
      const toggle = card.querySelector(".source-toggle");
      toggle.addEventListener("click", () => {
        card.classList.toggle("open");
        toggle.textContent = card.classList.contains("open") ? "원문 닫기" : "원문 보기";
      });
      grid.appendChild(card);
    });
    msgEl.querySelector(".content").appendChild(wrap);
  }

  // 답변이 끝난 뒤 chunk 요약을 하나씩 요청한다. 새 질문이 시작되면 남은 요청은 건너뛴다.
  async function processSummaries() {
    while (summaryQueue.length) {
      if (busy) return;
      const job = summaryQueue.shift();
      if (job.run !== summaryRun) {
        job.el.classList.remove("loading");
        job.el.innerHTML = `<span class="label">미리보기</span>${escapeHtml(job.preview)}`;
        continue;
      }
      try {
        const res = await fetch("/api/summarize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: job.id }),
        });
        const data = await res.json();
        job.el.classList.remove("loading");
        job.el.innerHTML = res.ok
          ? `<span class="label">요약</span>${escapeHtml(data.summary)}`
          : `<span class="label">미리보기</span>${escapeHtml(job.preview)}`;
      } catch {
        job.el.classList.remove("loading");
        job.el.innerHTML = `<span class="label">미리보기</span>${escapeHtml(job.preview)}`;
      }
    }
  }

  // ── 채팅 ───────────────────────────────────────────────
  async function ask(question) {
    busy = true;
    summaryRun++;
    updateSendState();
    addUserMessage(question);
    const msgEl = addBotMessage();
    let text = "";
    let finished = false;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `요청 실패 (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          const ev = JSON.parse(line);
          if (ev.type === "status") {
            const st = msgEl.querySelector(".status-text");
            if (st) st.textContent = ev.message;
          } else if (ev.type === "token") {
            text += ev.text;
            setAnswer(msgEl, text, { streaming: true });
          } else if (ev.type === "done") {
            finished = true;
            setAnswer(msgEl, ev.answer, { noInfo: ev.no_info });
            renderSources(msgEl, ev.sources, summaryRun);
          } else if (ev.type === "error") {
            finished = true;
            setAnswer(msgEl, ev.message, { error: true });
          }
          scrollToBottom();
        }
      }
      if (!finished) setAnswer(msgEl, text || "응답이 중단되었습니다.", { error: !text });
    } catch (e) {
      setAnswer(msgEl, e.message || "오류가 발생했습니다.", { error: true });
    } finally {
      busy = false;
      updateSendState();
      scrollToBottom();
      processSummaries();
    }
  }

  els.composer.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = els.input.value.trim();
    if (!q || busy) return;
    els.input.value = "";
    autoResize();
    ask(q);
  });

  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      els.composer.requestSubmit();
    }
  });

  function autoResize() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 200) + "px";
    updateSendState();
  }
  els.input.addEventListener("input", autoResize);

  els.newChatBtn.addEventListener("click", async () => {
    if (busy) return toast("답변 생성이 끝난 뒤 새 대화를 시작할 수 있습니다.");
    await fetch("/api/reset", { method: "POST" });
    summaryRun++;
    summaryQueue.length = 0;
    els.messages.innerHTML = "";
    updateEmptyState();
    els.input.focus();
    els.sidebar.classList.remove("open");
  });

  els.menuBtn.addEventListener("click", () => els.sidebar.classList.toggle("open"));

  async function loadHistory() {
    const res = await fetch("/api/history");
    const { history } = await res.json();
    for (const turn of history) {
      addUserMessage(turn.question);
      const msgEl = addBotMessage();
      const noInfo = turn.answer === window.NO_INFO && !turn.sources.length;
      setAnswer(msgEl, turn.answer, { noInfo });
      renderSources(msgEl, turn.sources, summaryRun);
    }
    scrollToBottom();
    processSummaries();
  }

  loadDocs();
  loadHistory();
  els.input.focus();
})();
