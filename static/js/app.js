/* 问答页启动入口：绑定交互事件，加载业务场景并建立首个会话；启动失败时保留可理解的页面状态。 */
document.addEventListener('DOMContentLoaded', async () => {
  bindEvents();
  try {
    await loadScenarios();
  } catch {
    renderWelcome('业务场景加载失败，请检查后端服务和场景配置。');
    return;
  }
  try {
    await createNewSession();
  } catch (error) {
    els.sessionInfo.textContent = `会话创建失败：${error.message || '请稍后重试'}`;
    renderWelcome('业务场景已加载，会话暂不可用。');
    updateSideStats();
    return;
  }
  renderWelcome();
});

function bindEvents() {
  els.newSessionBtn.addEventListener('click', createNewSession);
  els.sidebarNewSessionBtn.addEventListener('click', createNewSession);
  els.clearHistoryBtn.addEventListener('click', clearHistory);
  els.sendBtn.addEventListener('click', () => state.inProgress ? cancelStream() : sendMessage());
  els.scenarioSelect.addEventListener('change', async () => {
    if (state.inProgress) cancelStream();
    await applyScenario(els.scenarioSelect.value, true);
  });
  [els.sourceFilter, els.tenantInput, els.datasetInput, els.visibilitySelect, els.roleSelect].forEach(item => {
    item.addEventListener('change', updateScopeDisplay);
    item.addEventListener('input', updateScopeDisplay);
  });
  els.chatInput.addEventListener('input', autoResizeInput);
  els.chatInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!state.inProgress) sendMessage();
    }
  });
}
