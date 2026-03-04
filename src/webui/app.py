"""
轻量 Web UI
用于管理 bot 的记忆、黑话、风格与人格等数据
"""

from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.utils.db_manager import db_manager
from src.utils.error_handler import handle_errors
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="TingFengBot 管理面板", docs_url="/api/docs", redoc_url=None)

app.mount("/static", StaticFiles(directory="src/webui/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """主页"""
    return HTMLResponse(
        """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>TingFengBot 管理中心</title>
  <link rel=\"stylesheet\" href=\"/static/styles.css\" />
</head>
<body>
  <div class=\"page\">
    <header class=\"hero\">
      <div class=\"hero-top\">
        <div>
          <div class=\"hero-title\">TingFengBot 管理中心</div>
          <div class=\"hero-sub\">以群组为核心的管理台，统一维护记忆、黑话、风格与人格数据</div>
        </div>
        <div class=\"hero-actions\">
          <button class=\"primary\" onclick=\"App.refreshAll()\">一键刷新</button>
          <span class=\"status\" id=\"statusText\">等待加载</span>
        </div>
      </div>
    </header>

    <div class=\"layout\">
      <aside class=\"side\">
        <div class=\"group-card\">
          <div class=\"group-title\">群组选择</div>
          <div class=\"group-row\">
            <select id=\"groupSelect\"></select>
            <button class=\"ghost\" onclick=\"App.reloadGroups()\">刷新</button>
          </div>
          <div class=\"group-row\">
            <input id=\"groupManualInput\" placeholder=\"手动输入群组ID\" />
            <button onclick=\"App.applyManualGroup()\">应用</button>
          </div>
          <div class=\"group-meta\">
            当前群组：<span id=\"currentGroup\">未设置</span>
          </div>
        </div>

        <nav class=\"nav\">
          <button class=\"nav-item active\" data-tab=\"overview\">总览</button>
          <button class=\"nav-item\" data-tab=\"personality\">人格</button>
          <button class=\"nav-item\" data-tab=\"memories\">记忆</button>
          <button class=\"nav-item\" data-tab=\"slang\">黑话</button>
          <button class=\"nav-item\" data-tab=\"styles\">风格</button>
          <button class=\"nav-item\" data-tab=\"users\">用户</button>
          <button class=\"nav-item\" data-tab=\"knowledge\">知识</button>
          <button class=\"nav-item\" data-tab=\"mood\">心情/作息</button>
        </nav>
      </aside>

      <main class=\"content\">
        <section class=\"tab-section active\" id=\"tab-overview\">
          <div class=\"section-title\">总览</div>
          <div class=\"card-grid\">
            <div class=\"stat-card\">
              <div class=\"stat-label\">当前群组</div>
              <div class=\"stat-value\" id=\"summaryGroup\">未设置</div>
              <div class=\"helper\">从侧边栏选择群组即可加载数据</div>
            </div>
            <div class=\"stat-card\">
              <div class=\"stat-label\">人格基调</div>
              <div class=\"stat-value\" id=\"summaryVibe\">—</div>
              <div class=\"helper\" id=\"summaryThoughts\">—</div>
            </div>
            <div class=\"stat-card\">
              <div class=\"stat-label\">当前心情值</div>
              <div class=\"stat-value\" id=\"summaryMood\">—</div>
              <div class=\"helper\" id=\"summaryMoodHint\">最近变化：暂无</div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-personality\">
          <div class=\"section-title\">人格与风格基调</div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">当前人格状态</div>
              <div class=\"panel-actions\">
                <button class=\"ghost\" onclick=\"App.loadPersonality()\">刷新</button>
              </div>
            </div>
            <div class=\"panel-body\">
              <div class=\"form\">
                <label>风格基调</label>
                <input id=\"styleVibeInput\" placeholder=\"如：正常聊天 / 慵懒 / 活泼\" />
                <label>近期想法</label>
                <textarea id=\"recentThoughtsInput\" rows=\"4\" placeholder=\"可为空\"></textarea>
                <button class=\"primary\" onclick=\"App.savePersonality()\">保存</button>
              </div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-memories\">
          <div class=\"section-title\">记忆管理</div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">查询记忆</div>
              <div class=\"panel-actions\">
                <input id=\"memoryUserId\" placeholder=\"用户ID(可选)\" />
                <input id=\"memoryKeyword\" placeholder=\"关键词\" />
                <button onclick=\"App.loadMemories()\">查询</button>
              </div>
            </div>
            <div class=\"panel-body\">
              <div class=\"table\" id=\"memoryTable\"></div>
            </div>
          </div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">新增记忆</div>
            </div>
            <div class=\"panel-body\">
              <div class=\"form\">
                <div class=\"form-row\">
                  <input id=\"memoryAddUserId\" placeholder=\"用户ID\" />
                  <input id=\"memoryAddUserName\" placeholder=\"用户名\" />
                </div>
                <textarea id=\"memoryAddContent\" rows=\"3\" placeholder=\"记忆内容\"></textarea>
                <button class=\"primary\" onclick=\"App.addMemory()\">提交</button>
              </div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-slang\">
          <div class=\"section-title\">黑话管理</div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">查询黑话</div>
              <div class=\"panel-actions\">
                <input id=\"slangKeyword\" placeholder=\"关键词\" />
                <select id=\"slangStage\">
                  <option value=\"\">阶段(全部)</option>
                  <option value=\"1\">观察中</option>
                  <option value=\"2\">验证中</option>
                  <option value=\"3\">已采纳</option>
                  <option value=\"4\">已废弃</option>
                </select>
                <button onclick=\"App.loadSlang()\">查询</button>
              </div>
            </div>
            <div class=\"panel-body\">
              <div class=\"table\" id=\"slangTable\"></div>
            </div>
          </div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">新增/更新黑话</div>
            </div>
            <div class=\"panel-body\">
              <div class=\"form\">
                <div class=\"form-row\">
                  <input id=\"slangPhraseInput\" placeholder=\"黑话\" />
                  <input id=\"slangDeltaInput\" placeholder=\"频次增量(默认1)\" />
                  <select id=\"slangStageInput\">
                    <option value=\"\">阶段(可选)</option>
                    <option value=\"1\">观察中</option>
                    <option value=\"2\">验证中</option>
                    <option value=\"3\">已采纳</option>
                    <option value=\"4\">已废弃</option>
                  </select>
                </div>
                <input id=\"slangDefinitionInput\" placeholder=\"定义(可选)\" />
                <textarea id=\"slangSamplesInput\" rows=\"3\" placeholder=\"语境样例，换行分隔\"></textarea>
                <button class=\"primary\" onclick=\"App.upsertSlang()\">提交</button>
              </div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-styles\">
          <div class=\"section-title\">风格模式</div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">查询风格</div>
              <div class=\"panel-actions\">
                <input id=\"styleKeyword\" placeholder=\"关键词\" />
                <button onclick=\"App.loadStyles()\">查询</button>
              </div>
            </div>
            <div class=\"panel-body\">
              <div class=\"table\" id=\"styleTable\"></div>
            </div>
          </div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">新增风格模式</div>
            </div>
            <div class=\"panel-body\">
              <div class=\"form\">
                <input id=\"styleContextInput\" placeholder=\"情境\" />
                <textarea id=\"styleDescInput\" rows=\"3\" placeholder=\"风格描述\"></textarea>
                <button class=\"primary\" onclick=\"App.addStyle()\">提交</button>
              </div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-users\">
          <div class=\"section-title\">用户管理</div>
          <div class=\"grid\">
            <div class=\"panel\">
              <div class=\"panel-header\">
                <div class=\"panel-title\">用户印象</div>
              </div>
              <div class=\"panel-body\">
                <div class=\"form\">
                  <div class=\"form-row\">
                    <input id=\"impressionUserId\" placeholder=\"用户ID\" />
                    <input id=\"impressionUserName\" placeholder=\"用户名\" />
                  </div>
                  <textarea id=\"impressionText\" rows=\"4\" placeholder=\"印象描述（支持增量更新）\"></textarea>
                  <div class=\"helper\" style=\"margin-top: 8px; font-size: 12px;\">
                    <strong>增量更新：</strong>+添加 -删除 ~旧|新 智能合并自动去重
                  </div>
                  <div class=\"form-row\">
                    <button class=\"ghost\" onclick=\"App.loadImpression()\">加载</button>
                    <button class=\"primary\" onclick=\"App.saveImpression()\">保存</button>
                  </div>
                </div>
              </div>
            </div>
            <div class=\"panel\">
              <div class=\"panel-header\">
                <div class=\"panel-title\">用户关系</div>
              </div>
              <div class=\"panel-body\">
                <div class=\"form\">
                  <div class=\"form-row\">
                    <input id=\"relationUserId\" placeholder=\"用户ID\" />
                    <input id=\"relationUserName\" placeholder=\"用户名\" />
                  </div>
                  <div class=\"form-row\">
                    <input id=\"relationDelta\" placeholder=\"好感度增量(可负数)\" />
                    <input id=\"relationStatus\" placeholder=\"关系状态(可选)\" />
                  </div>
                  <div class=\"relation-info\">
                    当前：<span id=\"relationValue\">—</span>
                  </div>
                  <div class=\"form-row\">
                    <button class=\"ghost\" onclick=\"App.loadRelationship()\">加载</button>
                    <button class=\"primary\" onclick=\"App.updateRelationship()\">更新</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-knowledge\">
          <div class=\"section-title\">知识三元组</div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">查询知识</div>
              <div class=\"panel-actions\">
                <input id=\"knowledgeSubjectFilter\" placeholder=\"主体(可选)\" />
                <button onclick=\"App.loadKnowledge()\">查询</button>
              </div>
            </div>
            <div class=\"panel-body\">
              <div class=\"table\" id=\"knowledgeTable\"></div>
            </div>
          </div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">新增知识</div>
            </div>
            <div class=\"panel-body\">
              <div class=\"form\">
                <div class=\"form-row\">
                  <input id=\"knowledgeSubject\" placeholder=\"主体\" />
                  <input id=\"knowledgePredicate\" placeholder=\"谓语\" />
                  <input id=\"knowledgeObject\" placeholder=\"客体\" />
                </div>
                <input id=\"knowledgeConfidence\" placeholder=\"置信度(0-1，默认1)\" />
                <button class=\"primary\" onclick=\"App.addKnowledge()\">提交</button>
              </div>
            </div>
          </div>
          <div class=\"panel\">
            <div class=\"panel-header\">
              <div class=\"panel-title\">删除知识</div>
            </div>
            <div class=\"panel-body\">
              <div class=\"form\">
                <div class=\"form-row\">
                  <input id=\"knowledgeDeleteSubject\" placeholder=\"主体(可选)\" />
                  <input id=\"knowledgeDeletePredicate\" placeholder=\"谓语(可选)\" />
                  <input id=\"knowledgeDeleteObject\" placeholder=\"客体(可选)\" />
                </div>
                <button class=\"primary\" onclick=\"App.deleteKnowledge()\">执行删除</button>
              </div>
            </div>
          </div>
        </section>

        <section class=\"tab-section\" id=\"tab-mood\">
          <div class=\"section-title\">心情与作息</div>
          <div class=\"grid\">
            <div class=\"panel\">
              <div class=\"panel-header\">
                <div class=\"panel-title\">心情值</div>
                <div class=\"panel-actions\">
                  <button class=\"ghost\" onclick=\"App.loadMood()\">刷新</button>
                </div>
              </div>
              <div class=\"panel-body\">
                <div class=\"stat-line\">当前心情：<span id=\"moodValue\">—</span></div>
                <div class=\"mood-actions\">
                  <button onclick=\"App.updateMood(-10)\">-10</button>
                  <button onclick=\"App.updateMood(-5)\">-5</button>
                  <button onclick=\"App.updateMood(5)\">+5</button>
                  <button onclick=\"App.updateMood(10)\">+10</button>
                </div>
                <div class=\"sub-title\">最近变化</div>
                <div class=\"table\" id=\"moodHistory\"></div>
              </div>
            </div>
            <div class=\"panel\">
              <div class=\"panel-header\">
                <div class=\"panel-title\">作息表</div>
                <div class=\"panel-actions\">
                  <input id=\"scheduleDate\" type=\"date\" />
                  <button class=\"ghost\" onclick=\"App.loadSchedule()\">加载</button>
                </div>
              </div>
              <div class=\"panel-body\">
                <textarea id=\"scheduleJson\" class=\"code\" rows=\"10\" placeholder=\"JSON 数组，例如：[{&quot;time&quot;:&quot;08:00&quot;,&quot;task&quot;:&quot;晨间问候&quot;}]\"></textarea>
                <button class=\"primary\" onclick=\"App.saveSchedule()\">保存作息</button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>

    <footer class=\"footer\">
      <span>API: /api/*</span>
      <span>简单易用 · 本地运行</span>
    </footer>
  </div>
  <script src="/static/app.js?v=2"></script>
 </body>
 </html>"""
    )


def _require_group_id(value: str) -> int:
    if not value or not value.isdigit():
        raise ValueError("无效的群组ID")
    return int(value)


@app.get("/api/ping")
async def ping() -> Dict[str, Any]:
    """健康检查"""
    return {"ok": True}


@app.get("/api/personality")
@handle_errors(default_return={"error": "获取人格状态失败"}, log_level="ERROR")
async def get_personality(request: Request) -> Dict[str, Any]:
    """获取人格状态"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    state = await db_manager.get_personality_state(group_id)
    return {"group_id": group_id, "state": state}


@app.post("/api/personality")
@handle_errors(default_return={"error": "更新人格状态失败"}, log_level="ERROR")
async def update_personality(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新人格状态"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    vibe_value = payload.get("style_vibe")
    thoughts_value = payload.get("recent_thoughts")
    vibe = str(vibe_value) if vibe_value is not None else None
    thoughts = str(thoughts_value) if thoughts_value is not None else None
    await db_manager.update_personality_state(group_id, thoughts=thoughts, vibe=vibe)
    state = await db_manager.get_personality_state(group_id)
    return {"group_id": group_id, "state": state}


@app.get("/api/memories")
@handle_errors(default_return={"items": [], "error": "获取记忆失败"}, log_level="ERROR")
async def list_memories(request: Request) -> Dict[str, Any]:
    """获取记忆列表"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    user_id = request.query_params.get("user_id")
    keyword = request.query_params.get("keyword")
    limit = int(request.query_params.get("limit", "50"))
    offset = int(request.query_params.get("offset", "0"))
    items = await db_manager.list_user_memories(
        group_id=group_id,
        user_id=int(user_id) if user_id and user_id.isdigit() else None,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return {"items": items}


@app.post("/api/memories")
@handle_errors(default_return={"error": "添加记忆失败"}, log_level="ERROR")
async def add_memory(payload: Dict[str, Any]) -> Dict[str, Any]:
    """添加记忆"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    user_id_raw = str(payload.get("user_id", "")).strip()
    if not user_id_raw.isdigit():
        raise ValueError("用户ID无效")
    user_id = int(user_id_raw)
    user_name = str(payload.get("user_name", "")).strip()
    if not user_name:
        raise ValueError("用户名不能为空")
    content = str(payload.get("content", "")).strip()
    if not content:
        raise ValueError("记忆内容不能为空")
    await db_manager.add_user_specific_memory(group_id, user_id, user_name, content)
    return {"ok": True}


@app.delete("/api/memories/{memory_id}")
@handle_errors(default_return={"error": "删除记忆失败"}, log_level="ERROR")
async def delete_memory(memory_id: int) -> Dict[str, Any]:
    """删除记忆"""
    deleted = await db_manager.delete_user_memory(memory_id)
    return {"deleted": deleted}


@app.get("/api/slangs")
@handle_errors(default_return={"items": [], "error": "获取黑话失败"}, log_level="ERROR")
async def list_slangs(request: Request) -> Dict[str, Any]:
    """获取黑话列表"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    stage = request.query_params.get("stage")
    min_freq = int(request.query_params.get("min_freq", "0"))
    keyword = request.query_params.get("keyword")
    limit = int(request.query_params.get("limit", "100"))
    offset = int(request.query_params.get("offset", "0"))
    items = await db_manager.list_slang_candidates(
        group_id=group_id,
        stage=int(stage) if stage and stage.isdigit() else None,
        min_freq=min_freq,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return {"items": items}


@app.post("/api/slangs")
@handle_errors(default_return={"error": "更新黑话失败"}, log_level="ERROR")
async def upsert_slang(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新黑话"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    phrase = str(payload.get("phrase", "")).strip()
    if not phrase:
        raise ValueError("黑话不能为空")
    delta_freq = int(payload.get("delta_freq", 0))
    stage_raw = payload.get("stage")
    stage = int(stage_raw) if stage_raw is not None and str(stage_raw).isdigit() else None
    definition_raw = payload.get("definition")
    definition = str(definition_raw).strip() if definition_raw is not None else None
    context_samples_raw = payload.get("context_samples")
    context_samples: Optional[List[str]] = None
    if isinstance(context_samples_raw, list):
        context_samples = [str(item).strip() for item in context_samples_raw if str(item).strip()]
    await db_manager.update_slang_candidate(
        group_id=group_id,
        phrase=phrase,
        delta_freq=delta_freq,
        stage=int(stage) if stage is not None else None,
        definition=definition,
        context_samples=context_samples,
    )
    return {"ok": True}


@app.delete("/api/slangs")
@handle_errors(default_return={"error": "删除黑话失败"}, log_level="ERROR")
async def delete_slang(request: Request) -> Dict[str, Any]:
    """删除黑话"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    phrase = request.query_params.get("phrase", "")
    if not phrase:
        raise ValueError("黑话不能为空")
    deleted = await db_manager.delete_slang_candidate(group_id, phrase)
    return {"deleted": deleted}


@app.get("/api/styles")
@handle_errors(default_return={"items": [], "error": "获取风格失败"}, log_level="ERROR")
async def list_styles(request: Request) -> Dict[str, Any]:
    """获取风格模式列表"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    keyword = request.query_params.get("keyword")
    limit = int(request.query_params.get("limit", "100"))
    offset = int(request.query_params.get("offset", "0"))
    items = await db_manager.list_style_patterns(
        group_id=group_id,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return {"items": items}


@app.post("/api/styles")
@handle_errors(default_return={"error": "添加风格失败"}, log_level="ERROR")
async def add_style(payload: Dict[str, Any]) -> Dict[str, Any]:
    """添加风格模式"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    context = str(payload.get("context", "")).strip()
    style_desc = str(payload.get("style_desc", "")).strip()
    if not context or not style_desc:
        raise ValueError("情境与风格描述不能为空")
    await db_manager.add_style_pattern(group_id, context, style_desc)
    return {"ok": True}


@app.delete("/api/styles/{style_id}")
@handle_errors(default_return={"error": "删除风格失败"}, log_level="ERROR")
async def delete_style(style_id: int) -> Dict[str, Any]:
    """删除风格模式"""
    deleted = await db_manager.delete_style_pattern_by_id(style_id)
    return {"deleted": deleted}


@app.get("/api/groups")
@handle_errors(default_return={"items": [], "error": "获取群组失败"}, log_level="ERROR")
async def list_groups() -> Dict[str, Any]:
    """获取群组列表"""
    groups = await db_manager.get_all_groups()
    moods = await db_manager.get_all_group_moods()
    mood_map = {group_id: mood for group_id, mood in moods}
    items = [{"group_id": group_id, "mood": mood_map.get(group_id)} for group_id in groups]
    return {"items": items}


@app.get("/api/user/impression")
@handle_errors(default_return={"error": "获取用户印象失败"}, log_level="ERROR")
async def get_impression(request: Request) -> Dict[str, Any]:
    """获取用户印象"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    user_id_raw = request.query_params.get("user_id", "")
    if not user_id_raw.isdigit():
        raise ValueError("用户ID无效")
    user_id = int(user_id_raw)
    impression = await db_manager.get_user_impression(group_id, user_id)
    # 同时查询用户名，方便前端自动填充
    user_name = await db_manager.get_user_name_by_id(group_id, user_id)
    return {"group_id": group_id, "user_id": user_id, "user_name": user_name or "", "impression": impression or ""}


@app.get("/api/user/impression/history")
@handle_errors(default_return={"items": [], "error": "获取印象历史失败"}, log_level="ERROR")
async def get_impression_history(request: Request) -> Dict[str, Any]:
    """获取用户印象历史"""
    user_id_raw = request.query_params.get("user_id", "")
    if not user_id_raw.isdigit():
        raise ValueError("用户ID无效")
    user_id = int(user_id_raw)
    limit = int(request.query_params.get("limit", "20"))
    items = await db_manager.get_user_impression_history(user_id, limit=limit)
    return {"items": items}


@app.post("/api/user/impression")
@handle_errors(default_return={"error": "更新用户印象失败"}, log_level="ERROR")
async def update_impression(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户印象"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    user_id_raw = str(payload.get("user_id", "")).strip()
    if not user_id_raw.isdigit():
        raise ValueError("用户ID无效")
    user_id = int(user_id_raw)
    user_name = str(payload.get("user_name", "")).strip()

    # 如果用户名为空，尝试从数据库查询
    if not user_name:
        user_name = await db_manager.get_user_name_by_id(group_id, user_id)
        if not user_name:
            raise ValueError(f"未找到用户ID {user_id} 对应的用户名，请确保该用户在群内发过言，或手动输入用户名")

    impression = str(payload.get("impression", "")).strip()
    if not impression:
        raise ValueError("印象不能为空")
    await db_manager.update_user_impression(group_id, user_id, user_name, impression)
    return {"ok": True}


@app.get("/api/user/relationship")
@handle_errors(default_return={"error": "获取用户关系失败"}, log_level="ERROR")
async def get_relationship(request: Request) -> Dict[str, Any]:
    """获取用户关系"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    user_id_raw = request.query_params.get("user_id", "")
    if not user_id_raw.isdigit():
        raise ValueError("用户ID无效")
    user_id = int(user_id_raw)
    data = await db_manager.get_user_relationship(group_id, user_id)
    return {"group_id": group_id, "user_id": user_id, "favorability": data["favorability"], "status": data["status"]}


@app.post("/api/user/relationship")
@handle_errors(default_return={"error": "更新用户关系失败"}, log_level="ERROR")
async def update_relationship(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户关系"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    user_id_raw = str(payload.get("user_id", "")).strip()
    if not user_id_raw.isdigit():
        raise ValueError("用户ID无效")
    user_id = int(user_id_raw)

    # 用户名可选：如果未提供，从现有记录获取
    user_name = str(payload.get("user_name", "")).strip()
    if not user_name:
        # 从现有记录获取用户名
        existing_data = await db_manager.get_user_relationship(group_id, user_id)
        # 尝试从数据库获取用户名
        async with await db_manager._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT user_name FROM user_relationships WHERE group_id = ? AND user_id = ?", (group_id, user_id)
            )
            row = await cursor.fetchone()
            if row:
                user_name = row[0]
            else:
                # 如果是新用户，使用用户ID作为默认用户名
                user_name = str(user_id)

    delta_raw = str(payload.get("delta_favorability", "0")).strip() or "0"
    if not delta_raw.lstrip("-").isdigit():
        raise ValueError("好感度增量无效")
    delta_favorability = int(delta_raw)
    status_raw = payload.get("status")
    status = str(status_raw).strip() if status_raw is not None and str(status_raw).strip() else None
    data = await db_manager.update_user_relationship(group_id, user_id, user_name, delta_favorability, status)
    return {"group_id": group_id, "user_id": user_id, "favorability": data["favorability"], "status": data["status"]}


@app.get("/api/knowledge")
@handle_errors(default_return={"items": [], "error": "获取知识失败"}, log_level="ERROR")
async def list_knowledge(request: Request) -> Dict[str, Any]:
    """获取知识三元组"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    subject = request.query_params.get("subject")
    limit = int(request.query_params.get("limit", "50"))
    items = await db_manager.get_knowledge_triplets(group_id, subject=subject, limit=limit)
    return {"items": items}


@app.post("/api/knowledge")
@handle_errors(default_return={"error": "添加知识失败"}, log_level="ERROR")
async def add_knowledge(payload: Dict[str, Any]) -> Dict[str, Any]:
    """添加知识三元组"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    subject = str(payload.get("subject", "")).strip()
    predicate = str(payload.get("predicate", "")).strip()
    obj = str(payload.get("object", "")).strip()
    if not subject or not predicate or not obj:
        raise ValueError("主体、谓语、客体不能为空")
    confidence_raw = payload.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        raise ValueError("置信度无效")
    await db_manager.add_knowledge_triplet(group_id, subject, predicate, obj, confidence=confidence)
    return {"ok": True}


@app.delete("/api/knowledge")
@handle_errors(default_return={"error": "删除知识失败"}, log_level="ERROR")
async def delete_knowledge(request: Request) -> Dict[str, Any]:
    """删除知识三元组"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    subject = request.query_params.get("subject")
    predicate = request.query_params.get("predicate")
    obj = request.query_params.get("object")
    deleted = await db_manager.delete_knowledge_triplet(group_id, subject=subject, predicate=predicate, obj=obj)
    return {"deleted": deleted}


@app.get("/api/mood")
@handle_errors(default_return={"error": "获取心情失败"}, log_level="ERROR")
async def get_mood(request: Request) -> Dict[str, Any]:
    """获取心情值"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    mood = await db_manager.get_mood(group_id)
    return {"group_id": group_id, "mood": mood}


@app.post("/api/mood")
@handle_errors(default_return={"error": "更新心情失败"}, log_level="ERROR")
async def update_mood(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新心情值"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    delta_raw = str(payload.get("delta", "0")).strip() or "0"
    if not delta_raw.lstrip("-").isdigit():
        raise ValueError("心情变化值无效")
    delta = int(delta_raw)
    mood = await db_manager.update_mood(group_id, delta)
    return {"group_id": group_id, "mood": mood}


@app.get("/api/mood/history")
@handle_errors(default_return={"items": [], "error": "获取心情记录失败"}, log_level="ERROR")
async def list_mood_history(request: Request) -> Dict[str, Any]:
    """获取心情变化记录"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    count = int(request.query_params.get("count", "10"))
    items = await db_manager.get_recent_mood_changes(group_id, count=count)
    return {"items": items}


@app.get("/api/schedule")
@handle_errors(default_return={"items": [], "error": "获取作息失败"}, log_level="ERROR")
async def get_schedule(request: Request) -> Dict[str, Any]:
    """获取作息表"""
    group_id = _require_group_id(request.query_params.get("group_id", ""))
    date_str = request.query_params.get("date", "").strip()
    if not date_str:
        raise ValueError("日期不能为空")
    items = await db_manager.get_bot_schedule(group_id, date_str)
    return {"items": items}


@app.post("/api/schedule")
@handle_errors(default_return={"error": "更新作息失败"}, log_level="ERROR")
async def update_schedule(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新作息表"""
    group_id = _require_group_id(str(payload.get("group_id", "")))
    date_str = str(payload.get("date", "")).strip()
    if not date_str:
        raise ValueError("日期不能为空")
    schedule = payload.get("schedule")
    if not isinstance(schedule, list):
        raise ValueError("作息必须是列表")
    await db_manager.update_bot_schedule(group_id, date_str, schedule)
    return {"ok": True}


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning(f"请求参数错误: {exc}")
    return JSONResponse(status_code=400, content={"error": str(exc)})
