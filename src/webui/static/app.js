const App = (() => {
  let groupId = null;

  const statusText = document.getElementById("statusText");
  const currentGroup = document.getElementById("currentGroup");
  const summaryGroup = document.getElementById("summaryGroup");
  const summaryVibe = document.getElementById("summaryVibe");
  const summaryThoughts = document.getElementById("summaryThoughts");
  const summaryMood = document.getElementById("summaryMood");
  const summaryMoodHint = document.getElementById("summaryMoodHint");

  const memoryTable = document.getElementById("memoryTable");
  const slangTable = document.getElementById("slangTable");
  const styleTable = document.getElementById("styleTable");
  const knowledgeTable = document.getElementById("knowledgeTable");
  const moodHistory = document.getElementById("moodHistory");

  const groupSelect = document.getElementById("groupSelect");
  const groupManualInput = document.getElementById("groupManualInput");
  const memoryUserId = document.getElementById("memoryUserId");
  const memoryKeyword = document.getElementById("memoryKeyword");
  const memoryAddUserId = document.getElementById("memoryAddUserId");
  const memoryAddUserName = document.getElementById("memoryAddUserName");
  const memoryAddContent = document.getElementById("memoryAddContent");
  const slangKeyword = document.getElementById("slangKeyword");
  const slangStage = document.getElementById("slangStage");
  const slangPhraseInput = document.getElementById("slangPhraseInput");
  const slangDeltaInput = document.getElementById("slangDeltaInput");
  const slangStageInput = document.getElementById("slangStageInput");
  const slangDefinitionInput = document.getElementById("slangDefinitionInput");
  const slangSamplesInput = document.getElementById("slangSamplesInput");
  const styleKeyword = document.getElementById("styleKeyword");
  const styleContextInput = document.getElementById("styleContextInput");
  const styleDescInput = document.getElementById("styleDescInput");
  const styleVibeInput = document.getElementById("styleVibeInput");
  const recentThoughtsInput = document.getElementById("recentThoughtsInput");

  const impressionUserId = document.getElementById("impressionUserId");
  const impressionUserName = document.getElementById("impressionUserName");
  const impressionText = document.getElementById("impressionText");

  const relationUserId = document.getElementById("relationUserId");
  const relationUserName = document.getElementById("relationUserName");
  const relationDelta = document.getElementById("relationDelta");
  const relationStatus = document.getElementById("relationStatus");
  const relationValue = document.getElementById("relationValue");

  const knowledgeSubjectFilter = document.getElementById("knowledgeSubjectFilter");
  const knowledgeSubject = document.getElementById("knowledgeSubject");
  const knowledgePredicate = document.getElementById("knowledgePredicate");
  const knowledgeObject = document.getElementById("knowledgeObject");
  const knowledgeConfidence = document.getElementById("knowledgeConfidence");
  const knowledgeDeleteSubject = document.getElementById("knowledgeDeleteSubject");
  const knowledgeDeletePredicate = document.getElementById("knowledgeDeletePredicate");
  const knowledgeDeleteObject = document.getElementById("knowledgeDeleteObject");

  const moodValue = document.getElementById("moodValue");
  const scheduleDate = document.getElementById("scheduleDate");
  const scheduleJson = document.getElementById("scheduleJson");

  const setStatus = (text) => {
    statusText.textContent = text;
  };

  const fetchJson = async (url, options = {}) => {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "请求失败");
    }
    return data;
  };

  const ensureGroup = () => {
    if (!groupId) {
      throw new Error("请先选择群组");
    }
  };

  const renderEmpty = (container, text) => {
    container.innerHTML = `<div class="row"><div class="row-title">${text}</div></div>`;
  };

  const setActiveTab = (tabId) => {
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.tab === tabId);
    });
    document.querySelectorAll(".tab-section").forEach((section) => {
      section.classList.toggle("active", section.id === `tab-${tabId}`);
    });
  };

  const bindTabs = () => {
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.addEventListener("click", () => setActiveTab(item.dataset.tab));
    });
  };

  const renderMemories = (items) => {
    if (!items.length) {
      return renderEmpty(memoryTable, "暂无记忆");
    }
    memoryTable.innerHTML = items
      .map(
        (item) => `
        <div class="row">
          <div class="row-title">${item.content}</div>
          <div class="row-meta">用户: ${item.user_name || "-"} (${item.user_id}) · ${item.created_at}</div>
          <div class="row-actions">
            <button class="ghost" onclick="App.deleteMemory(${item.id})">删除</button>
          </div>
        </div>
      `
      )
      .join("");
  };

  const stageName = (stage) => {
    const map = { 1: "观察中", 2: "验证中", 3: "已采纳", 4: "已废弃" };
    return map[stage] || "未知";
  };

  const renderSlangs = (items) => {
    if (!items.length) {
      return renderEmpty(slangTable, "暂无黑话");
    }
    slangTable.innerHTML = items
      .map(
        (item) => `
        <div class="row">
          <div class="row-title">${item.phrase}</div>
          <div class="row-meta">频率 ${item.frequency} · ${stageName(item.stage)}</div>
          <div class="row-meta">${item.definition || "暂无定义"}</div>
          <div class="row-actions">
            <button class="ghost" onclick="App.deleteSlang('${item.phrase}')">删除</button>
          </div>
        </div>
      `
      )
      .join("");
  };

  const renderStyles = (items) => {
    if (!items.length) {
      return renderEmpty(styleTable, "暂无风格模式");
    }
    styleTable.innerHTML = items
      .map(
        (item) => `
        <div class="row">
          <div class="row-title">${item.context}</div>
          <div>${item.style_desc}</div>
          <div class="row-meta">权重 ${item.weight} · ${item.updated_at}</div>
          <div class="row-actions">
            <button class="ghost" onclick="App.deleteStyle(${item.id})">删除</button>
          </div>
        </div>
      `
      )
      .join("");
  };

  const applyGroup = async (value) => {
    if (!value) {
      return setStatus("请选择群组或输入群组ID");
    }
    groupId = value;
    currentGroup.textContent = value;
    summaryGroup.textContent = value;
    await refreshAll();
  };

  const applyManualGroup = async () => {
    const value = groupManualInput.value.trim();
    await applyGroup(value);
  };

  const reloadGroups = async () => {
    const data = await fetchJson("/api/groups");
    const items = data.items || [];
    groupSelect.innerHTML = items.length
      ? items
          .map((item) => {
            const moodText = item.mood !== null && item.mood !== undefined ? `心情 ${item.mood}` : "暂无心情";
            return `<option value="${item.group_id}">${item.group_id} · ${moodText}</option>`;
          })
          .join("")
      : `<option value="">暂无群组</option>`;
    if (items.length && !groupId) {
      await applyGroup(String(items[0].group_id));
      groupSelect.value = String(items[0].group_id);
    }
  };

  const loadPersonality = async () => {
    ensureGroup();
    setStatus("加载人格状态...");
    const data = await fetchJson(`/api/personality?group_id=${groupId}`);
    summaryVibe.textContent = data.state.style_vibe || "-";
    summaryThoughts.textContent = data.state.recent_thoughts || "-";
    styleVibeInput.value = data.state.style_vibe || "";
    recentThoughtsInput.value = data.state.recent_thoughts || "";
    setStatus("人格状态已更新");
  };

  const savePersonality = async () => {
    ensureGroup();
    setStatus("保存中...");
    await fetchJson("/api/personality", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        style_vibe: styleVibeInput.value.trim(),
        recent_thoughts: recentThoughtsInput.value.trim(),
      }),
    });
    await loadPersonality();
  };

  const loadMemories = async () => {
    ensureGroup();
    setStatus("加载记忆...");
    const params = new URLSearchParams({ group_id: groupId });
    if (memoryUserId.value.trim()) {
      params.set("user_id", memoryUserId.value.trim());
    }
    if (memoryKeyword.value.trim()) {
      params.set("keyword", memoryKeyword.value.trim());
    }
    const data = await fetchJson(`/api/memories?${params.toString()}`);
    renderMemories(data.items || []);
    setStatus("记忆已更新");
  };

  const deleteMemory = async (id) => {
    ensureGroup();
    if (!confirm("确定删除这条记忆？")) return;
    await fetchJson(`/api/memories/${id}`, { method: "DELETE" });
    await loadMemories();
  };

  const addMemory = async () => {
    ensureGroup();
    setStatus("提交记忆中...");
    await fetchJson("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        user_id: memoryAddUserId.value.trim(),
        user_name: memoryAddUserName.value.trim(),
        content: memoryAddContent.value.trim(),
      }),
    });
    memoryAddContent.value = "";
    await loadMemories();
  };

  const loadSlang = async () => {
    ensureGroup();
    setStatus("加载黑话...");
    const params = new URLSearchParams({ group_id: groupId });
    if (slangKeyword.value.trim()) {
      params.set("keyword", slangKeyword.value.trim());
    }
    if (slangStage.value) {
      params.set("stage", slangStage.value);
    }
    const data = await fetchJson(`/api/slangs?${params.toString()}`);
    renderSlangs(data.items || []);
    setStatus("黑话已更新");
  };

  const deleteSlang = async (phrase) => {
    ensureGroup();
    if (!confirm(`确定删除黑话 “${phrase}”？`)) return;
    const params = new URLSearchParams({ group_id: groupId, phrase });
    await fetchJson(`/api/slangs?${params.toString()}`, { method: "DELETE" });
    await loadSlang();
  };

  const upsertSlang = async () => {
    ensureGroup();
    setStatus("提交黑话...");
    const samples = slangSamplesInput.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    await fetchJson("/api/slangs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        phrase: slangPhraseInput.value.trim(),
        delta_freq: slangDeltaInput.value.trim() || 1,
        stage: slangStageInput.value || null,
        definition: slangDefinitionInput.value.trim(),
        context_samples: samples,
      }),
    });
    slangPhraseInput.value = "";
    slangDeltaInput.value = "";
    slangDefinitionInput.value = "";
    slangSamplesInput.value = "";
    await loadSlang();
  };

  const loadStyles = async () => {
    ensureGroup();
    setStatus("加载风格...");
    const params = new URLSearchParams({ group_id: groupId });
    if (styleKeyword.value.trim()) {
      params.set("keyword", styleKeyword.value.trim());
    }
    const data = await fetchJson(`/api/styles?${params.toString()}`);
    renderStyles(data.items || []);
    setStatus("风格已更新");
  };

  const deleteStyle = async (id) => {
    ensureGroup();
    if (!confirm("确定删除该风格模式？")) return;
    await fetchJson(`/api/styles/${id}`, { method: "DELETE" });
    await loadStyles();
  };

  const addStyle = async () => {
    ensureGroup();
    setStatus("提交风格...");
    await fetchJson("/api/styles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        context: styleContextInput.value.trim(),
        style_desc: styleDescInput.value.trim(),
      }),
    });
    styleContextInput.value = "";
    styleDescInput.value = "";
    await loadStyles();
  };

  const loadImpression = async () => {
    ensureGroup();
    setStatus("加载用户印象...");
    const userId = impressionUserId.value.trim();
    const data = await fetchJson(`/api/user/impression?group_id=${groupId}&user_id=${userId}`);
    impressionText.value = data.impression || "";
    setStatus("用户印象已加载");
  };

  const saveImpression = async () => {
    ensureGroup();
    setStatus("保存用户印象...");
    await fetchJson("/api/user/impression", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        user_id: impressionUserId.value.trim(),
        user_name: impressionUserName.value.trim(),
        impression: impressionText.value.trim(),
      }),
    });
    setStatus("用户印象已保存");
  };

  const loadRelationship = async () => {
    ensureGroup();
    setStatus("加载用户关系...");
    const userId = relationUserId.value.trim();
    const data = await fetchJson(`/api/user/relationship?group_id=${groupId}&user_id=${userId}`);
    relationValue.textContent = `${data.favorability} · ${data.status}`;
    setStatus("用户关系已加载");
  };

  const updateRelationship = async () => {
    ensureGroup();
    setStatus("更新用户关系...");
    const data = await fetchJson("/api/user/relationship", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        user_id: relationUserId.value.trim(),
        user_name: relationUserName.value.trim(),
        delta_favorability: relationDelta.value.trim() || 0,
        status: relationStatus.value.trim() || null,
      }),
    });
    relationValue.textContent = `${data.favorability} · ${data.status}`;
    setStatus("用户关系已更新");
  };

  const renderKnowledge = (items) => {
    if (!items.length) {
      return renderEmpty(knowledgeTable, "暂无知识");
    }
    knowledgeTable.innerHTML = items
      .map(
        (item) => `
        <div class="row">
          <div class="row-title">${item.subject} · ${item.predicate} · ${item.object}</div>
          <div class="row-meta">置信度 ${item.confidence}</div>
        </div>
      `
      )
      .join("");
  };

  const loadKnowledge = async () => {
    ensureGroup();
    setStatus("加载知识...");
    const params = new URLSearchParams({ group_id: groupId });
    if (knowledgeSubjectFilter.value.trim()) {
      params.set("subject", knowledgeSubjectFilter.value.trim());
    }
    const data = await fetchJson(`/api/knowledge?${params.toString()}`);
    renderKnowledge(data.items || []);
    setStatus("知识已更新");
  };

  const addKnowledge = async () => {
    ensureGroup();
    setStatus("提交知识...");
    await fetchJson("/api/knowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: groupId,
        subject: knowledgeSubject.value.trim(),
        predicate: knowledgePredicate.value.trim(),
        object: knowledgeObject.value.trim(),
        confidence: knowledgeConfidence.value.trim() || 1,
      }),
    });
    knowledgeSubject.value = "";
    knowledgePredicate.value = "";
    knowledgeObject.value = "";
    knowledgeConfidence.value = "";
    await loadKnowledge();
  };

  const deleteKnowledge = async () => {
    ensureGroup();
    setStatus("删除知识...");
    const params = new URLSearchParams({ group_id: groupId });
    if (knowledgeDeleteSubject.value.trim()) {
      params.set("subject", knowledgeDeleteSubject.value.trim());
    }
    if (knowledgeDeletePredicate.value.trim()) {
      params.set("predicate", knowledgeDeletePredicate.value.trim());
    }
    if (knowledgeDeleteObject.value.trim()) {
      params.set("object", knowledgeDeleteObject.value.trim());
    }
    const data = await fetchJson(`/api/knowledge?${params.toString()}`, { method: "DELETE" });
    setStatus(`已删除 ${data.deleted || 0} 条知识`);
    await loadKnowledge();
  };

  const renderMoodHistory = (items) => {
    if (!items.length) {
      return renderEmpty(moodHistory, "暂无心情变化");
    }
    moodHistory.innerHTML = items
      .map(
        (item) => `
        <div class="row">
          <div class="row-title">变化 ${item.mood_delta}</div>
          <div class="row-meta">${item.timestamp}</div>
        </div>
      `
      )
      .join("");
  };

  const loadMood = async () => {
    ensureGroup();
    const data = await fetchJson(`/api/mood?group_id=${groupId}`);
    const history = await fetchJson(`/api/mood/history?group_id=${groupId}&count=8`);
    moodValue.textContent = data.mood;
    summaryMood.textContent = data.mood;
    if (history.items && history.items.length) {
      summaryMoodHint.textContent = `最近变化：${history.items[0].mood_delta}`;
    }
    renderMoodHistory(history.items || []);
  };

  const updateMood = async (delta) => {
    ensureGroup();
    await fetchJson("/api/mood", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_id: groupId, delta }),
    });
    await loadMood();
  };

  const loadSchedule = async () => {
    ensureGroup();
    const dateValue = scheduleDate.value;
    if (!dateValue) {
      return setStatus("请选择日期");
    }
    const data = await fetchJson(`/api/schedule?group_id=${groupId}&date=${dateValue}`);
    scheduleJson.value = JSON.stringify(data.items || [], null, 2);
    setStatus("作息已加载");
  };

  const saveSchedule = async () => {
    ensureGroup();
    const dateValue = scheduleDate.value;
    if (!dateValue) {
      return setStatus("请选择日期");
    }
    let schedule = [];
    try {
      schedule = JSON.parse(scheduleJson.value || "[]");
    } catch (error) {
      return setStatus("作息 JSON 格式不正确");
    }
    await fetchJson("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_id: groupId, date: dateValue, schedule }),
    });
    setStatus("作息已保存");
  };

  const refreshAll = async () => {
    try {
      ensureGroup();
      await Promise.all([loadPersonality(), loadMemories(), loadSlang(), loadStyles(), loadMood()]);
    } catch (error) {
      setStatus(error.message);
    }
  };

  const init = async () => {
    bindTabs();
    groupSelect.addEventListener("change", async (event) => {
      if (event.target.value) {
        await applyGroup(event.target.value);
      }
    });
    await reloadGroups();
  };

  return {
    applyGroup,
    applyManualGroup,
    reloadGroups,
    refreshAll,
    loadMemories,
    addMemory,
    deleteMemory,
    loadSlang,
    upsertSlang,
    deleteSlang,
    loadStyles,
    addStyle,
    deleteStyle,
    loadPersonality,
    savePersonality,
    loadImpression,
    saveImpression,
    loadRelationship,
    updateRelationship,
    loadKnowledge,
    addKnowledge,
    deleteKnowledge,
    loadMood,
    updateMood,
    loadSchedule,
    saveSchedule,
    init,
  };
})();

window.App = App;
window.addEventListener("DOMContentLoaded", () => {
  App.init();
});
