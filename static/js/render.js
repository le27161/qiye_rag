/* 视图渲染层：把回答事件、引用和诊断数据转换为安全 HTML，不负责请求和业务状态持久化。 */
function renderWelcome(prefix = '') {
  const scenario = currentScenario();
  els.chatHistory.innerHTML = '';
  let content;
  if (scenario) {
    const samples = (scenario.sample_questions || []).slice(0, 3);
    content = [
      prefix,
      prefix ? '' : '',
      `### ${scenario.display_name}`,
      '',
      scenario.description || scenario.business_domain || '',
      '',
      samples.length ? '**试着提问：**' : '',
      samples.map(q => `- ${q}`).join('\n'),
    ].filter(line => line !== undefined).join('\n');
  } else {
    content = '### 欢迎使用 KnowForge RAG Platform\n\n请在上方选择一个业务场景后开始提问。';
  }
  const welcome = appendMessage('assistant', content, '系统');
  welcome.wrapper.classList.add('welcome-message');
}

function renderSamples() {
  const scenario = currentScenario();
  const questions = (scenario && scenario.sample_questions) || [];
  if (!questions.length) {
    els.sampleQuestions.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i class="fas fa-comment-dots"></i></div>当前场景暂无示例问题</div>';
    return;
  }
  els.sampleQuestions.innerHTML = questions.slice(0, 6).map(question => `
    <button class="sample-question" data-question="${escapeAttribute(question)}">${escapeHtml(question)}</button>
  `).join('');
  els.sampleQuestions.querySelectorAll('.sample-question').forEach(button => {
    button.addEventListener('click', () => {
      els.chatInput.value = button.dataset.question || '';
      autoResizeInput();
      els.chatInput.focus();
    });
  });
}

function updateScopeDisplay() {
  const sourceLabel = els.sourceFilter.selectedOptions[0]?.textContent || '全部';
  const tenant = els.tenantInput.value.trim() || 'default';
  const dataset = els.datasetInput.value.trim() || 'default';
  const visibility = els.visibilitySelect.value || 'public';
  const role = els.roleSelect.value || 'public';
  els.composerScope.textContent = `${sourceLabel}｜${tenant}/${dataset}｜${visibility}/${role}`;
  updateSideStats();
}

function updateSideStats() {
  const diagnostics = state.lastDiagnostics || {};
  const promptProfile = diagnostics.promptProfile || '-';
  const intentName = diagnostics.intentName || '-';
  const questionCategory = diagnostics.questionCategory || '-';
  const performance = performanceStatus(diagnostics);
  const confidence = confidenceStatus(diagnostics.answerConfidence);
  const confidenceTitle = confidence.reasons.length ? confidence.reasons.join(' / ') : confidence.label;
  const generation = generationStatus(diagnostics.answerConfidence?.generation_verification);
  const firstToken = diagnostics.firstTokenMs ? `${diagnostics.firstTokenMs} ms` : '-';
  const totalElapsed = diagnostics.totalElapsedMs ? `${diagnostics.totalElapsedMs} ms` : '-';
  const slowestStage = diagnostics.slowestStageName
    ? `${diagnostics.slowestStageName} ${diagnostics.slowestStageMs || 0} ms`
    : '-';
  els.sideStats.innerHTML = `
    <div class="diagnostic-panel">
      <div class="diagnostic-section-title">运行上下文</div>
      <div class="side-stat"><span>场景</span><strong>${escapeHtml(currentScenario()?.scenario_id || '-')}</strong></div>
      <div class="side-stat"><span>业务分类</span><strong>${escapeHtml(els.sourceFilter.selectedOptions[0]?.textContent || '全部')}</strong></div>
      <div class="side-stat"><span>数据域</span><strong>${escapeHtml(scopeLabel())}</strong></div>
      <div class="side-stat"><span>知识库版本</span><strong title="${escapeAttribute(state.kbVersion || '-')}">${escapeHtml(shortText(state.kbVersion || '-', 22))}</strong></div>
    </div>
    <div class="diagnostic-panel">
      <div class="diagnostic-section-title">最近一次回答</div>
      <div class="performance-badge ${escapeAttribute(performance.level)}"><i class="fas ${escapeAttribute(performance.icon)}"></i><span>${escapeHtml(performance.label)}</span></div>
      <div class="side-stat"><span>流式状态</span><strong>${escapeHtml(state.lastStreamStatus)}</strong></div>
      <div class="side-stat"><span>命中路径</span><strong>${escapeHtml(state.lastHitType)}</strong></div>
      <div class="side-stat"><span>答案置信度</span><strong class="confidence-text ${escapeAttribute(confidence.level)}" title="${escapeAttribute(confidenceTitle)}">${escapeHtml(confidence.text)}</strong></div>
      <div class="side-stat"><span>生成核验</span><strong title="${escapeAttribute(generation.title)}">${escapeHtml(generation.text)}</strong></div>
      <div class="side-stat"><span>Prompt</span><strong title="${escapeAttribute(promptProfile)}">${escapeHtml(shortText(promptProfile, 22))}</strong></div>
      <div class="side-stat"><span>意图/类别</span><strong title="${escapeAttribute(`${intentName} / ${questionCategory}`)}">${escapeHtml(shortText(`${intentName} / ${questionCategory}`, 22))}</strong></div>
      <div class="side-stat"><span>来源数量</span><strong>${escapeHtml(String(state.lastSourceCount))}</strong></div>
      <div class="side-stat"><span>首 token</span><strong>${escapeHtml(firstToken)}</strong></div>
      <div class="side-stat"><span>总耗时</span><strong>${escapeHtml(totalElapsed)}</strong></div>
      <div class="side-stat"><span>最慢阶段</span><strong title="${escapeAttribute(slowestStage)}">${escapeHtml(shortText(slowestStage, 22))}</strong></div>
      <div class="side-stat"><span>Trace</span><strong title="${escapeAttribute(state.lastTraceId || '-')}">${escapeHtml(shortText(state.lastTraceId || '-', 22))}</strong></div>
    </div>
    ${renderSideSourceList(diagnostics.sources || [])}
  `;
}

function appendMessage(role, content, meta, rawHtml = false) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role === 'user' ? 'user' : 'assistant'}`;
  const metaElement = document.createElement('div');
  metaElement.className = 'message-meta';
  metaElement.textContent = meta || (role === 'user' ? '你' : '助手');
  const contentElement = document.createElement('div');
  contentElement.className = 'message-content';
  contentElement.innerHTML = rawHtml ? content : (role === 'assistant' ? renderAnswerContent(content) : renderMarkdown(content));
  wrapper.appendChild(metaElement);
  wrapper.appendChild(contentElement);
  els.chatHistory.appendChild(wrapper);
  scrollToBottom();
  return { wrapper, content: contentElement };
}

function renderAnswerContent(content) {
  const structured = renderStructuredAnswer(content);
  return structured || renderMarkdown(content);
}

function renderInlineMarkdown(content) {
  return renderMarkdown(String(content || ''))
    .replace(/^<p>/, '')
    .replace(/<\/p>\s*$/, '');
}

function renderStructuredAnswer(content) {
  const text = String(content || '').trim();
  if (!text) return '';

  const lines = text.split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean);
  const hasMarkdownLayout = lines.some(line => /^#{1,6}\s+/.test(line) || /^-{3,}$/.test(line));
  if (hasMarkdownLayout) return '';

  const hasStructuredMarkers = lines.some(line =>
    /^(✅|✔|❌|✖|⚠️|📌|已确认(?:[:：]|$)|无法确认(?:[:：]|$)|未确认(?:[:：/／]|$)|需人工确认(?:[:：/／]|$)|待确认(?:[:：]|$)|建议(?:[:：]|$)|→|->)/.test(line)
  );
  const hasInsufficientIntro = /^(信息不足|无法确认|当前知识库资料不足)/.test(lines[0] || '');
  if (!hasStructuredMarkers && !hasInsufficientIntro) return '';

  const intro = [];
  const sections = [];
  let statusLine = '';
  let followup = '';
  let current = null;

  const pushCurrent = () => {
    if (current && (current.body.length || current.items.length)) {
      sections.push(current);
    }
    current = null;
  };
  const startSection = (type, title, body) => {
    pushCurrent();
    current = { type, title, body: body ? [body] : [], items: [] };
  };

  lines.forEach((line, index) => {
    if (index === 0 && hasInsufficientIntro) {
      statusLine = line;
      return;
    }
    if (/^如需[，,]/.test(line)) {
      pushCurrent();
      followup = line;
      return;
    }

    const marker = parseAnswerLineMarker(line);
    if (marker.type === 'confirmed' || marker.type === 'unknown' || marker.type === 'advice') {
      startSection(marker.type, marker.title, marker.text);
      return;
    }
    if (marker.type === 'step') {
      if (!current || current.type !== 'advice') {
        startSection('advice', '建议', '');
      }
      current.items.push(marker.text);
      return;
    }

    if (current && marker.type === 'dash') {
      current.items.push(marker.text);
      return;
    }

    if (current) {
      current.body.push(line);
    } else {
      intro.push(line);
    }
  });
  pushCurrent();

  const statusHtml = statusLine ? renderAnswerStatus(statusLine) : '';
  const introHtml = intro.length ? `<div class="answer-brief">${intro.map(line => renderMarkdown(line)).join('')}</div>` : '';
  const gridClass = answerSectionGridClass(sections);
  const sectionsHtml = sections.length ? `
    <div class="${escapeAttribute(gridClass)}">
      ${sections.map(renderAnswerSection).join('')}
    </div>
  ` : '';
  const followupHtml = followup ? `<div class="answer-followup"><i class="fas fa-envelope-open-text"></i><span>${renderInlineMarkdown(followup)}</span></div>` : '';

  return `<div class="structured-answer">${statusHtml}${introHtml}${sectionsHtml}${followupHtml}</div>`;
}

function answerSectionGridClass(sections) {
  const isShort = section =>
    section.items.length === 0 &&
    section.body.length <= 2 &&
    section.body.join('').length <= 180;
  const canUseTwoColumns =
    sections.length === 2 &&
    sections.some(section => section.type === 'confirmed') &&
    sections.some(section => section.type === 'unknown') &&
    sections.every(isShort);
  return `answer-section-grid${sections.length === 1 ? ' single' : ''}${canUseTwoColumns ? ' two-column' : ''}`;
}

function parseAnswerLineMarker(line) {
  const text = String(line || '').trim();
  const rules = [
    { type: 'confirmed', title: '已确认', pattern: /^(?:✅|✔)\s*(?:已确认[:：])?\s*/ },
    { type: 'confirmed', title: '已确认', pattern: /^已确认[:：]\s*/ },
    { type: 'confirmed', title: '已确认', pattern: /^已确认$/ },
    { type: 'unknown', title: '需确认', pattern: /^(?:⚠️)\s*(?:未确认|需人工确认|待确认)?(?:[:：/／])?\s*/ },
    { type: 'unknown', title: '无法确认', pattern: /^(?:❌|✖)\s*(?:无法确认[:：])?\s*/ },
    { type: 'unknown', title: '无法确认', pattern: /^无法确认[:：]\s*/ },
    { type: 'unknown', title: '无法确认', pattern: /^无法确认$/ },
    { type: 'unknown', title: '需确认', pattern: /^未确认(?:\s*[\/／]\s*需人工确认)?[:：]?\s*/ },
    { type: 'unknown', title: '需人工确认', pattern: /^需人工确认(?:[:：/／])?\s*/ },
    { type: 'unknown', title: '待确认', pattern: /^待确认[:：]?\s*/ },
    { type: 'advice', title: '建议', pattern: /^(?:📌)\s*(?:建议[:：])?\s*/ },
    { type: 'advice', title: '建议', pattern: /^建议[:：]\s*/ },
    { type: 'advice', title: '建议', pattern: /^建议$/ },
    { type: 'step', title: '', pattern: /^(?:→|->)\s*/ },
    { type: 'dash', title: '', pattern: /^-\s*/ },
  ];
  for (const rule of rules) {
    if (rule.pattern.test(text)) {
      return { type: rule.type, title: rule.title, text: text.replace(rule.pattern, '').trim() };
    }
  }
  return { type: 'plain', title: '', text };
}

function renderAnswerStatus(line) {
  const normalized = line.replace(/[。.!！]+$/, '');
  const title = normalized.includes('，') ? normalized.split('，')[0] : normalized;
  const detail = normalized.includes('，') ? normalized.split('，').slice(1).join('，') : '';
  return `
    <div class="answer-status">
      <span class="answer-status-icon"><i class="fas fa-circle-exclamation"></i></span>
      <div>
        <strong>${escapeHtml(title || '信息不足')}</strong>
        ${detail ? `<p>${escapeHtml(detail)}</p>` : ''}
      </div>
    </div>
  `;
}

function renderAnswerSection(section) {
  const iconMap = {
    confirmed: 'fa-circle-check',
    unknown: 'fa-circle-question',
    advice: 'fa-route',
  };
  const body = section.body.length ? `<div class="answer-section-body">${section.body.map(line => renderMarkdown(line)).join('')}</div>` : '';
  const listTag = section.type === 'advice' ? 'ol' : 'ul';
  const listClass = section.type === 'advice' ? 'answer-step-list' : 'answer-fact-list';
  const items = section.items.length ? `<${listTag} class="${listClass}">${section.items.map(item => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</${listTag}>` : '';
  return `
    <section class="answer-section answer-section-${escapeAttribute(section.type)}">
      <div class="answer-section-head">
        <span><i class="fas ${escapeAttribute(iconMap[section.type] || 'fa-circle-info')}"></i></span>
        <strong>${escapeHtml(section.title)}</strong>
      </div>
      ${body}
      ${items}
    </section>
  `;
}

function renderSources(sources) {
  const wrapper = document.createElement('div');
  wrapper.className = 'answer-sources';
  const title = document.createElement('div');
  title.className = 'message-meta';
  title.textContent = '参考来源';
  wrapper.appendChild(title);
  sources.slice(0, 5).forEach((source, index) => {
    const metadata = source.metadata || {};
    const label = source.citation || metadata.file_name || metadata.standard_question || metadata.source || `来源 ${index + 1}`;
    const table = source.table || {};
    const tableMeta = table.row_number
      ? `表格行 · ${table.sheet_name || '工作表'} · 第 ${table.row_number} 行`
      : '';
    const scoreValue = Number(source.score);
    const score = Number.isFinite(scoreValue) ? scoreValue.toFixed(3) : '-';
    const item = document.createElement('div');
    item.className = `source-item${tableMeta ? ' table-source' : ''}`;
    item.innerHTML = `
      <span>
        ${index + 1}. ${escapeHtml(label)}
        ${tableMeta ? `<small>${escapeHtml(tableMeta)}</small>` : ''}
      </span>
      <span>${score}</span>
    `;
    wrapper.appendChild(item);
  });
  return wrapper;
}

function scopeLabel() {
  const tenant = els.tenantInput.value.trim() || 'default';
  const dataset = els.datasetInput.value.trim() || 'default';
  const visibility = els.visibilitySelect.value || 'public';
  const role = els.roleSelect.value || 'public';
  return `${tenant}/${dataset}/${visibility}/${role}`;
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatMs(value) {
  const number = numberOrNull(value);
  return number === null ? '-' : `${Math.round(number)} ms`;
}

function sourceLabel(source, index) {
  const metadata = source.metadata || {};
  return source.citation
    || metadata.file_name
    || metadata.standard_question
    || metadata.h1
    || metadata.source
    || `来源 ${index + 1}`;
}

function buildDiagnosticsSnapshot(event, sources) {
  const retrieval = event.retrieval || {};
  const plan = retrieval.plan || {};
  const promptProfile = retrieval.prompt_profile || {};
  const answerConfidence = event.answer_confidence || retrieval.answer_confidence || {};
  const intent = event.intent || {};
  const slowest = event.slowest_stage || retrieval.slowest_stage || {};
  return {
    traceId: event.trace_id || state.lastTraceId || '-',
    hitType: event.hit_type || '-',
    scenarioId: retrieval.scenario_id || event.scenario_id || state.scenarioId || '-',
    scenarioName: retrieval.scenario_name || currentScenario()?.display_name || '-',
    kbVersion: retrieval.kb_version || event.kb_version || state.kbVersion || '-',
    sourceFilter: retrieval.source_filter || els.sourceFilter.value || '全部',
    promptProfile: promptProfile.name || '-',
    promptReason: promptProfile.reason || '',
    answerConfidence,
    intentName: intent.intent || '-',
    intentRuleScore: numberOrNull(intent.rule_score ?? intent.confidence),
    intentReason: intent.reason || '',
    questionCategory: plan.question_category || '-',
    planReason: plan.reason || '-',
    queryVariants: retrieval.query_variants || plan.query_variants || [],
    faqTopScore: numberOrNull(retrieval.faq_top_score),
    faqReusedFromFastPath: retrieval.faq_reused_from_fast_path === true,
    faqReuseReason: retrieval.faq_reuse_reason || '',
    faqIncrementalVariantQueries: retrieval.faq_incremental_variant_queries || [],
    firstTokenMs: numberOrNull(event.first_token_ms || retrieval.first_token_ms),
    totalElapsedMs: numberOrNull(retrieval.total_elapsed_ms || event.processing_time * 1000),
    slowestStageName: slowest.name || '',
    slowestStageMs: numberOrNull(slowest.elapsed_ms),
    stageTimings: event.stage_timings_ms || retrieval.stage_timings_ms || {},
    cache: retrieval.cache || null,
    sources: sources || []
  };
}

function renderAnswerDiagnostics(diagnostics) {
  const wrapper = document.createElement('div');
  wrapper.className = 'answer-diagnostics';
  const confidence = confidenceStatus(diagnostics.answerConfidence);
  const confidenceTitle = confidence.reasons.length ? confidence.reasons.join(' / ') : confidence.label;
  const evidenceConfidence = confidenceStatus(diagnostics.answerConfidence?.evidence_confidence);
  const generation = generationStatus(diagnostics.answerConfidence?.generation_verification);
  const stageEntries = Object.entries(diagnostics.stageTimings || {})
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 4);
  const variants = (diagnostics.queryVariants || []).slice(0, 3);
  const incrementalVariants = (diagnostics.faqIncrementalVariantQueries || []).slice(0, 3);
  const cache = diagnostics.cache || {};
  const cacheEvents = Array.isArray(cache.events) ? cache.events : [];
  const cacheEnabled = cache.enabled === true || cacheEvents.some(event => event.enabled === true);
  const cacheHitCount = Number.isFinite(Number(cache.hit_count))
    ? Number(cache.hit_count)
    : cacheEvents.filter(event => event.hit === true).length;
  const cacheMissCount = Number.isFinite(Number(cache.miss_count))
    ? Number(cache.miss_count)
    : cacheEvents.filter(event => event.enabled === true && event.hit !== true).length;
  const hasCacheDiagnostics = Boolean(diagnostics.cache) || cacheEvents.length > 0;
  const cacheStatusText = !hasCacheDiagnostics
    ? '缓存：无检索阶段'
    : cacheEnabled
      ? `缓存：命中 ${cacheHitCount} / 未命中 ${cacheMissCount}`
      : '缓存：未启用';
  const cacheEventRows = cacheEvents
    .filter(event => event && event.stage)
    .map(event => {
      const hit = event.hit === true;
      const state = hit ? '命中' : '未命中';
      const stateClass = hit ? 'hit' : 'miss';
      return `<code class="cache-event ${stateClass}">${escapeHtml(event.stage)}：${state}</code>`;
    })
    .join('');
  wrapper.innerHTML = `
    <div class="answer-diagnostics-title">
      <i class="fas fa-chart-line"></i>
      <span>检索诊断</span>
    </div>
    <div class="diagnostic-chips">
      <span>路径：${escapeHtml(diagnostics.hitType)}</span>
      <span>模板：${escapeHtml(diagnostics.promptProfile)}</span>
      <span>类别：${escapeHtml(diagnostics.questionCategory)}</span>
      <span class="confidence-chip ${escapeAttribute(confidence.level)}" title="${escapeAttribute(confidenceTitle)}">置信度：${escapeHtml(confidence.text)}</span>
      <span class="confidence-chip ${escapeAttribute(evidenceConfidence.level)}">证据：${escapeHtml(evidenceConfidence.text)}</span>
      <span title="${escapeAttribute(generation.title)}">生成核验：${escapeHtml(generation.text)}</span>
      <span>性能：${escapeHtml(performanceStatus(diagnostics).label)}</span>
      <span>首 token：${escapeHtml(formatMs(diagnostics.firstTokenMs))}</span>
      <span class="${cacheEnabled ? 'cache-chip-enabled' : 'cache-chip-disabled'}">${escapeHtml(cacheStatusText)}</span>
    </div>
    <div class="diagnostic-grid">
      <div><span>意图</span><strong>${escapeHtml(diagnostics.intentName)}</strong></div>
      <div><span>规则分数</span><strong>${diagnostics.intentRuleScore === null ? '-' : diagnostics.intentRuleScore}</strong></div>
      <div><span>FAQ 最高分</span><strong>${diagnostics.faqTopScore === null ? '-' : diagnostics.faqTopScore.toFixed(3)}</strong></div>
      <div><span>答案置信度</span><strong title="${escapeAttribute(confidenceTitle)}">${escapeHtml(confidence.text)}</strong></div>
      <div><span>证据置信度</span><strong>${escapeHtml(evidenceConfidence.text)}</strong></div>
      <div><span>生成核验</span><strong title="${escapeAttribute(generation.title)}">${escapeHtml(generation.text)}</strong></div>
      <div><span>知识库版本</span><strong title="${escapeAttribute(diagnostics.kbVersion)}">${escapeHtml(shortText(diagnostics.kbVersion, 28))}</strong></div>
      <div><span>最慢阶段</span><strong>${escapeHtml(diagnostics.slowestStageName || '-')}${diagnostics.slowestStageMs === null ? '' : ` · ${formatMs(diagnostics.slowestStageMs)}`}</strong></div>
    </div>
    ${variants.length ? `<div class="diagnostic-mini-list"><span>查询变体</span>${variants.map(item => `<code>${escapeHtml(item)}</code>`).join('')}</div>` : ''}
    ${diagnostics.faqReusedFromFastPath ? `<div class="diagnostic-mini-list"><span>FAQ 复用</span><code>${escapeHtml(diagnostics.faqReuseReason || 'reuse_original_and_search_variants')}</code>${incrementalVariants.map(item => `<code>补查：${escapeHtml(item)}</code>`).join('')}</div>` : ''}
    ${cacheEventRows ? `<div class="diagnostic-mini-list cache-event-list"><span>缓存状态</span>${cacheEventRows}</div>` : ''}
    ${confidence.reasons.length ? `<div class="diagnostic-mini-list"><span>置信原因</span>${confidence.reasons.slice(0, 5).map(item => `<code>${escapeHtml(item)}</code>`).join('')}</div>` : ''}
    ${stageEntries.length ? `<div class="stage-bars">${stageEntries.map(([name, value]) => renderStageBar(name, value, stageEntries[0][1])).join('')}</div>` : ''}
  `;
  return wrapper;
}

function confidenceStatus(confidence) {
  const payload = confidence || {};
  const score = numberOrNull(payload.score);
  const rawLevel = String(payload.level || '').toLowerCase();
  const level = ['high', 'medium', 'low'].includes(rawLevel) ? rawLevel : 'unknown';
  const levelLabels = { high: '高', medium: '中', low: '低', unknown: '-' };
  const label = payload.label || levelLabels[level] || '-';
  const scoreText = score === null ? '' : score.toFixed(2);
  const reasons = Array.isArray(payload.reasons) ? payload.reasons.map(item => String(item)).filter(Boolean) : [];
  return {
    level,
    label,
    score,
    scoreText,
    reasons,
    text: scoreText ? `${label} ${scoreText}` : label
  };
}

function generationStatus(verification) {
  const payload = verification || {};
  const status = String(payload.status || '').toLowerCase();
  const score = numberOrNull(payload.score);
  const labels = {
    verified: '已通过',
    partial: '部分通过',
    failed: '未通过',
    pending: '待核验',
    not_applicable: '不适用'
  };
  const reasons = Array.isArray(payload.reasons) ? payload.reasons.map(item => String(item)).filter(Boolean) : [];
  const label = labels[status] || '-';
  const scoreText = score === null ? '' : ` ${score.toFixed(2)}`;
  return {
    status,
    score,
    reasons,
    text: `${label}${scoreText}`,
    title: reasons.length ? reasons.join(' / ') : label
  };
}

function performanceStatus(diagnostics) {
  const firstToken = numberOrNull(diagnostics.firstTokenMs);
  const total = numberOrNull(diagnostics.totalElapsedMs);
  if (firstToken === null && total === null) {
    return { level: 'idle', label: '等待数据', icon: 'fa-circle' };
  }
  if ((firstToken !== null && firstToken > 8000) || (total !== null && total > 15000)) {
    return { level: 'slow', label: '较慢', icon: 'fa-triangle-exclamation' };
  }
  if ((firstToken !== null && firstToken > 4000) || (total !== null && total > 8000)) {
    return { level: 'warn', label: '偏慢', icon: 'fa-clock' };
  }
  return { level: 'ok', label: '正常', icon: 'fa-circle-check' };
}

function renderStageBar(name, value, maxValue) {
  const current = Number(value) || 0;
  const max = Math.max(Number(maxValue) || 1, 1);
  const width = Math.max(6, Math.min(100, (current / max) * 100));
  return `
    <div class="stage-bar">
      <div class="stage-bar-label"><span>${escapeHtml(name)}</span><strong>${escapeHtml(formatMs(current))}</strong></div>
      <div class="stage-bar-track"><span style="width:${width.toFixed(1)}%"></span></div>
    </div>
  `;
}

function renderSideSourceList(sources) {
  if (!sources.length) {
    return '<div class="diagnostic-panel"><div class="diagnostic-section-title">命中来源</div><div class="empty-state compact">暂无来源</div></div>';
  }
  return `
    <div class="diagnostic-panel">
      <div class="diagnostic-section-title">命中来源</div>
      <div class="side-source-list">
        ${sources.slice(0, 4).map((source, index) => {
          const score = numberOrNull(source.score);
          const metadata = source.metadata || {};
          const sourceType = source.source_type || metadata.source_type || '-';
          return `
            <div class="side-source-item">
              <div title="${escapeAttribute(sourceLabel(source, index))}">${index + 1}. ${escapeHtml(shortText(sourceLabel(source, index), 24))}</div>
              <span>${escapeHtml(sourceType)}${score === null ? '' : ` · ${score.toFixed(3)}`}</span>
            </div>
          `;
        }).join('')}
      </div>
    </div>
  `;
}

function renderFeedbackActions(question, answer, sources) {
  const wrapper = document.createElement('div');
  wrapper.className = 'answer-actions';
  const thumbsUpIcon = `
    <span class="feedback-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M7 10v10"></path>
        <path d="M11 6l-1 4h8a2 2 0 0 1 2 2l-1 6a2 2 0 0 1-2 2H7"></path>
        <path d="M7 10H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h3"></path>
      </svg>
    </span>
  `;
  const thumbsDownIcon = `
    <span class="feedback-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M7 14V4"></path>
        <path d="M11 18l-1-4h8a2 2 0 0 0 2-2l-1-6a2 2 0 0 0-2-2H7"></path>
        <path d="M7 14H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3"></path>
      </svg>
    </span>
  `;
  const label = document.createElement('span');
  label.textContent = '反馈';
  const useful = document.createElement('button');
  useful.title = '有用';
  useful.setAttribute('aria-label', '有用');
  useful.innerHTML = thumbsUpIcon;
  const notUseful = document.createElement('button');
  notUseful.title = '无用';
  notUseful.setAttribute('aria-label', '无用');
  notUseful.innerHTML = thumbsDownIcon;

  const submit = async rating => {
    useful.disabled = true;
    notUseful.disabled = true;
    try {
      await fetchJson('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          scenario_id: state.scenarioId,
          tenant_id: els.tenantInput.value.trim() || 'default',
          dataset_id: els.datasetInput.value.trim() || 'default',
          question,
          answer,
          rating,
          sources
        })
      });
      wrapper.textContent = '反馈已记录';
    } catch {
      wrapper.textContent = '反馈暂未保存';
    }
  };

  useful.addEventListener('click', () => submit('useful'));
  notUseful.addEventListener('click', () => submit('not_useful'));
  wrapper.append(label, useful, notUseful);
  return wrapper;
}

function setConnectionState(type, text) {
  const map = { ready: 'ok', error: 'error', connecting: 'warn', disconnected: '' };
  const state = map[type] || '';
  els.connectionPill.className = `pill ${state}`;
  els.connectionPill.innerHTML = `<i class="fas fa-circle"></i><span>${escapeHtml(text)}</span>`;
}

function updateSendState() {
  els.sendBtn.classList.toggle('is-stopping', state.inProgress);
  els.sendBtn.title = state.inProgress ? '停止' : '发送';
  els.sendBtn.innerHTML = state.inProgress ? '<i class="fas fa-stop"></i>' : '<i class="fas fa-paper-plane"></i>';
}

function autoResizeInput() {
  els.chatInput.style.height = 'auto';
  els.chatInput.style.height = `${Math.min(els.chatInput.scrollHeight, 160)}px`;
}

function scrollToBottom() {
  els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
}

/* ---- Toast notification system ---- */
function showToast(message, type = 'info', duration = 3500) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: 'fa-circle-check', error: 'fa-circle-exclamation', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <i class="fas ${icons[type] || icons.info} toast-icon"></i>
    <span class="toast-message">${escapeHtml(message)}</span>
    <button class="toast-close" aria-label="关闭"><i class="fas fa-xmark"></i></button>
  `;
  toast.querySelector('.toast-close').addEventListener('click', () => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 200);
  });

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      setTimeout(() => toast.remove(), 200);
    }
  }, duration);
}
