const state = {
  history: [],
  health: null,
  busy: false,
};

const el = {
  statusPill: document.getElementById("statusPill"),
  sourceFilter: document.getElementById("sourceFilter"),
  scenarioName: document.getElementById("scenarioName"),
  kbVersion: document.getElementById("kbVersion"),
  llmModel: document.getElementById("llmModel"),
  llmBaseUrl: document.getElementById("llmBaseUrl"),
  llmRuntime: document.getElementById("llmRuntime"),
  envFiles: document.getElementById("envFiles"),
  retrievalMode: document.getElementById("retrievalMode"),
  retrievalTopK: document.getElementById("retrievalTopK"),
  messages: document.getElementById("messages"),
  form: document.getElementById("askForm"),
  queryInput: document.getElementById("queryInput"),
  sendBtn: document.getElementById("sendBtn"),
  diagnostics: document.getElementById("diagnostics"),
  sources: document.getElementById("sources"),
  clearBtn: document.getElementById("clearBtn"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setBusy(busy) {
  state.busy = busy;
  el.sendBtn.disabled = busy;
  el.queryInput.disabled = busy;
  el.sendBtn.textContent = busy ? "处理中" : "发送";
}

function appendMessage(role, text, extraClass = "") {
  const item = document.createElement("div");
  item.className = `message ${role} ${extraClass}`.trim();
  item.textContent = text;
  el.messages.appendChild(item);
  el.messages.scrollTop = el.messages.scrollHeight;
}

function compactPath(path) {
  const parts = String(path || "").split(/[\\/]+/).filter(Boolean);
  return parts.slice(-2).join("/");
}

function renderDiagnostics(payload) {
  const retrieval = payload.retrieval || {};
  const timings = retrieval.timings || {};
  const rows = [
    ["route", payload.route],
    ["rewritten_query", payload.rewritten_query],
    ["query_variants", (payload.query_variants || []).join(" | ")],
    ["query_variant_count", retrieval.query_variant_count ?? (payload.query_variants || []).length],
    ["rerank", retrieval.rerank ?? "-"],
    ["kb_version", retrieval.kb_version || "-"],
    ["faq_top_score", retrieval.faq_top_score ?? "-"],
    ["doc_top_score", retrieval.doc_top_score ?? "-"],
    ["faq_hits", retrieval.faq_hits ?? "-"],
    ["doc_hits", retrieval.doc_hits ?? "-"],
    ["context_docs", retrieval.context_docs ?? "-"],
    ["faq_elapsed_ms", retrieval.faq_elapsed_ms ?? "-"],
    ["doc_elapsed_ms", retrieval.doc_elapsed_ms ?? "-"],
    ["faq_rerank_ms", retrieval.faq_rerank_ms ?? "-"],
    ["doc_rerank_ms", retrieval.doc_rerank_ms ?? "-"],
    ["total_ms", timings.total_ms ?? "-"],
    ["llm_generate_ms", timings.llm_generate_ms ?? "-"],
  ];
  el.diagnostics.innerHTML = rows.map(([label, value]) => `
    <div class="diag-row">
      <span>${escapeHtml(label)}</span>
      <code>${escapeHtml(value)}</code>
    </div>
  `).join("");
}

function renderSources(sources) {
  if (!sources || sources.length === 0) {
    el.sources.innerHTML = '<p class="muted">本次没有返回引用来源。</p>';
    return;
  }
  el.sources.innerHTML = sources.map((source, index) => `
    <article class="source-card">
      <div class="source-title">
        <span>${index + 1}. ${escapeHtml(source.citation || source.source_type)}</span>
        <span class="score">${Number(source.score || 0).toFixed(3)}</span>
      </div>
      <p>${escapeHtml(source.content || "")}</p>
    </article>
  `).join("");
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    state.health = data;
    el.scenarioName.textContent = data.display_name || data.scenario_id || "-";
    el.kbVersion.textContent = data.active_kb_version || "-";
    const llm = data.llm || {};
    el.llmModel.textContent = llm.chat_model || "-";
    el.llmBaseUrl.textContent = llm.base_url || "-";
    el.llmRuntime.textContent = `${llm.api_key_configured ? "Key 已配置" : "Key 未配置"} / ${llm.timeout_seconds || "-"}s / T=${llm.temperature ?? "-"}`;
    el.envFiles.textContent = (llm.env_files || []).map(compactPath).join(" | ") || "-";
    const retrievalConfig = data.retrieval_config || {};
    el.retrievalMode.textContent = `变体=${retrievalConfig.use_query_variants ? "开" : "关"} / 重排=${retrievalConfig.rerank ? "开" : "关"}`;
    el.retrievalTopK.textContent = `FAQ ${retrievalConfig.faq_top_k || "-"} / Doc ${retrievalConfig.doc_top_k || "-"} / Rerank ${retrievalConfig.rerank_top_n || "-"}`;
    const ready = !String(data.active_kb_version || "").startsWith("not_ready");
    const runtimeOk = data.runtime && data.runtime.ok;
    el.statusPill.textContent = ready && runtimeOk ? "系统就绪" : "需要处理";
    el.statusPill.className = `status-pill ${ready && runtimeOk ? "ready" : "warn"}`;

    if (!runtimeOk) {
      const missing = (data.runtime.missing || [])
        .map((item) => `${item.package}：${item.used_by}`)
        .join("\n");
      appendMessage(
        "assistant",
        `当前 Python 环境缺少 Mini RAG 提问链路依赖：\n${missing}\n\n请在启动 API 的同一个环境执行：pip install -r requirements.txt`,
        "error",
      );
      el.diagnostics.innerHTML = `
        <div class="diag-row">
          <span>runtime</span>
          <code>缺少依赖，提问链路暂不可用</code>
        </div>
        <div class="diag-row">
          <span>install</span>
          <code>${escapeHtml(data.runtime.install_command || "pip install -r requirements.txt")}</code>
        </div>
      `;
    }

    const labels = data.source_labels || {};
    for (const source of data.valid_sources || []) {
      const option = document.createElement("option");
      option.value = source;
      option.textContent = labels[source] ? `${labels[source]} (${source})` : source;
      el.sourceFilter.appendChild(option);
    }
  } catch (error) {
    el.statusPill.textContent = "服务异常";
    el.statusPill.className = "status-pill warn";
    appendMessage("assistant", `健康检查失败：${error.message}`, "error");
  }
}

async function submitQuestion(query) {
  const trimmed = query.trim();
  if (!trimmed || state.busy) {
    return;
  }
  appendMessage("user", trimmed);
  el.queryInput.value = "";
  setBusy(true);
  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        query: trimmed,
        history: state.history.slice(-8),
        source_filter: el.sourceFilter.value || null,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    appendMessage("assistant", data.answer || "");
    state.history.push(trimmed);
    state.history.push(data.answer || "");
    renderDiagnostics(data);
    renderSources(data.sources || []);
  } catch (error) {
    appendMessage("assistant", `请求失败：${error.message}`, "error");
  } finally {
    setBusy(false);
    el.queryInput.focus();
  }
}

el.form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitQuestion(el.queryInput.value);
});

el.queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitQuestion(el.queryInput.value);
  }
});

document.querySelectorAll(".sample").forEach((button) => {
  button.addEventListener("click", () => {
    const history = button.dataset.history;
    if (history) {
      state.history = [history];
    }
    submitQuestion(button.dataset.question || button.textContent);
  });
});

el.clearBtn.addEventListener("click", () => {
  state.history = [];
  el.messages.innerHTML = "";
  el.diagnostics.innerHTML = '<p class="muted">发送问题后显示 route、改写问题、查询变体和检索分数。</p>';
  el.sources.innerHTML = "";
  el.queryInput.focus();
});

loadHealth();
