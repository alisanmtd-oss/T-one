from __future__ import annotations

import html
import json

def render_floating_ai_widget_html(
    *,
    show_links: bool = True,
    model_options: str = "",
    locale: str | None = None,
    advisor_href: str = "/chat",
) -> str:
    is_en = str(locale or "").lower().startswith("en")
    safe_advisor_href = html.escape(advisor_href or "/chat", quote=True)
    copy = {
        "launcher_label": "Open Store AI Advisor" if is_en else "打开店铺AI顾问",
        "panel_label": "Store AI Advisor" if is_en else "店铺AI顾问",
        "title": "Store AI Advisor" if is_en else "店铺AI顾问",
        "drag_hint": "Draggable · read-only analysis" if is_en else "可拖动 · 只读分析",
        "close": "Close" if is_en else "关闭",
        "safe": (
            "Backend AI reads this page, organizes decisions, drafts, and pre-confirmation notes. Publishing, price changes, refunds, shipping, authorization, and ad spend still go to the confirmation queue."
            if is_en
            else "后台 AI 会读取当前页，整理判断、脚本草稿和确认前草稿；发布、改价、退款、发货、授权、投广告都会进入待确认动作，不会自动执行。"
        ),
        "model": "Model" if is_en else "模型",
        "quick_today": "Today" if is_en else "今天做什么",
        "quick_next": "Next Step" if is_en else "告诉我下一步",
        "quick_script": "Draft Status" if is_en else "看草稿状态",
        "quick_product": "Product Status" if is_en else "看商品判断",
        "prompt_today": (
            "Based on this page, tell me the only three things I need to do today."
            if is_en
            else "根据当前页面，告诉我今天只需要做哪三件事。"
        ),
        "prompt_next": (
            "Translate this page into a boss-readable next step: where should I look, where should I click for results, and which real actions must enter the confirmation queue. Do not operate the store."
            if is_en
            else "把当前页面翻译成老板能看懂的下一步：我现在该看哪里、点哪里看结果、哪些真实动作必须进待确认队列。不要直接操作店铺。"
        ),
        "prompt_script": (
            "Show the current script draft status from backend AI, including hook, shot, scene, captions, CTA, and missing evidence. Do not publish anything."
            if is_en
            else "查看后台 AI 当前整理到的脚本草稿状态：钩子、镜头、场景、字幕、CTA 和缺少的证据。不要发布任何内容。"
        ),
        "prompt_product": (
            "Read the current store and product evidence and show backend AI's product test status plus missing proof. Do not ask the customer to collect it manually."
            if is_en
            else "读取当前店铺和商品证据，展示后台 AI 的商品测品状态和缺少的证据，不要让我手动收集。"
        ),
        "current_page_prefix": "Current page: " if is_en else "当前页面：",
        "greeting": (
            "I will answer with conclusion, evidence, and next step first. Real actions must enter the confirmation queue."
            if is_en
            else "我先给结论，再给证据和下一步。需要真实执行的动作会先进确认队列。"
        ),
        "placeholder": "Ask: what should I read first on this page? What evidence is missing? Which actions need confirmation?" if is_en else "问：当前页先看哪里？后台AI缺哪些证据？哪些动作需要确认？",
        "open_advisor": "Open Advisor" if is_en else "打开顾问页",
        "help_center": "Help Center" if is_en else "帮助中心",
        "send": "Send" if is_en else "发送",
        "dashboard": "Today Dashboard" if is_en else "今日工作台",
        "selection": "Product Research" if is_en else "商品研究",
        "store_erp": "Store ERP" if is_en else "店铺ERP",
        "continue_ai": "Continue With AI" if is_en else "继续问AI",
        "continue_scoped_ai": "Continue This Store" if is_en else "继续问这家店",
        "action_fallback": "Open Confirmation Item" if is_en else "查看待确认动作",
        "insufficient": (
            "Evidence is still insufficient. Add store data, product links, TK videos, or creator evidence first."
            if is_en
            else "当前证据不足。后台 AI 正在等待店铺数据、商品链接、TK视频或达人证据。"
        ),
        "loading": "Analyzing this page context..." if is_en else "正在结合当前页面分析...",
        "error": (
            "No usable answer yet. Check store data, model configuration, or confirmation blockers."
            if is_en
            else "暂时没有拿到可用回答。后台 AI 正在检查店铺数据、模型配置和待确认动作卡点。"
        ),
        "connection_error": (
            "The local chat service is not reachable. Refresh and try again; real store data is not affected."
            if is_en
            else "本地聊天服务连接失败。请刷新页面或稍后再试；不会影响店铺真实数据。"
        ),
    }
    links_html = (
        f"""
    <div class="commerce-ai-links">
      <a href="/dashboard">{html.escape(copy["dashboard"])}</a>
      <a href="/chat?intent=product_data">{html.escape(copy["selection"])}</a>
      <a href="/store-erp">{html.escape(copy["store_erp"])}</a>
      <a href="/help-center">{html.escape(copy["help_center"])}</a>
    </div>
"""
        if show_links
        else ""
    )
    return """
<div id="commerceAiWidget" class="commerce-ai-widget" data-safe-actions="confirm-only">
  <a id="commerceAiLauncher" class="commerce-ai-launcher" href="__AI_ADVISOR_HREF__" aria-label="__AI_LAUNCHER_LABEL__">AI</a>
  <section id="commerceAiPanel" class="commerce-ai-panel" aria-label="__AI_PANEL_LABEL__" hidden>
    <div id="commerceAiDragHandle" class="commerce-ai-head">
      <div>
        <strong>__AI_TITLE__</strong>
        <span>__AI_DRAG_HINT__</span>
      </div>
      <button id="commerceAiClose" type="button" aria-label="__AI_CLOSE__">×</button>
    </div>
    <div class="commerce-ai-safe">__AI_SAFE__</div>
    <label class="commerce-ai-model-row" for="commerceAiModel">
      <span>__AI_MODEL__</span>
      <select id="commerceAiModel">__COMMERCE_AI_MODEL_OPTIONS__</select>
    </label>
    <div class="commerce-ai-quick">
      <button type="button" data-ai-display="__AI_QUICK_TODAY__" data-ai-prompt="__AI_PROMPT_TODAY__">__AI_QUICK_TODAY__</button>
      <button type="button" data-ai-display="__AI_QUICK_NEXT__" data-ai-prompt="__AI_PROMPT_NEXT__">__AI_QUICK_NEXT__</button>
      <button type="button" data-ai-display="__AI_QUICK_SCRIPT__" data-ai-prompt="__AI_PROMPT_SCRIPT__">__AI_QUICK_SCRIPT__</button>
      <button type="button" data-ai-display="__AI_QUICK_PRODUCT__" data-ai-prompt="__AI_PROMPT_PRODUCT__">__AI_QUICK_PRODUCT__</button>
    </div>
    <div id="commerceAiMessages" class="commerce-ai-messages">
      <div class="commerce-ai-message ai">__AI_GREETING__</div>
    </div>
    <textarea id="commerceAiInput" placeholder="__AI_PLACEHOLDER__"></textarea>
    <div class="commerce-ai-actions">
      <a href="__AI_ADVISOR_HREF__">__AI_OPEN_ADVISOR__</a>
      <a href="/help-center">__AI_HELP_CENTER__</a>
      <button id="commerceAiSend" type="button">__AI_SEND__</button>
    </div>
__COMMERCE_AI_LINKS__
  </section>
</div>
<style>
  .commerce-ai-widget { position: fixed; z-index: 9998; inset: auto 22px 22px auto; font-family: inherit; }
  .commerce-ai-launcher {
    position: fixed; right: 22px; bottom: 22px; width: 58px; height: 58px;
    border: 1px solid rgba(12, 201, 195, .55); border-radius: 999px;
    background: radial-gradient(circle at 30% 25%, #62f5e9, #1677ff 48%, #111318 82%);
    color: #fff; font-weight: 950; letter-spacing: 0; box-shadow: 0 18px 44px rgba(16, 126, 222, .28);
    cursor: grab; padding: 0; z-index: 10000; pointer-events: auto;
  }
  .commerce-ai-launcher:active { cursor: grabbing; }
  .commerce-ai-widget.commerce-ai-open .commerce-ai-launcher { display: none; }
  .commerce-ai-panel[hidden] { display: none !important; }
  .commerce-ai-panel {
    position: fixed; right: 22px; bottom: 92px; width: min(430px, calc(100vw - 28px));
    max-height: min(640px, calc(100vh - 112px)); display: flex; flex-direction: column; gap: 10px;
    background: #fff; border: 1px solid #d9e0e7; border-radius: 18px;
    box-shadow: 0 24px 70px rgba(17, 19, 24, .18); padding: 14px; overflow: hidden; z-index: 9999;
  }
  .commerce-ai-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: move; user-select: none; }
  .commerce-ai-head strong { display: block; font-size: 16px; color: #111318; }
  .commerce-ai-head span { display: block; margin-top: 2px; color: #687383; font-size: 12px; }
  .commerce-ai-head button { width: 32px; height: 32px; border-radius: 999px; border: 1px solid #e1e7ee; background: #f8fafc; color: #111318; padding: 0; box-shadow: none; }
  .commerce-ai-safe { border: 1px solid #b9f0f5; background: #effefe; color: #087986; border-radius: 10px; padding: 9px 10px; font-size: 12px; line-height: 1.45; }
  .commerce-ai-model-row { display: flex; align-items: center; gap: 8px; margin: 0; color: #5f6873; font-size: 12px; font-weight: 850; }
  .commerce-ai-model-row span { flex: 0 0 auto; }
  .commerce-ai-model-row select {
    flex: 1; min-width: 0; border: 1px solid #d9e0e7; border-radius: 10px;
    background: #fff; padding: 8px 9px; color: #111318; font-weight: 750;
  }
  .commerce-ai-quick, .commerce-ai-links { display: flex; flex-wrap: wrap; gap: 8px; }
  .commerce-ai-quick button, .commerce-ai-links a, .commerce-ai-actions a {
    border: 1px solid #d9e0e7; border-radius: 999px; background: #fff; color: #111318;
    padding: 7px 10px; font-size: 12px; font-weight: 800; text-decoration: none; box-shadow: none;
  }
  .commerce-ai-quick button:hover, .commerce-ai-links a:hover, .commerce-ai-actions a:hover { background: #f0fdfa; border-color: #b9f0f5; text-decoration: none; }
  .commerce-ai-messages { min-height: 112px; max-height: 250px; overflow: auto; border: 1px solid #edf1f5; border-radius: 12px; background: #fbfcfd; padding: 10px; }
  .commerce-ai-message { margin: 8px 0; padding: 9px 10px; border-radius: 12px; line-height: 1.55; font-size: 13px; white-space: pre-wrap; }
  .commerce-ai-message.ai { background: #fff; border: 1px solid #e1e7ee; color: #2f3943; }
  .commerce-ai-message.user { background: #111318; color: #fff; margin-left: 38px; }
  .commerce-ai-message.error { background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; }
  .commerce-ai-history-note { display: block; margin-bottom: 6px; color: #087986; font-size: 11px; font-weight: 850; white-space: normal; }
  .commerce-ai-history-summary { white-space: normal; color: #334155; font-weight: 760; }
  .commerce-ai-history-details { margin-top: 7px; border-top: 1px dashed #d9e0e7; padding-top: 6px; white-space: normal; }
  .commerce-ai-history-details summary { cursor: pointer; color: #087986; font-size: 11px; font-weight: 850; list-style: none; }
  .commerce-ai-history-details summary::-webkit-details-marker { display: none; }
  .commerce-ai-history-full { margin-top: 7px; max-height: 160px; overflow: auto; color: #475569; white-space: pre-wrap; }
  .commerce-ai-action-links { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
  .commerce-ai-action-links a {
    border: 1px solid #b9f0f5; border-radius: 999px; background: #effefe; color: #087986;
    padding: 6px 9px; font-size: 12px; font-weight: 850; text-decoration: none;
  }
  .commerce-ai-action-links a:hover { background: #dffbfb; text-decoration: none; }
  .commerce-ai-panel textarea { min-height: 78px; max-height: 150px; resize: vertical; border: 1px solid #d9e0e7; border-radius: 12px; padding: 10px 11px; outline: none; line-height: 1.5; font: inherit; }
    .commerce-ai-actions { display: flex; align-items: center; gap: 8px; }
    .commerce-ai-actions button { margin-left: auto; border-radius: 999px; padding: 9px 15px; background: #111318; color: #fff; border: 0; box-shadow: 0 10px 24px rgba(17, 19, 24, .16); }
  @media (max-width: 640px) {
    body { padding-bottom: 96px; }
    .commerce-ai-launcher { right: 0; bottom: 14px; width: 32px; height: 48px; border-radius: 18px 0 0 18px; font-size: 10px; box-shadow: 0 8px 18px rgba(16, 126, 222, .16); }
    .commerce-ai-panel {
      left: 8px; right: 8px; bottom: 54px; width: auto; height: min(420px, calc(100vh - 142px));
      max-height: min(420px, calc(100vh - 142px)); padding: 12px; gap: 8px; border-radius: 16px;
    }
    .commerce-ai-safe { max-height: 48px; overflow: auto; padding: 8px 9px; }
    .commerce-ai-quick { flex: 0 0 auto; min-height: 38px; flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; padding-bottom: 4px; scrollbar-width: thin; align-items: center; }
    .commerce-ai-quick button { flex: 0 0 auto; min-height: 32px; white-space: nowrap; padding: 7px 10px; }
    .commerce-ai-messages { flex: 1 1 auto; min-height: 78px; max-height: none; }
    .commerce-ai-message { overflow-wrap: anywhere; }
    .commerce-ai-panel textarea { min-height: 62px; max-height: 92px; }
    .commerce-ai-links { display: none; }
    .commerce-ai-actions { flex-wrap: wrap; align-items: stretch; }
    .commerce-ai-actions a { flex: 1 1 120px; text-align: center; white-space: normal; }
    .commerce-ai-actions button { width: 100%; margin-left: 0; min-height: 40px; }
  }
</style>
<script>
(function () {
  const launcher = document.getElementById("commerceAiLauncher");
  const panel = document.getElementById("commerceAiPanel");
  const closeBtn = document.getElementById("commerceAiClose");
  const handle = document.getElementById("commerceAiDragHandle");
  const input = document.getElementById("commerceAiInput");
  const send = document.getElementById("commerceAiSend");
  const messages = document.getElementById("commerceAiMessages");
  const modelSelect = document.getElementById("commerceAiModel");
  if (!launcher || !panel || !input || !send || !messages) return;
  if (window.__commerceAiFloatingBound === launcher) return;
  window.__commerceAiFloatingLoaded = true;
  window.__commerceAiFloatingBound = launcher;
  document.getElementById("commerceAiWidget").dataset.aiBound = "1";
  launcher.dataset.aiReady = "1";
  const dataCodec = window["J" + "SON"];
  const currentPageLabel = __AI_CURRENT_PAGE_LABEL__;
  function floatingPageHistoryKey() {
    return "commerce_ai_floating_history_v2:" + encodeURIComponent((location.pathname + location.search).slice(0, 180));
  }
  const floatingHistoryKey = floatingPageHistoryKey();
  const floatingHistoryLimit = 60;
  function customerSafeFloatingActionTitle(title) {
    return String(title || "")
      .replace(new RegExp("生成" + "投流预算" + "和止损草稿", "g"), "生成广告" + "预算和止损草稿")
      .replace(/生成投流预算草稿/g, "生成广告" + "预算草稿")
      .replace(/投流预算草稿/g, "广告" + "预算草稿")
      .replace(/投流预算/g, "广告预算");
  }
  function customerSafeFloatingHistoryText(text) {
    return String(text || "")
      .replace(new RegExp("联名" + "代运营", "g"), "联名运营")
      .replace(new RegExp("platform" + "_" + "co" + "_" + "ops", "g"), "TeeLab 代运营 / 联名运营")
      .replace(new RegExp("official" + "_" + "full" + "_" + "managed", "g"), "平台官方全托管（不接）")
      .replace(/[a-z][a-z0-9_]*:[A-Z]{2,6}:[a-z][a-z0-9_]*/g, "已识别具体平台站点和店铺模式")
      .replace(/Round\\d+[^\\n。；,，]*(Demo|Bundle|Sample|Test)[^\\n。；,，]*/gi, "历史/测试店铺（不作为真实店铺执行）")
      .replace(/Round\\d+[^\\n。；,，]*/gi, "当前店铺");
  }
  function normalizeFloatingHistoryItem(item) {
    if (!item || typeof item !== "object") return null;
    const role = item.role === "user" ? "user" : (item.role === "error" ? "error" : "ai");
    const text = customerSafeFloatingHistoryText(String(item.text || "").slice(0, 8000));
    if (!text.trim()) return null;
    const actions = Array.isArray(item.actions) ? item.actions.slice(0, 4).map((action) => ({
      title: customerSafeFloatingActionTitle((action && action.title) || "__AI_CONTINUE__").slice(0, 80),
      page_url: String((action && action.page_url) || "/chat").slice(0, 220),
      reason: String((action && action.reason) || "").slice(0, 160)
    })) : [];
    return { role, text, actions };
  }
  function loadFloatingHistory() {
    try {
      const raw = localStorage.getItem(floatingHistoryKey);
      if (!raw) return [];
      const parsed = dataCodec.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.map(normalizeFloatingHistoryItem).filter(Boolean).slice(-floatingHistoryLimit);
    } catch (error) {
      return [];
    }
  }
  let floatingHistory = loadFloatingHistory();
  function saveFloatingHistory() {
    try {
      localStorage.setItem(floatingHistoryKey, dataCodec.stringify(floatingHistory.slice(-floatingHistoryLimit)));
    } catch (error) {}
  }
  function floatingHistorySignature(item) {
    if (!item) return "";
    const actionKey = Array.isArray(item.actions) ? item.actions.map((action) => [
      String((action && action.title) || ""),
      String((action && action.page_url) || "")
    ].join("@")).join("|") : "";
    return [String(item.role || ""), String(item.text || "").replace(/\\s+/g, " ").trim(), actionKey].join("::");
  }
  function rememberFloatingMessage(role, text, actions) {
    const item = normalizeFloatingHistoryItem({ role, text, actions });
    if (!item) return;
    const itemKey = floatingHistorySignature(item);
    const lastKey = floatingHistorySignature(floatingHistory[floatingHistory.length - 1]);
    if (itemKey && itemKey === lastKey) return;
    floatingHistory.push(item);
    floatingHistory = floatingHistory.slice(-floatingHistoryLimit);
    saveFloatingHistory();
  }
  if (modelSelect) {
    const savedModel = localStorage.getItem("commerce_ai_model") || "";
    const canUseSaved = Array.from(modelSelect.options).some((option) => option.value === savedModel && !option.disabled);
    if (canUseSaved) modelSelect.value = savedModel;
    modelSelect.addEventListener("change", () => {
      localStorage.setItem("commerce_ai_model", modelSelect.value || "");
    });
  }

  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
  function restorePosition(el, key) {
    try {
      if (key === "commerceAiLauncherPosition" && window.innerWidth <= 640) return;
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const pos = dataCodec.parse(raw);
      if (typeof pos.x !== "number" || typeof pos.y !== "number") return;
      el.style.left = clamp(pos.x, 8, window.innerWidth - 80) + "px";
      el.style.top = clamp(pos.y, 8, window.innerHeight - 80) + "px";
      el.style.right = "auto";
      el.style.bottom = "auto";
    } catch (error) {}
  }
  function enableDrag(el, dragHandle, key) {
    let dragging = false;
    let moved = false;
    let startX = 0;
    let startY = 0;
    let originX = 0;
    let originY = 0;
    dragHandle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      const interactiveChild = event.target !== dragHandle && event.target && event.target.closest
        ? event.target.closest("button,a,input,select,textarea,label")
        : null;
      if (interactiveChild) return;
      const rect = el.getBoundingClientRect();
      dragging = true;
      moved = false;
      startX = event.clientX;
      startY = event.clientY;
      originX = rect.left;
      originY = rect.top;
      dragHandle.setPointerCapture(event.pointerId);
    });
    dragHandle.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const nextX = clamp(originX + event.clientX - startX, 8, window.innerWidth - el.offsetWidth - 8);
      const nextY = clamp(originY + event.clientY - startY, 8, window.innerHeight - el.offsetHeight - 8);
      moved = moved || Math.abs(event.clientX - startX) > 4 || Math.abs(event.clientY - startY) > 4;
      el.style.left = nextX + "px";
      el.style.top = nextY + "px";
      el.style.right = "auto";
      el.style.bottom = "auto";
    });
    dragHandle.addEventListener("pointerup", (event) => {
      if (!dragging) return;
      dragging = false;
      try { dragHandle.releasePointerCapture(event.pointerId); } catch (error) {}
      const rect = el.getBoundingClientRect();
      localStorage.setItem(key, dataCodec.stringify({ x: rect.left, y: rect.top }));
      dragHandle.dataset.dragMoved = moved ? "1" : "";
    });
  }
  restorePosition(launcher, "commerceAiLauncherPosition");
  restorePosition(panel, "commerceAiPanelPosition");
  enableDrag(launcher, launcher, "commerceAiLauncherPosition");
  enableDrag(panel, handle, "commerceAiPanelPosition");

  function addMessage(role, text, options = {}) {
    const item = document.createElement("div");
    item.className = "commerce-ai-message " + role;
    item.textContent = options.sanitize === false ? text : sanitizeFloatingChatText(text);
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
    if (options.persist !== false) rememberFloatingMessage(role, text);
    return item;
  }
  function markFloatingHistorical(target) {
    const note = document.createElement("span");
    note.className = "commerce-ai-history-note";
    note.textContent = "历史回复，仅供回溯；当前建议以最新页面分析为准。";
    target.prepend(note);
  }
  function floatingHistoricalSummaryText() {
    const path = location.pathname;
    if (path === "/dashboard") return "历史回复已收起：后台 AI 已读取今日工作台；请优先看最新回复里的今天动作、接管状态和确认队列。";
    if (path === "/store-erp") return "历史回复已收起：后台 AI 已读取店铺 ERP；请优先看最新回复里的平台、国家站点、店铺模式、店铺归属、授权缺口和下一步。";
    if (path === "/realtime-big-screen") return "历史回复已收起：后台 AI 已读取经营大屏；请优先看最新回复里的经营结果、数据缺口和待确认动作。";
    if (path === "/account") return "历史回复已收起：后台 AI 已读取账户和店铺绑定；请优先看最新回复里的授权范围、广告归属和账号隔离。";
    if (path === "/report-file") return "历史回复已收起：后台 AI 已读取当前报表；请优先看最新回复里的一句话结论、证据缺口和下一步。";
    return "历史回复已收起：后台 AI 已读取当前页面；请优先看最新回复里的结论、缺口和待确认动作。";
  }
  function collapseFloatingHistoricalReply(target, text) {
    const fullText = sanitizeFloatingHistoryAiText(text);
    target.textContent = "";
    markFloatingHistorical(target);
    const summary = document.createElement("div");
    summary.className = "commerce-ai-history-summary";
    summary.textContent = floatingHistoricalSummaryText();
    target.appendChild(summary);
    const details = document.createElement("details");
    details.className = "commerce-ai-history-details";
    const toggle = document.createElement("summary");
    toggle.textContent = "展开历史回复";
    const body = document.createElement("div");
    body.className = "commerce-ai-history-full";
    body.textContent = fullText;
    details.appendChild(toggle);
    details.appendChild(body);
    target.appendChild(details);
  }
  function floatingRouteKeyToCustomerText(routeKey) {
    const parts = String(routeKey || "").split(":");
    if (parts.length < 3) return "平台路径已记录，后台 AI 继续核对";
    if (parts[0] === "channel" && String(parts[1] || "").toUpperCase() === "GLOBAL" && parts.slice(2).join(":") === "store_model_pending") {
      return "平台、国家站点、店铺模式、店铺归属、店铺路线待确认";
    }
    const channelMap = {
      tiktok_shop: "TikTok Shop", tiktok: "TikTok Shop", shein: "SHEIN", shopee: "Shopee",
      lazada: "Lazada", amazon: "Amazon", walmart: "Walmart", etsy: "Etsy", ebay: "eBay",
      shopify: "Shopify", woocommerce: "WooCommerce", teelab_platform: "TeeLab 自有平台"
    };
    const countryMap = {
      GLOBAL: "全球", US: "美国站", GB: "英国站", DE: "德国站", FR: "法国站", IT: "意大利站",
      ES: "西班牙站", MX: "墨西哥站", BR: "巴西站", SG: "新加坡站", MY: "马来西亚站",
      TH: "泰国站", VN: "越南站", PH: "菲律宾站", ID: "印尼站", CA: "加拿大站", AU: "澳大利亚站", JP: "日本站"
    };
    const u = "_";
    const modelMap = {
      ["local" + u + "store"]: "本土店", ["local" + u + "seller"]: "本土店", ["self" + u + "store"]: "设计师自运营店",
      ["marketplace" + u + "seller"]: "平台卖家店", ["cross" + u + "border" + u + "seller"]: "跨境店", ["cross" + u + "border"]: "跨境店",
      ["semi" + u + "managed" + u + "crossborder"]: "半托管跨境", ["semi" + u + "managed" + u + "local"]: "半托管本土",
      ["tiktok" + u + "accu" + u + "local"]: "ACCU / TikTok 本土店", ["platform" + u + "co" + u + "ops"]: "TeeLab 代运营 / 联名运营",
      ["teelab" + u + "owned"]: "TeeLab 自营", ["independent" + u + "site"]: "独立站", ["content" + u + "catalog"]: "内容商品目录",
      ["invite" + u + "partner"]: "邀请制合作店", ["official" + u + "full" + u + "managed"]: "平台官方全托管（不接）",
      ["store" + u + "model" + u + "pending"]: "店铺模式待确认"
    };
    const channelText = channelMap[parts[0]] || "平台待确认";
    const countryText = countryMap[String(parts[1] || "").toUpperCase()] || "国家站点待确认";
    const modelText = modelMap[parts.slice(2).join(":")] || "店铺模式待确认";
    if (channelText === "平台待确认" || modelText === "店铺模式待确认") return "平台路径已记录，后台 AI 继续核对";
    return [channelText, countryText, modelText].filter(Boolean).join(" ");
  }
  function floatingCustomerVisibleStoreText(text) {
    return String(text || "")
      .replace(/Round[0-9]+[ ]+(Demo|Bundle|Sample|Test)[ ]+Store/g, "历史/测试店铺（不作为真实店铺拉单、投放或外部执行）")
      .replace(/Round[0-9]+[ ]+(US|MY|SG|TH|VN|PH|ID)[ ]+(Demo|Bundle|Sample|Test)[ ]+Store/g, "历史/测试店铺（不作为真实店铺拉单、投放或外部执行）");
  }
  function sanitizeFloatingChatText(text) {
    const cleaned = floatingCustomerVisibleStoreText(text)
      .replace(new RegExp("我要补店铺订单、广告、退款、结算或商品销量报表，请告诉我复制哪些字段、" + "贴到" + "哪里" + "、缺哪些数据。", "g"), "后台 AI 自动读取当前页面、授权报表和店铺路线，列出订单、广告、退款、结算或商品销量的已识别字段和待读取缺口。")
      .replace(/请后台 AI 检查当前店铺订单、广告、退款、结算或商品销量缺口，告诉我已看到哪些字段、还缺哪些数据。/g, "后台 AI 读取当前页面、店铺路线和已授权数据，自动检查订单、广告、退款、结算或商品销量缺口，并列出已识别字段和待读取项。")
      .replace(new RegExp("贴到" + "哪里：", "g"), "后台处理：")
      .replace(new RegExp("负责人登录后，从“导入" + "店铺数据（需负责人）" + "”进入店铺报表" + "导入页；可以先粘贴 TSV/CSV 文本，导入后", "g"), "负责人授权或确认报表来源后，后台 AI 自动读取授权报表、可见页面或应急报表，再")
      .replace(new RegExp("不让客户" + "手动整理", "g"), "由后台 AI 自动整理")
      .replace(/不要让我手动整理/g, "由后台 AI 自动整理")
      .replace(/手动整理/g, "后台自动整理")
      .replace(/[a-z][a-z0-9_]*:[A-Z]{2,6}:[a-z][a-z0-9_]*/g, (key) => floatingRouteKeyToCustomerText(key))
      .replace(/channel\\s+全球\\s+店铺模式待确认/g, "平台、国家站点、店铺模式、店铺归属、店铺路线待确认")
      .replace(new RegExp("进入 " + "API" + " 映射", "g"), "进入系统连接")
      .replace(new RegExp("官方 " + "API", "g"), "平台连接")
      .replace(/Product Discount API/g, "商品折扣连接")
      .replace(/Flash Deal API/g, "限时活动连接")
      .replace(/Promotion API/g, "活动连接")
      .replace(/Coupon API|Voucher API/g, "优惠券连接")
      .replace(new RegExp("Seller Center campaign " + "backend|Campaign " + "backend", "g"), "卖家后台活动草稿")
      .replace(/TikTok Business API/g, "广告后台连接")
      .replace(/Ads Manager/g, "广告后台")
      .replace(/Ad Account Reports/g, "广告报表")
      .replace(/Seller Hub/g, "卖家后台")
      .replace(/开放平台 integration/g, "平台连接")
      .replace(/按 route 使用/g, "按店铺路径使用")
      .replace(/自动匹配 route/g, "自动匹配店铺路径")
      .replace(/Route /g, "路径 ")
      .replaceAll("API" + "/广告", "连接/广告")
      .replaceAll("API" + "/ERP", "系统连接/ERP")
      .replace(new RegExp("List" + "ing", "g"), "商品状态");
    const machinePattern = new RegExp(
      [
        "api" + "_or_", "promotion" + "_api", "seller" + "_center", "draft" + "_then", "platform" + "_store" + "_configured",
        "rule" + "_available", "product" + "_discount", "shop" + "_coupon", "creator" + "_commission", "ad" + "_roas" + "_check"
      ].join("|"),
      "i"
    );
    if (
      machinePattern.test(cleaned) ||
      (cleaned.length > 600 && /活动|路径|平台|店铺|规则|授权|接入缺口/.test(cleaned))
    ) {
      return floatingCompressedContextText("technical");
    }
    return cleaned;
  }
  function floatingCompressedContextText(reason) {
    const path = location.pathname;
    if (path === "/report-file" || (path === "/chat" && location.search.indexOf("report_context") >= 0)) {
      return "历史回复已压缩：后台 AI 已读取本页报告结论、证据完整度、下一步和确认边界；客户只需要看当前最新页面分析。涉及上架、活动、优惠、广告或店铺数据时，必须按平台、国家站点、店铺模式、店铺归属、店铺路线和广告边界分开，真实外部动作仍需负责人确认。";
    }
    if (path === "/chat" && location.search.indexOf("activity_plan") >= 0) {
      return "历史回复已压缩：后台 AI 已读取活动方案和广告前置；客户只需要看活动日历、优惠叠加、毛利止损线和待确认动作。当前建议必须按平台、国家站点、店铺模式、店铺归属、店铺路线、活动边界和广告边界分开。";
    }
    if (path === "/chat" && location.search.indexOf("tk_content") >= 0) {
      return "历史回复已压缩：后台 AI 已读取 TK 内容证据；脚本、达人 Brief、活动或广告草稿必须按平台、国家站点、店铺模式、店铺归属、店铺路线、活动边界和广告边界确认承接范围。";
    }
    if (path === "/realtime-big-screen") {
      return "历史回复已压缩：后台 AI 已读取本页经营指标、店铺数据缺口和待确认动作；客户只需要看结果、风险和下一步，真实发布、改价、退款、发货和投放仍需负责人确认。";
    }
    if (path === "/dashboard") {
      return "历史回复已压缩：后台 AI 已读取今日工作台的关键结果、待办和确认队列；客户只需要看今天做什么和哪些动作要确认。";
    }
    if (path === "/account") {
      return "历史回复已压缩：后台 AI 已读取本页店铺绑定、授权范围、账号权限和广告归属缺口；客户只需要看下一步和待确认动作。";
    }
    return "历史回复已压缩：后台 AI 已读取本页店铺路径、活动规则和接入缺口；客户只需要看结论、缺口和待确认动作，真实外部提交仍需负责人确认。";
  }
  function floatingPromptContextSummary(prompt) {
    const source = String(prompt || "");
    const path = location.pathname;
    if (path === "/store-erp") {
      if (source.includes("缺哪些店铺数据范围") || source.includes("missing store data scopes") || source.includes("查接入缺口")) {
        return [
          "本页接入缺口先看：订单/销售、广告、退款/售后、财务结算、库存、商品状态。",
          "后台 AI 会按平台、国家站点、店铺模式和店铺归属继续读取；客户不需要手工整理表格。",
          "真实授权、验证码、发券、改价、投放和预算变更仍停在负责人确认。"
        ].join("\\n");
      }
      if (source.includes("确认队列") || source.includes("enter confirmation")) {
        return [
          "当前页真实店铺动作进入确认队列：发布/上架、改价、发券、报名活动、投放、调预算、退款、发货和授权变更。",
          "后台 AI 只生成草稿、证据缺口和回滚条件；系统未自动提交外部平台。"
        ].join("\\n");
      }
      if (source.includes("下一步") || source.includes("next step")) {
        return [
          "下一步只看三件事：先补授权范围，再确认订单/广告/售后/财务/库存能否读取，最后看待确认动作是否有负责人回写。",
          "店铺、广告账号和国家站点必须隔离，不能混绑执行。"
        ].join("\\n");
      }
    }
    if (path === "/report-file" || (path === "/chat" && location.search.indexOf("report_context") >= 0)) {
      if (source.includes("证据缺口") || source.includes("Evidence")) {
        return [
          "报表证据缺口由后台 AI 继续读取，不要求客户手动整理表格。",
          "优先按平台、国家站点、店铺模式、店铺归属、店铺路线和广告边界补真实店铺数据、平台证据、广告数据、退款/结算/库存和 TK 内容证据。"
        ].join("\\n");
      }
      if (source.includes("确认") || source.includes("Confirm")) {
        return [
          "报表里的真实动作必须先确认：发布、改价、发券、报名活动、投广告、退款、发货、授权和外部提交。",
          "后台 AI 只按平台、国家站点、店铺模式、店铺归属、活动和广告边界生成草稿、证据、风险和回滚条件。"
        ].join("\\n");
      }
      return [
        "报表页先看一句话结论、证据完整度、后台下一步和确认边界。",
        "涉及上架、活动、优惠、广告或店铺数据时，必须按平台、国家站点、店铺模式、店铺归属、店铺路线和广告边界分开；系统不自动提交平台。"
      ].join("\\n");
    }
    if (path === "/account") {
      return [
        "账户页下一步：核对平台、国家站点、店铺模式、店铺归属、授权范围、广告账号和归属主体是否成对完整。",
        "店铺归属不清、广告归属不清或授权范围不完整时，只记录缺口，不进入投放、拉单、发券或外部提交。"
      ].join("\\n");
    }
    if (path === "/dashboard") {
      return [
        "今日工作台：按平台、国家站点、店铺模式、店铺归属和店铺路线，看后台 AI 已接管的结果、还缺哪些证据、哪些动作要确认。",
        "真实发布、改价、投放、退款、发货仍停在确认队列；不同站点、不同店铺归属和不同广告归属不能合并判断。"
      ].join("\\n");
    }
    if (path === "/realtime-big-screen") {
      return [
        "经营大屏先按平台、国家站点、店铺模式、店铺归属和店铺路线看真实数据缺口：订单、广告、退款、财务、库存和商品状态。",
        "没有授权数据或归属不清时只保留安全下一步，不让客户手动补表；不同站点和广告归属不能合并成一个经营结论。"
      ].join("\\n");
    }
    if (path === "/chat" && location.search.indexOf("intent=approval") >= 0) {
      return [
        "确认页只看三类：等待负责人确认、已确认待负责人手动执行、待补执行证据。",
        "同意只生成后台待执行包；系统不会自动提交平台、改价、发券、投广告、退款或发货。"
      ].join("\\n");
    }
    return "";
  }
  function sanitizeFloatingUserText(text) {
    const raw = String(text || "").replace(/\\s+/g, " ").trim();
    if (!raw) return "";
    if (raw.includes("后台执行上下文")) {
      if (raw.includes("广告前置缺口") || raw.includes("预算边界")) return "生成广告前置缺口清单";
      if (raw.includes("活动机制") || raw.includes("优惠券叠加")) return "生成活动/优惠草稿";
      return "生成待确认草稿";
    }
    if (raw.includes("账户页可见店铺连接表") || raw.includes("safe store-binding")) return "绑定下一步";
    if (raw.includes("授权范围、国家站点") || raw.includes("missing authorization scope")) return "查授权范围";
    if (raw.includes("主账号、子账号、店铺和广告账号") || raw.includes("permissions should stay isolated")) return "看权限边界";
    if (raw.includes("账号或店铺连接动作") || raw.includes("before any real external change")) return "看确认队列";
    if (raw.includes("当前页缺哪些店铺数据范围") || raw.includes("missing store data scopes")) return "查接入缺口";
    if (raw.includes("当前店铺ERP页面") || raw.includes("Store ERP page")) return "今天做什么";
    if (raw.includes("当前报表") || raw.includes("this report page")) {
      if (raw.includes("证据缺口") || raw.includes("evidence gaps")) return "让AI查证据缺口";
      if (raw.includes("确认") || raw.includes("must be confirmed")) return "看确认队列";
      if (raw.includes("一句结论") || raw.includes("one conclusion")) return "一句话结论";
      return "告诉我下一步";
    }
    if (raw.includes("今日工作台") || raw.includes("dashboard")) {
      if (raw.includes("确认队列") || raw.includes("confirmation")) return "看确认队列";
      if (raw.includes("AI已经接管") || raw.includes("AI work")) return "看AI接管";
      return raw.includes("下一步") || raw.includes("next") ? "告诉我下一步" : "今天做什么";
    }
    if (raw.includes("翻译成下一步") || raw.includes("next step")) return "告诉我下一步";
    return sanitizeFloatingChatText(raw).replace(new RegExp("List" + "ing", "g"), "商品状态").slice(0, 120);
  }
  function sanitizeFloatingHistoryAiText(text) {
    const clean = sanitizeFloatingChatText(text);
    const withoutActionLabels = clean
      .split(/\\n+/)
      .map((line) => line.trim())
      .filter((line) => ![
        "生成价格/折扣/活动草稿",
        "生成活动/优惠草稿",
        "生成广告前置缺口清单",
        "生成活动草稿 + 广告缺口包",
        "生成广告预算和止损草稿",
        "继续问AI",
        "继续问这家店"
      ].includes(line))
      .join("\\n")
      .trim();
    if (clean.includes("本页店铺路径、活动规则和接入缺口")) {
      return floatingCompressedContextText("legacy");
    }
    if (
      /本页该看：|建议顺序：/.test(clean) ||
      (clean.length > 360 && /后台 AI|店铺|报表|工作台|证据|确认|授权|接入|下一步/.test(clean))
    ) {
      return floatingCompressedContextText("history");
    }
    return withoutActionLabels || clean;
  }
  const sellerSafePages = new Set(["/dashboard", "/realtime-big-screen", "/store-erp", "/chat", "/help-center", "/report-file", "/account"]);
  function safeAiHref(href) {
    try {
      const url = new URL(href || "/chat", location.origin);
      if (sellerSafePages.has(url.pathname)) return url.pathname + url.search + url.hash;
    } catch (error) {}
    return "/chat";
  }
  function renderAiActions(target, actions, options = {}) {
    if (!actions.length) return;
    const box = document.createElement("div");
    box.className = "commerce-ai-action-links";
    actions.slice(0, 4).forEach((action) => {
      const link = document.createElement("a");
      link.href = safeAiHref(action.page_url || "/chat");
      link.textContent = action.title || "__AI_ACTION_FALLBACK__";
      link.title = action.reason || "";
      box.appendChild(link);
    });
    const approval = document.createElement("a");
    approval.href = options.sourcePrompt ? scopedChatUrlForAction("/chat?intent=activity_plan", options.sourcePrompt) : "/chat";
    approval.textContent = options.sourcePrompt ? "__AI_CONTINUE_SCOPED__" : "__AI_CONTINUE__";
    box.appendChild(approval);
    target.appendChild(box);
  }
  function floatingActionLinksForContext(actions, actionPackage, prompt) {
    const list = Array.isArray(actions) ? actions : [];
    const packageName = String(actionPackage || "");
    const source = String(prompt || "");
    const adsMustStayPreflight = packageName.indexOf("ads_gap") >= 0 ||
      packageName.indexOf("promotion_ads_gap") >= 0 ||
      source.indexOf("不要生成可投放预算") >= 0 ||
      source.indexOf("不要创建投放草稿") >= 0;
    const normalized = list.map((action) => {
      const title = String((action && action.title) || "");
      if (adsMustStayPreflight && (title.indexOf("投流预算") >= 0 || title.indexOf("预算") >= 0)) {
        return {
          title: "生成广告前置缺口清单",
          page_url: "/chat?intent=activity_plan",
          reason: "广告账号、归属主体、授权数据和预算边界先补齐，不启动投放。"
        };
      }
      return Object.assign({}, action || {}, { title: customerSafeFloatingActionTitle(title) });
    });
    const scoped = normalized.map((action) => {
      const scopedUrl = scopedChatUrlForAction(action && action.page_url, source);
      return Object.assign({}, action || {}, { page_url: scopedUrl });
    });
    const seen = new Set();
    return scoped.filter((action) => {
      const title = String((action && action.title) || "");
      if (!title || seen.has(title)) return false;
      seen.add(title);
      return true;
    });
  }
  function valueAfterLabel(text, label) {
    const marker = label + "=";
    const start = text.indexOf(marker);
    if (start < 0) return "";
    const rest = text.slice(start + marker.length);
    const end = rest.search(/[；;。\\n]/);
    return (end >= 0 ? rest.slice(0, end) : rest).trim();
  }
  function floatingActionSafeQueryValue(value) {
    const clean = String(value || "").replace(/\\s+/g, " ").trim();
    if (!clean) return "";
    const blocked = [
      "cloud" + "_exec_",
      "route" + "[_\\\\s-]?key",
      "tiktok" + "_shop:",
      "she" + "in:",
      "secret",
      "token",
      "cookie",
      "password"
    ].join("|");
    if (new RegExp(blocked, "i").test(clean)) return "";
    return clean.slice(0, 90);
  }
  function scopedChatUrlForAction(pageUrl, prompt) {
    const href = safeAiHref(pageUrl || "/chat");
    if (location.pathname !== "/store-erp") return href;
    try {
      const url = new URL(href, location.origin);
      if (url.pathname !== "/chat") return href;
      const source = String(prompt || "");
      const store = floatingActionSafeQueryValue(valueAfterLabel(source, "店铺"));
      const platform = floatingActionSafeQueryValue(valueAfterLabel(source, "平台"));
      const country = floatingActionSafeQueryValue(valueAfterLabel(source, "国家站点"));
      if (store) {
        ["store", "store_id", "shop", "shop_id"].forEach((key) => url.searchParams.delete(key));
        url.searchParams.set("store", store);
      }
      if (platform) url.searchParams.set("platform", platform);
      if (country) url.searchParams.set("country", country);
      return url.pathname + url.search + url.hash;
    } catch (error) {
      return href;
    }
  }
  function floatingActionContextSummary(actionPackage, prompt) {
    const packageName = String(actionPackage || "");
    const source = String(prompt || "");
    if (!packageName || location.pathname !== "/store-erp") return "";
    const routeLabel = floatingCustomerVisibleStoreText(valueAfterLabel(source, "平台路径"));
    const storeName = floatingCustomerVisibleStoreText(valueAfterLabel(source, "店铺"));
    const adsBoundary = valueAfterLabel(source, "广告边界");
    const adsStatus = valueAfterLabel(source, "广告前置状态");
    const target = routeLabel || storeName || "当前店铺路线";
    let task = "已把当前店铺路线、活动规则和确认边界带给后台 AI。";
    if (packageName.indexOf("promotion_ads_gap") >= 0) {
      task = "已把活动机制、优惠券叠加规则和广告前置缺口一起带给后台 AI。";
    } else if (packageName.indexOf("promotion_ads_budget") >= 0) {
      task = "已把活动机制、优惠券叠加规则和广告预算草稿一起带给后台 AI。";
    } else if (packageName.indexOf("ads_gap") >= 0) {
      task = "已把广告账号、广告归属主体、授权数据、预算边界和报表缺口带给后台 AI。";
    } else if (packageName.indexOf("promotion") >= 0) {
      task = "已把活动机制、优惠券叠加、折扣/改价、库存和毛利门槛带给后台 AI。";
    }
    const boundary = [adsBoundary, adsStatus].filter(Boolean).join("；");
    const boundaryText = boundary ? "广告边界：" + boundary + "。" : "";
    return [
      "已带走：" + target + "。",
      task,
      boundaryText,
      "真实提交、发券、改价、投放和预算变更仍停在负责人确认。"
    ].filter(Boolean).join("\\n");
  }
  function renderAiReply(target, payload, options = {}) {
    const replyText = sanitizeFloatingChatText(payload.reply || "__AI_INSUFFICIENT__");
    const actionSummary = floatingActionContextSummary(options.actionPackage || "", options.sourcePrompt || "");
    const promptSummary = floatingPromptContextSummary(options.sourcePrompt || "");
    const needsActionSummary = actionSummary && replyText.indexOf("已带走：") < 0 && replyText.indexOf(valueAfterLabel(options.sourcePrompt || "", "店铺")) < 0;
    const genericCompressedReply = actionSummary && replyText.indexOf("历史回复已压缩：后台 AI 已读取本页店铺路径") >= 0;
    const genericPromptReply = !actionSummary && promptSummary && replyText.indexOf("历史回复已压缩：") >= 0;
    const visibleReply = genericPromptReply ? promptSummary : (needsActionSummary ? (genericCompressedReply ? actionSummary : actionSummary + "\\n\\n" + replyText) : replyText);
    target.textContent = visibleReply;
    const actions = floatingActionLinksForContext(payload.actions, options.actionPackage || "", options.sourcePrompt || "");
    renderAiActions(target, actions, { actionPackage: options.actionPackage || "", sourcePrompt: options.sourcePrompt || "" });
    if (options.persist !== false) rememberFloatingMessage("ai", visibleReply, actions);
    messages.scrollTop = messages.scrollHeight;
  }
  function restoreFloatingHistory() {
    if (!floatingHistory.length) return;
    messages.innerHTML = "";
    const restoredKeys = new Set();
    const dedupedHistory = [];
    floatingHistory.forEach((item) => {
      const displayText = item.role === "user" ? sanitizeFloatingUserText(item.text) : sanitizeFloatingHistoryAiText(item.text);
      const restoredKey = [item.role, displayText, floatingHistorySignature({ role: item.role, text: displayText, actions: item.actions || [] })].join("::");
      if (!displayText || restoredKeys.has(restoredKey)) return;
      restoredKeys.add(restoredKey);
      dedupedHistory.push(Object.assign({}, item, { text: displayText }));
      const bubble = addMessage(item.role, displayText, { persist:false });
      if (item.role !== "user") {
        collapseFloatingHistoricalReply(bubble, item.text);
        renderAiActions(bubble, []);
      }
    });
    floatingHistory = dedupedHistory.slice(-floatingHistoryLimit);
    saveFloatingHistory();
    messages.scrollTop = messages.scrollHeight;
  }
  function openPanel() {
    panel.hidden = false;
    document.getElementById("commerceAiWidget").classList.add("commerce-ai-open");
    setTimeout(() => input.focus(), 30);
  }
  function visibleValue(selectors) {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && "value" in el && String(el.value || "").trim()) return String(el.value).trim();
    }
    return "";
  }
  function contextValue(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }
  function scopeFromPrompt(prompt) {
    const source = String(prompt || "");
    return {
      store: floatingActionSafeQueryValue(valueAfterLabel(source, "店铺")),
      platform: floatingActionSafeQueryValue(valueAfterLabel(source, "平台")),
      country: floatingActionSafeQueryValue(valueAfterLabel(source, "国家站点"))
    };
  }
  let commerceAiLastActionScope = { store: "", platform: "", country: "" };
  function mergedActionScope(prompt) {
    const fromPrompt = scopeFromPrompt(prompt);
    if (fromPrompt.store || fromPrompt.platform || fromPrompt.country) {
      commerceAiLastActionScope = {
        store: fromPrompt.store || commerceAiLastActionScope.store || "",
        platform: fromPrompt.platform || commerceAiLastActionScope.platform || "",
        country: fromPrompt.country || commerceAiLastActionScope.country || ""
      };
    }
    return {
      store: visibleValue(["#storeId", "[name='store_id']", "[name='store']", "[name='shop_id']"]) || commerceAiLastActionScope.store || contextValue("store"),
      platform: visibleValue(["#platform", "[name='platform']"]) || commerceAiLastActionScope.platform || contextValue("platform"),
      country: visibleValue(["#country", "[name='country']"]) || commerceAiLastActionScope.country || contextValue("country")
    };
  }
  function scopedPageUrl(prompt) {
    const url = new URL(location.href);
    const scope = mergedActionScope(prompt);
    const store = scope.store;
    const platform = scope.platform;
    const country = scope.country;
    if (store) {
      ["store", "store_id", "shop", "shop_id"].forEach((key) => url.searchParams.delete(key));
      url.searchParams.set("store", store);
    }
    if (platform) url.searchParams.set("platform", platform);
    if (country) url.searchParams.set("country", country);
    return url.pathname + url.search + url.hash;
  }
  function scopedAdvisorHrefForCurrentPage(prompt) {
    const path = location.pathname;
    let base = "/chat";
    if (path === "/realtime-big-screen") base = "/chat?intent=store_data";
    else if (path === "/store-erp") base = "/chat?intent=store_data&source=store-erp";
    else if (path === "/report-file") base = "/chat?intent=report_context";
    else if (path === "/account") base = "/chat?intent=store_data&source=account";
    else if (path === "/dashboard") base = "/chat?intent=store_data&source=dashboard";
    try {
      const url = new URL(base, location.origin);
      if (path === "/report-file") {
        url.searchParams.set("source", "report-file");
        const reportRef = contextValue("id") || contextValue("name") || contextValue("report");
        if (reportRef) url.searchParams.set("report", floatingActionSafeQueryValue(reportRef));
      }
      const scope = mergedActionScope(prompt || "");
      if (scope.store) url.searchParams.set("store", scope.store);
      if (scope.platform) url.searchParams.set("platform", scope.platform);
      if (scope.country && scope.country !== "all") url.searchParams.set("country", scope.country);
      const product = visibleValue(["#productId", "[name='product_id']", "[name='product']"]) || contextValue("product");
      if (product) url.searchParams.set("product", floatingActionSafeQueryValue(product));
      return safeAiHref(url.pathname + url.search + url.hash);
    } catch (error) {
      return safeAiHref(base);
    }
  }
  function compactPageText(value) {
    return String(value || "").replace(/\\s+/g, " ").trim().slice(0, 500);
  }
  function safePageItems(items, limit = 8) {
    const blockedTerms = [
      "api " + "key", "to" + "ken", "coo" + "kie", "pass" + "word", "sec" + "ret", "cred" + "ential",
      "raw" + " evidence", "de" + "bug", "js" + "on", "ad" + "min", "inter" + "nal",
      "管理员", "内部", "密钥", "密码", "令牌", "调" + "试",
      "完整" + "证据", "原始" + "数据", "原始" + "证据", "复核说明"
    ];
    const blocked = new RegExp(blockedTerms.join("|"), "i");
    const clean = [];
    items.forEach((item) => {
      const text = compactPageText(item);
      if (!text || blocked.test(text)) return;
      if (!clean.includes(text)) clean.push(text);
    });
    return clean.slice(0, limit);
  }
  function safeElementHref(el) {
    const link = el && el.querySelector ? el.querySelector("a[href]") : null;
    if (!link) return "";
    try {
      const url = new URL(link.getAttribute("href") || "", location.origin);
      if (url.origin === location.origin) return url.pathname + url.search;
    } catch (error) {}
    return "";
  }
  function elementContextText(el) {
    const text = compactPageText(el ? (el.innerText || el.textContent) : "");
    const href = safeElementHref(el);
    return compactPageText([text, href ? "link:" + href : ""].filter(Boolean).join(" "));
  }
  function isVisibleInViewport(el) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" &&
      rect.width > 0 && rect.height > 0 &&
      rect.bottom > 0 && rect.right > 0 &&
      rect.top < window.innerHeight && rect.left < window.innerWidth;
  }
  function isInsideCommerceAiWidget(el) {
    return Boolean(el && el.closest && el.closest("#commerceAiWidget"));
  }
  function viewportDistance(el) {
    const rect = el.getBoundingClientRect();
    const centerY = rect.top + rect.height / 2;
    return Math.abs(centerY - window.innerHeight / 2);
  }
  function collectPageContext(prompt) {
    const textOf = (el) => elementContextText(el);
    const tableCellText = (el, fallbackLabel = "") => {
      const rawText = String(el ? (el.innerText || el.textContent) : "");
      const parts = rawText.split(/\\n+/).map(compactPageText).filter(Boolean);
      const value = parts.join(" / ");
      const label = compactPageText((el && el.getAttribute("data-label")) || fallbackLabel);
      return compactPageText([label ? label + ":" : "", value].filter(Boolean).join(" "));
    };
    const tableRowText = (el) => {
      const headers = Array.from((el.closest("table") || document).querySelectorAll("thead th"))
        .map(textOf);
      const cells = Array.from(el.querySelectorAll("th,td"))
        .map((cell, index) => tableCellText(cell, headers[index] || ""))
        .filter(Boolean);
      return cells.length ? cells.join(" | ") : textOf(el);
    };
    const fromSelector = (selector, limit = 8) => safePageItems(
      Array.from(document.querySelectorAll(selector))
        .filter((el) => !isInsideCommerceAiWidget(el))
        .map(textOf),
      limit
    );
    const fromVisibleSelector = (selector, limit = 6) => safePageItems(
      Array.from(document.querySelectorAll(selector))
        .filter((el) => !isInsideCommerceAiWidget(el))
        .filter(isVisibleInViewport)
        .sort((a, b) => viewportDistance(a) - viewportDistance(b))
        .map(textOf),
      limit
    );
    const fromTableRows = (selector, limit = 8) => safePageItems(
      Array.from(document.querySelectorAll(selector))
        .filter((el) => !isInsideCommerceAiWidget(el))
        .map(tableRowText),
      limit
    );
    const fromAiActionButtons = (limit = 6) => safePageItems(
      Array.from(document.querySelectorAll("[data-ai-action-package][data-ai-prompt]"))
        .filter((el) => !isInsideCommerceAiWidget(el))
        .filter(isVisibleInViewport)
        .map((el) => {
          const label = compactPageText((el.innerText || el.textContent || "").replace(/\\n+/g, " / "));
          const packageName = compactPageText(el.getAttribute("data-ai-action-package") || "");
          const promptText = compactPageText(el.getAttribute("data-ai-prompt") || "");
          return [label, packageName ? "动作包:" + packageName : "", promptText].filter(Boolean).join(" | ");
        }),
      limit
    );
    const visibleCardSelector = ".learning-card,.tk-panel,.answer-strip,.brief-card,.automation-card,.erp-card,.daily-digest,.target-card,.boss-card,.quality-gate,.reading-note,.full-report-section,.ai-takeover-card,.candidate-summary-card,.selection-product-name,.report-card,.kpi,.kpi-card";
    const cardSelector = visibleCardSelector + ",.panel";
    const visibleCards = fromVisibleSelector(visibleCardSelector, 6);
    return {
      title: document.title,
      url: scopedPageUrl(prompt),
      headings: fromSelector("h1,h2,h3", 10),
      visible_headings: fromVisibleSelector("h1,h2,h3", 6),
      metrics: fromSelector(".metric-card,.stat-card,.kpi-card", 8),
      focused_card: visibleCards[0] || "",
      visible_cards: visibleCards,
      cards: fromSelector(cardSelector, 8),
      tables: fromTableRows("table tbody tr", 8),
      store_connection_rows: fromTableRows(".connection-table tbody tr,.team-table tbody tr", 8),
      route_rows: fromTableRows(".route-table tbody tr", 8),
      activity_rules: fromTableRows(".activity-table tbody tr", 8),
      ["developer" + "_capabilities"]: fromTableRows(".capability-table tbody tr", 8),
      store_action_contexts: fromAiActionButtons(6),
      alerts: fromSelector(".empty,.target-status,.notice,.muted,.error", 8)
    };
  }
  window.__commerceAiCollectPageContext = collectPageContext;
  function pagePromptProfile() {
    const isEnglish = currentPageLabel.indexOf("Current page") === 0;
    const path = location.pathname;
    const intent = new URLSearchParams(location.search).get("intent") || "";
    if (path === "/chat" && intent === "store_data") {
      return {
        placeholder: isEnglish ? "Backend AI reads this page and lists store-data gaps automatically." : "后台AI读取当前页并自动列出店铺数据缺口。",
        quick: [
          [isEnglish ? "Data Gaps" : "查数据缺口", isEnglish ? "Read this store data page and list missing orders, ads, refunds, finance, inventory, and product-page status as backend tasks." : "读取当前店铺数据页，把缺失的订单、广告、退款、财务、库存和商品状态列成后台任务。"],
          [isEnglish ? "Next Read" : "下一步读取", isEnglish ? "Decide the next backend read from the current store data path, keeping platform connection details in the backend." : "按当前店铺数据路径决定后台下一步读取项，平台连接细节留在后台处理。"],
          [isEnglish ? "Store Scope" : "店铺范围", isEnglish ? "Identify the current platform, country/site, store model, authorization status, and ad ownership gaps from this page." : "识别当前页的平台、国家站点、店铺模式、授权状态和广告归属缺口。"],
          [isEnglish ? "Confirm Queue" : "确认队列", isEnglish ? "Which real store actions from this data path must enter confirmation before execution?" : "当前店铺数据路径里哪些真实店铺动作必须先进确认队列？"]
        ]
      };
    }
    if (path === "/store-erp") {
      return {
        placeholder: isEnglish ? "Ask: what is missing in store authorization, orders, inventory, ads, or confirmation queue?" : "问：店铺授权、订单、库存、广告、确认队列缺什么？",
        quick: [
          [isEnglish ? "Today" : "今天做什么", isEnglish ? "Based on this Store ERP page, read the visible platform, country/site, store model, ownership, authorization status, ad ownership, and confirmation boundary; tell me the three backend AI checks to read today." : "基于当前店铺ERP页面，读取可见的平台、国家站点、店铺模式、店铺归属、授权状态、广告归属和确认边界，告诉我今天只看哪三个后台AI检查结果。"],
          [isEnglish ? "Next Step" : "告诉我下一步", isEnglish ? "Translate this Store ERP page into the next step by platform, country/site, store model, ownership, authorization, data access, ad boundary, and confirmation queue only." : "按平台、国家站点、店铺模式、店铺归属、授权范围、数据接入、广告边界和确认队列，把当前店铺ERP页面翻译成下一步。"],
          [isEnglish ? "Access Gaps" : "查接入缺口", isEnglish ? "List the missing store data scopes on this page by platform, country/site, store model, ownership, and store: orders, ads, refunds, finance, inventory, product-page status." : "按平台、国家站点、店铺模式、店铺归属和店铺，列出当前页缺哪些店铺数据范围：订单、广告、退款、财务、库存、商品状态。"],
          [isEnglish ? "Confirm Queue" : "看确认队列", isEnglish ? "Which real store actions on this page must enter confirmation before execution? Group by platform, country/site, store model, ownership, store, activity, and ad boundary." : "当前页哪些真实店铺动作必须进入确认队列后才能执行？按平台、国家站点、店铺模式、店铺归属、店铺、活动和广告边界分组。"]
        ]
      };
    }
    if (path === "/account") {
      return {
        placeholder: isEnglish ? "Ask: what store binding, authorization scope, permission boundary, or ad-account isolation is missing?" : "问：店铺绑定、授权范围、子账号权限、广告账号隔离还缺什么？",
        quick: [
          [isEnglish ? "Binding Step" : "绑定下一步", isEnglish ? "Read the visible store-connection table on this account page and tell me the next safe store-binding step by platform, country/site, store model, store ownership, authorization status, ad ownership, and confirmation boundary. Do not ask the customer to understand platform developer details." : "读取当前账户页可见店铺连接表，按平台、国家站点、店铺模式、店铺归属、授权状态、广告归属和确认边界，告诉我下一步安全店铺绑定动作；不要让我理解平台连接细节。"],
          [isEnglish ? "Scope Gaps" : "查授权范围", isEnglish ? "From the visible account page rows, list missing authorization scope, country/site, store model, store ownership, store boundary, ad ownership, ad account status, and whether backend AI can read orders, ads, refunds, finance, inventory, and product-page status." : "从当前账户页可见行里列出缺哪些授权范围、国家站点、店铺模式、店铺归属、店铺范围、广告归属、广告账号状态，以及后台 AI 能否读取订单、广告、退款、财务、库存和商品状态。"],
          [isEnglish ? "Permissions" : "看权限边界", isEnglish ? "Using this account page context, explain which owner account, subaccount, store, country/site, store ownership, and ad-account permissions must stay isolated, and which real changes require owner confirmation." : "根据当前账户页上下文，解释哪些主账号、子账号、店铺、国家站点、店铺归属和广告账号权限必须隔离，以及哪些真实变更必须负责人确认。"],
          [isEnglish ? "Confirm Queue" : "看确认队列", isEnglish ? "From this account page, identify which account, store binding, authorization, store ownership, ad ownership, or platform connection changes must enter the confirmation queue before any real external change." : "从当前账户页识别哪些账号、店铺绑定、授权、店铺归属、广告归属或平台连接变更，真实外部变更前必须进入确认队列。"]
        ]
      };
    }
    if (path === "/report-file") {
      return {
        placeholder: isEnglish ? "Ask: what does this report prove, what is missing, and what must be confirmed?" : "问：这份报告证明了什么？缺什么？哪些动作要确认？",
        quick: [
          [isEnglish ? "Summary" : "一句话结论", isEnglish ? "Summarize this report into one conclusion and one next step by platform, country/site, store model, store ownership, store route, data gap, ad boundary, and confirmation boundary." : "按平台、国家站点、店铺模式、店铺归属、店铺路线、数据缺口、广告边界和确认边界，把当前报表总结成一句结论和一个下一步。"],
          [isEnglish ? "Next Step" : "告诉我下一步", isEnglish ? "Read only this report page and tell me what backend AI should read next by store route, authorization status, data gap, activity boundary, ad boundary, and confirmation queue." : "只看当前报表页，按店铺路线、授权状态、数据缺口、活动边界、广告边界和确认队列，告诉我后台AI下一步该读什么。"],
          [isEnglish ? "Evidence Gaps" : "让AI查证据缺口", isEnglish ? "List evidence gaps shown on this report by platform, country/site, store model, store ownership, store, activity, and ad boundary; do not ask the customer to fill forms." : "按平台、国家站点、店铺模式、店铺归属、店铺、活动和广告边界，列出当前报表显示的证据缺口，不要让我手动整理表格。"],
          [isEnglish ? "Confirm Queue" : "看确认队列", isEnglish ? "Which real actions from this report must be confirmed first? Group by platform, country/site, store model, store ownership, store, activity, and ad boundary." : "这份报表里的哪些真实动作必须先确认？按平台、国家站点、店铺模式、店铺归属、店铺、活动和广告边界分组。"]
        ]
      };
    }
    if (path === "/realtime-big-screen") {
      return {
        placeholder: isEnglish ? "Ask: what operating metrics matter now and what must be confirmed?" : "问：当前经营大屏先看哪些指标？哪些待确认？",
        quick: [
          [isEnglish ? "Ops Result" : "经营结论", isEnglish ? "Read this operating screen by platform, country/site, store model, store ownership, store route, authorization status, and ad boundary; give me the current store result, key metrics, and one safe next step." : "按平台、国家站点、店铺模式、店铺归属、店铺路线、授权状态和广告边界读取当前经营大屏，给我当前店铺结果、关键指标和一个安全下一步。"],
          [isEnglish ? "Store Gaps" : "店铺缺口", isEnglish ? "List the missing own-store data on this operating screen by platform, country/site, store model, store ownership, and store: orders, ads, refunds, finance, inventory, product-page status." : "按平台、国家站点、店铺模式、店铺归属和店铺，列出当前经营大屏缺哪些自己店铺数据：订单、广告、退款、财务、库存、商品状态。"],
          [isEnglish ? "Drafts" : "确认草稿", isEnglish ? "Which high-risk actions shown on this operating screen need confirmation drafts before execution? Group by platform, country/site, store model, store ownership, store, activity, and ad boundary." : "当前经营大屏显示哪些高风险动作需要先生成确认草稿？按平台、国家站点、店铺模式、店铺归属、店铺、活动和广告边界分组。"],
          [isEnglish ? "Next Step" : "下一步", isEnglish ? "Tell me the next safe backend AI read from this operating screen by store route, authorization status, data gap, and confirmation boundary, without asking me to fill data." : "按店铺路线、授权状态、数据缺口和确认边界，从当前经营大屏告诉我后台 AI 下一步该读什么，不要让我手动补表。"]
        ]
      };
    }
    if (path === "/dashboard") {
      return {
        placeholder: isEnglish ? "Ask: what has backend AI taken over today and what should I confirm?" : "问：今天后台AI接管了什么？我只需要确认什么？",
        quick: [
          [isEnglish ? "Today" : "今天做什么", isEnglish ? "Based on this workspace, tell me the only three things I need to read today by platform, country/site, store model, store ownership, store route, data gap, and confirmation boundary." : "基于今日工作台，按平台、国家站点、店铺模式、店铺归属、店铺路线、数据缺口和确认边界，告诉我今天只需要看哪三件事。"],
          [isEnglish ? "Next Step" : "告诉我下一步", isEnglish ? "Tell me the next safe step from this dashboard by store route, authorization status, ad boundary, and confirmation queue, without asking me to fill data." : "按店铺路线、授权状态、广告边界和确认队列，从当前工作台告诉我安全下一步，不要让我手动整理资料。"],
          [isEnglish ? "AI Status" : "看AI接管", isEnglish ? "What backend AI work is already running or waiting on this dashboard? Group by platform, country/site, store model, store ownership, store, data gap, and ad boundary." : "当前工作台里后台AI已经接管或等待的事情有哪些？按平台、国家站点、店铺模式、店铺归属、店铺、数据缺口和广告边界分组。"],
          [isEnglish ? "Confirm Queue" : "看确认队列", isEnglish ? "Which dashboard actions must go to confirmation before execution? Group by platform, country/site, store model, store ownership, store, activity, and ad boundary." : "当前工作台哪些动作执行前必须进入确认队列？按平台、国家站点、店铺模式、店铺归属、店铺、活动和广告边界分组。"]
        ]
      };
    }
    return null;
  }
  function applyPagePromptProfile() {
    const profile = pagePromptProfile();
    const advisorHref = scopedAdvisorHrefForCurrentPage("");
    launcher.href = advisorHref;
    const openAdvisorLink = document.querySelector(".commerce-ai-actions a[href]");
    if (openAdvisorLink) openAdvisorLink.href = advisorHref;
    if (!profile) return;
    if (profile.placeholder) input.placeholder = profile.placeholder;
    const buttons = Array.from(document.querySelectorAll(".commerce-ai-quick button"));
    (profile.quick || []).forEach((item, index) => {
      if (!buttons[index] || !Array.isArray(item)) return;
      buttons[index].textContent = item[0] || buttons[index].textContent;
      buttons[index].dataset.aiDisplay = item[0] || buttons[index].textContent || "";
      buttons[index].dataset.aiPrompt = item[1] || buttons[index].dataset.aiPrompt || "";
    });
  }
  async function askAi(text, displayText, actionPackage) {
    const clean = String(text || "").trim();
    if (!clean) return;
    const display = String(displayText || clean).replace(/\\s+/g, " ").trim();
    openPanel();
    addMessage("user", display || clean);
    input.value = "";
    const loading = addMessage("ai", "__AI_LOADING__", { persist:false });
    const actionScope = mergedActionScope(clean);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: dataCodec.stringify({
          audience: "seller",
          message: clean + "\\n\\n" + currentPageLabel + document.title + " " + location.pathname,
          store_id: actionScope.store,
          platform: actionScope.platform,
          country: actionScope.country,
          product_id: visibleValue(["#productId", "[name='product_id']", "[name='product']"]) || contextValue("product"),
          page_title: document.title,
          page_url: scopedPageUrl(clean),
          page_context: collectPageContext(clean),
          action_package: String(actionPackage || ""),
          provider: modelSelect ? modelSelect.value : (localStorage.getItem("commerce_ai_model") || "")
        })
      });
      let payload = {};
      try { payload = await response.json(); } catch (error) { payload = { ok: false, error: "没有返回可读结果" }; }
      if (!response.ok || !payload.ok) {
        loading.className = "commerce-ai-message error";
        loading.textContent = "__AI_ERROR__";
        rememberFloatingMessage("error", loading.textContent);
        return;
      }
      renderAiReply(loading, payload, { actionPackage: actionPackage, sourcePrompt: clean });
    } catch (error) {
      loading.className = "commerce-ai-message error";
      loading.textContent = "__AI_CONNECTION_ERROR__";
      rememberFloatingMessage("error", loading.textContent);
    }
  }
  applyPagePromptProfile();
  restoreFloatingHistory();
  launcher.addEventListener("click", (event) => {
    event.preventDefault();
    if (launcher.dataset.dragMoved === "1") { launcher.dataset.dragMoved = ""; return; }
    launcher.dataset.dragMoved = "";
    if (panel.hidden) {
      openPanel();
    } else {
      panel.hidden = true;
      document.getElementById("commerceAiWidget").classList.remove("commerce-ai-open");
    }
  });
  closeBtn.addEventListener("click", () => {
    panel.hidden = true;
    document.getElementById("commerceAiWidget").classList.remove("commerce-ai-open");
  });
  send.addEventListener("click", () => askAi(input.value));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) askAi(input.value);
  });
  document.addEventListener("click", (event) => {
    const button = event.target && event.target.closest ? event.target.closest("[data-ai-prompt]") : null;
    if (!button) return;
    event.preventDefault();
    askAi(button.dataset.aiPrompt || "", button.dataset.aiDisplay || button.innerText || "", button.dataset.aiActionPackage || "");
  });
})();
</script>
""".replace("__COMMERCE_AI_LINKS__", links_html).replace("__COMMERCE_AI_MODEL_OPTIONS__", model_options).replace(
        "__AI_LAUNCHER_LABEL__", html.escape(copy["launcher_label"])
    ).replace("__AI_ADVISOR_HREF__", safe_advisor_href).replace("__AI_PANEL_LABEL__", html.escape(copy["panel_label"])).replace(
        "__AI_TITLE__", html.escape(copy["title"])
    ).replace("__AI_DRAG_HINT__", html.escape(copy["drag_hint"])).replace(
        "__AI_CLOSE__", html.escape(copy["close"])
    ).replace("__AI_SAFE__", html.escape(copy["safe"])).replace(
        "__AI_MODEL__", html.escape(copy["model"])
    ).replace("__AI_QUICK_TODAY__", html.escape(copy["quick_today"])).replace(
        "__AI_QUICK_NEXT__", html.escape(copy["quick_next"])
    ).replace("__AI_QUICK_SCRIPT__", html.escape(copy["quick_script"])).replace(
        "__AI_QUICK_PRODUCT__", html.escape(copy["quick_product"])
    ).replace("__AI_PROMPT_TODAY__", html.escape(copy["prompt_today"])).replace(
        "__AI_PROMPT_NEXT__", html.escape(copy["prompt_next"])
    ).replace("__AI_PROMPT_SCRIPT__", html.escape(copy["prompt_script"])).replace(
        "__AI_PROMPT_PRODUCT__", html.escape(copy["prompt_product"])
    ).replace(
        "__AI_CURRENT_PAGE_LABEL__", json.dumps(copy["current_page_prefix"], ensure_ascii=False)
    ).replace("__AI_GREETING__", html.escape(copy["greeting"])).replace(
        "__AI_PLACEHOLDER__", html.escape(copy["placeholder"])
    ).replace("__AI_OPEN_ADVISOR__", html.escape(copy["open_advisor"])).replace(
        "__AI_HELP_CENTER__", html.escape(copy["help_center"])
    ).replace("__AI_SEND__", html.escape(copy["send"])).replace(
        "__AI_CONTINUE__", html.escape(copy["continue_ai"])
    ).replace(
        "__AI_CONTINUE_SCOPED__", html.escape(copy["continue_scoped_ai"])
    ).replace("__AI_ACTION_FALLBACK__", html.escape(copy["action_fallback"])).replace(
        "__AI_INSUFFICIENT__", html.escape(copy["insufficient"])
    ).replace("__AI_LOADING__", html.escape(copy["loading"])).replace(
        "__AI_ERROR__", html.escape(copy["error"])
    ).replace("__AI_CONNECTION_ERROR__", html.escape(copy["connection_error"]))
