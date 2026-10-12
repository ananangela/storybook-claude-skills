// 埋點便利貼(Tracking Notes):畫面上的本體。
//
// PM 在任何一個 story 畫面上按「＋ 新增便利貼」,再點畫面上要標的位置,就會出現一張
// 綠色便利貼:選「既有埋點／新埋點／互動說明／補充資訊」,填觸發行為、事件名稱、參數、
// 補充、作者,存檔後寫進倉庫 `design-system/tracking-notes/<story>.json`(見 server.mjs),
// 同一台 Storybook 的所有人都看得到,Claude 也直接讀那些檔。
//
// 位置以「手機畫面外框」為基準記比例(xRatio／yRatio),視窗大小改變便利貼仍貼在同一處。
// 靜態建置版(storybook build)沒有伺服器,會退成唯讀:讀 staticDirs 的同一批 JSON。
import { toCanvas } from "html-to-image";
import { createElement as h, Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { createRoot } from "react-dom/client";

import "./tracking-notes.css";

const API_PATH = "/__tracking_notes";
const STATIC_NOTES_PATH = "/tracking-notes";
const EVENTS_URL = "/tracking-events/invoice-manager.json";
const AUTHOR_STORAGE_KEY = "tn:author";
const GLOBAL_NAME = "trackingNotes";
// 便利貼位置的基準框,依序找:手機預覽外框 → story 自己的最外層容器 → Storybook 根節點。
const ANCHOR_SELECTORS = [".ds-storybook-mobile-preview-frame", "#storybook-root > :first-child", "#storybook-root"];
const CAPTURE_MAX_SIDE = 720;

const KINDS = [
  { id: "existing", label: "既有埋點", hint: "事件清單裡已經有的事件(含別的功能先登記、還沒進 PM 表的),從清單挑一個,沿用原名。" },
  { id: "new", label: "新埋點", hint: "清單裡還沒有的事件。存檔後會自動登記進事件清單,之後別的功能就當既有埋點挑。名稱可以留空,交給 Claude 依命名規範命名。" },
  { id: "interaction", label: "互動說明", hint: "說明這裡怎麼互動、會發生什麼。" },
  { id: "info", label: "補充資訊", hint: "其他要給工程或 Claude 的補充。" },
];
const KIND_LABEL = Object.fromEntries(KINDS.map((kind) => [kind.id, kind.label]));

/* ------------------------------------------------------------------ */
/* 小工具                                                               */
/* ------------------------------------------------------------------ */

function storyFileStem(storyId) {
  return String(storyId ?? "")
    .replace(/[^\p{L}\p{N}_-]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 160);
}

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function findAnchor() {
  for (const selector of ANCHOR_SELECTORS) {
    const element = document.querySelector(selector);
    if (element && element.getBoundingClientRect().width > 0) return { element, selector };
  }
  return { element: document.body, selector: "body" };
}

/* 流程走查看板(FlowStoryboard):畫面上有 `[data-flow-board]` 時,便利貼改成**跟那條流程存**
   (檔名 `flow-<流程代號>.json`),不管是從哪一則 story 切過來看的;位置以「那一步的手機畫面框」
   為基準記比例,流程多一步或縮放改了都不會跑掉。 */
const BOARD_SELECTOR = "[data-flow-board]";
const STEP_FRAME_SELECTOR = ".ds-flow-storyboard__frame";

function findBoard() {
  const element = document.querySelector(BOARD_SELECTOR);
  if (!element) return null;
  const id = element.getAttribute("data-flow-board") ?? "";
  const title = (element.querySelector(".ds-flow-storyboard__title")?.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80);
  /* 看板可以自己說它屬於哪一則 story（全 App 流程圖用 data-flow-board-story-title），沒寫就是好友功能的流程走查 */
  const storyTitle = element.getAttribute("data-flow-board-story-title") ?? "好友功能/流程走查";
  return id ? { id, title, storyTitle } : null;
}

function stepFrameSelector(boardId, stepId) {
  return `[data-flow-board="${boardId}"] [data-flow-step="${stepId}"] ${STEP_FRAME_SELECTOR}`;
}

function toRect(element) {
  const next = element.getBoundingClientRect();
  return { left: next.left, top: next.top, width: next.width, height: next.height };
}

function isOurs(node) {
  return node instanceof Element && Boolean(node.closest("[data-tn-ignore]"));
}

function detectScreenLabel(target) {
  // 流程走查看板:貼在哪一步就記那一步(「第 3 步・好友頁：邀請」),不是整塊看板的標題。
  const step = target instanceof Element ? target.closest("[data-flow-step]") : null;
  if (step) return (step.getAttribute("data-flow-step-title") ?? "").slice(0, 60);
  // 只在 story 內容裡找,避免撿到 Storybook 自己藏起來的「No Preview」標題。
  const root = document.querySelector("#storybook-root");
  const element = root?.querySelector(
    ".ds-nav-bar__title, .ds-nav-bar-inverse__title-group, [data-screen-title], h1",
  );
  return (element?.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 40);
}

function describeTarget(target) {
  if (!(target instanceof Element)) return null;
  const element =
    target.closest("button, a, [role='button'], input, select, textarea, label, li, [data-testid]") ?? target;
  const label = (element.getAttribute("aria-label") || element.textContent || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 40);
  return { tag: element.tagName.toLowerCase(), label };
}

function formatDate(iso) {
  return typeof iso === "string" ? iso.slice(0, 10).replace(/-/g, "/") : "";
}

function readStoredAuthor() {
  try {
    return window.localStorage.getItem(AUTHOR_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function storeAuthor(value) {
  try {
    window.localStorage.setItem(AUTHOR_STORAGE_KEY, value);
  } catch {
    /* 私密視窗等情況存不了就算了 */
  }
}

async function captureAnchor(element) {
  const canvas = await toCanvas(element, {
    cacheBust: false,
    filter: (node) => !(node instanceof Element && node.hasAttribute("data-tn-ignore")),
    pixelRatio: 1,
  });
  const scale = Math.min(1, CAPTURE_MAX_SIDE / Math.max(canvas.width, canvas.height));
  if (scale >= 1) return canvas.toDataURL("image/webp", 0.8);
  const small = document.createElement("canvas");
  small.width = Math.round(canvas.width * scale);
  small.height = Math.round(canvas.height * scale);
  small.getContext("2d").drawImage(canvas, 0, 0, small.width, small.height);
  return small.toDataURL("image/webp", 0.8);
}

async function requestJson(url, init) {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `伺服器回應 ${response.status}`);
  return payload;
}

let eventsPromise = null;
function loadEvents() {
  eventsPromise ??= fetch(EVENTS_URL)
    .then((response) => (response.ok ? response.json() : { events: [] }))
    .then((payload) => (Array.isArray(payload.events) ? payload.events : []))
    .catch(() => []);
  return eventsPromise;
}

/**
 * 追蹤基準框在視窗裡的位置,便利貼跟著它走。
 * 回傳:`rect` 預設基準框(手機外框／story 最外層);`board` 畫面上的流程走查看板(沒有就 null);
 * `stepRects` 看板裡每一步手機畫面框的位置(步驟代號 → rect)。
 */
function useAnchorRects(active) {
  const [state, setState] = useState({ rect: null, board: null, stepRects: {} });
  useEffect(() => {
    if (!active) return undefined;
    let frame = 0;
    let last = "";
    const tick = () => {
      const rect = toRect(findAnchor().element);
      const board = findBoard();
      const stepRects = {};
      if (board) {
        document.querySelectorAll(`[data-flow-board="${board.id}"] [data-flow-step]`).forEach((step) => {
          const stepFrame = step.querySelector(STEP_FRAME_SELECTOR);
          const stepId = step.getAttribute("data-flow-step");
          if (stepFrame && stepId) stepRects[stepId] = toRect(stepFrame);
        });
      }
      const key = JSON.stringify([rect, board, stepRects]);
      if (key !== last) {
        last = key;
        setState({ rect, board, stepRects });
      }
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [active]);
  return state;
}

/* ------------------------------------------------------------------ */
/* 主元件                                                               */
/* ------------------------------------------------------------------ */

function TrackingNotes({ context }) {
  const currentStory = useMemo(
    () => ({ id: context.id, title: context.title ?? "", name: context.name ?? "" }),
    [context.id, context.title, context.name],
  );
  const visible = context.globals?.[GLOBAL_NAME] !== "hide";
  const { rect, board, stepRects } = useAnchorRects(visible);
  /* 畫面上是流程走查看板時,便利貼跟那條流程存,不跟目前的 story 存。 */
  const story = useMemo(
    () => (board ? { id: `flow-${board.id}`, title: board.storyTitle, name: board.title } : currentStory),
    [board, currentStory],
  );
  /* 哪一張便利貼用哪個基準框:貼在某一步的用那一步的手機畫面框;那一步已經不存在就先不畫。 */
  const rectFor = useCallback(
    (flowStep) => (flowStep ? stepRects[flowStep] ?? null : rect),
    [rect, stepRects],
  );

  const [writable, setWritable] = useState(null);
  const [notes, setNotes] = useState([]);
  const [fileName, setFileName] = useState("");
  const [events, setEvents] = useState([]);
  const [armed, setArmed] = useState(false);
  const [draft, setDraft] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());
  const [panelOpen, setPanelOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);

  const showToast = useCallback((message) => {
    setToast(message);
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => setToast(""), 3200);
  }, []);

  // 有沒有伺服器(設計師電腦上的 Storybook)決定能不能寫。
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_PATH}/status`)
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => !cancelled && setWritable(Boolean(payload?.writable)))
      .catch(() => !cancelled && setWritable(false));
    loadEvents().then((list) => !cancelled && setEvents(list));
    return () => {
      cancelled = true;
    };
  }, []);

  // 換 story 就重新讀那個 story 的便利貼。
  useEffect(() => {
    if (writable === null) return undefined;
    let cancelled = false;
    setNotes([]);
    setDraft(null);
    setArmed(false);
    setExpanded(new Set());
    const stem = storyFileStem(story.id);
    const url = writable
      ? `${API_PATH}/notes?story=${encodeURIComponent(story.id)}`
      : `${STATIC_NOTES_PATH}/${encodeURIComponent(stem)}.json`;
    fetch(url)
      .then((response) => (response.ok ? response.json() : { notes: [] }))
      .then((payload) => {
        if (cancelled) return;
        setNotes(Array.isArray(payload.notes) ? payload.notes : []);
        setFileName(payload.file ?? `${stem}.json`);
      })
      .catch(() => !cancelled && setNotes([]));
    return () => {
      cancelled = true;
    };
  }, [story.id, writable]);

  // 「新增」模式:攔下下一次點擊,拿位置,不讓原型跟著換頁。
  useEffect(() => {
    if (!armed) return undefined;
    document.body.classList.add("tn-arming");
    const options = { capture: true };
    const block = (event) => {
      if (isOurs(event.target)) return;
      event.stopPropagation();
      event.preventDefault();
    };
    const onPointerDown = (event) => {
      if (isOurs(event.target)) return;
      event.stopPropagation();
      event.preventDefault();
      /* 點在流程走查的某一步上:基準框是那一步的手機畫面框,並記下步驗代號。 */
      const stepElement = event.target instanceof Element ? event.target.closest("[data-flow-step]") : null;
      const stepFrame = stepElement?.querySelector(STEP_FRAME_SELECTOR) ?? null;
      const boardId = stepElement?.closest(BOARD_SELECTOR)?.getAttribute("data-flow-board") ?? "";
      const flowStep = stepFrame ? stepElement.getAttribute("data-flow-step") : null;
      const fallback = findAnchor();
      const element = stepFrame ?? fallback.element;
      const selector = stepFrame ? stepFrameSelector(boardId, flowStep) : fallback.selector;
      const bounds = element.getBoundingClientRect();
      const pin = {
        xRatio: clamp01((event.clientX - bounds.left) / bounds.width),
        yRatio: clamp01((event.clientY - bounds.top) / bounds.height),
      };
      const target = describeTarget(event.target);
      const screen = detectScreenLabel(event.target);
      setArmed(false);
      setDraft({
        mode: "create",
        pin,
        target,
        screen,
        flowStep,
        anchor: { selector, cssWidth: Math.round(bounds.width), cssHeight: Math.round(bounds.height) },
        capture: null,
        fields: {
          kind: "existing",
          trigger: target?.label ? `點「${target.label}」` : "",
          eventName: "",
          params: "",
          note: "",
          author: readStoredAuthor(),
          status: "open",
        },
      });
      captureAnchor(element)
        .then((dataUrl) => setDraft((current) => (current && current.mode === "create" ? { ...current, capture: dataUrl } : current)))
        .catch(() => {});
    };
    const onKey = (event) => {
      if (event.key === "Escape") setArmed(false);
    };
    document.addEventListener("pointerdown", onPointerDown, options);
    const blocked = ["pointerup", "click", "mousedown", "mouseup", "touchstart", "touchend"];
    blocked.forEach((type) => document.addEventListener(type, block, options));
    document.addEventListener("keydown", onKey, options);
    return () => {
      document.body.classList.remove("tn-arming");
      document.removeEventListener("pointerdown", onPointerDown, options);
      blocked.forEach((type) => document.removeEventListener(type, block, options));
      document.removeEventListener("keydown", onKey, options);
    };
  }, [armed]);

  const toggleExpanded = useCallback((id) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const saveDraft = useCallback(async () => {
    if (!draft || busy) return;
    let { fields } = draft;
    /* 「新埋點」填的名字其實已經在清單裡 → 自動改成既有埋點,免得同一個事件被兩個功能各自當新的 */
    if (fields.kind === "new" && fields.eventName.trim()) {
      const list = await loadEvents();
      const hit = list.find((event) => event.name.toLowerCase() === fields.eventName.trim().toLowerCase());
      if (hit) {
        fields = { ...fields, kind: "existing", eventName: hit.name };
        showToast(`「${hit.name}」已經在事件清單裡,已改成既有埋點。`);
      }
    }
    const needsTrigger = fields.kind === "existing" || fields.kind === "new";
    if (needsTrigger && !fields.trigger.trim()) return showToast("請填「觸發行為」。");
    if (fields.kind === "existing" && !fields.eventName.trim()) return showToast("請從清單選一個既有事件。");
    if (!needsTrigger && !fields.note.trim()) return showToast("請填說明內容。");
    setBusy(true);
    try {
      if (fields.author) storeAuthor(fields.author);
      if (draft.mode === "create") {
        const payload = await requestJson(`${API_PATH}/notes`, {
          body: JSON.stringify({
            capture: draft.capture,
            note: { ...fields, anchor: draft.anchor, pin: draft.pin, screen: draft.screen, target: draft.target, flowStep: draft.flowStep ?? null },
            story,
          }),
          headers: { "Content-Type": "application/json" },
          method: "POST",
        });
        setNotes((current) => [...current, payload.note]);
        setExpanded((current) => new Set(current).add(payload.note.id));
        if (payload.file) setFileName(payload.file);
        showToast("已存到倉庫。");
      } else {
        const payload = await requestJson(
          `${API_PATH}/notes/${encodeURIComponent(story.id)}/${encodeURIComponent(draft.noteId)}`,
          { body: JSON.stringify(fields), headers: { "Content-Type": "application/json" }, method: "PATCH" },
        );
        setNotes((current) => current.map((note) => (note.id === payload.note.id ? payload.note : note)));
        showToast("已更新。");
      }
      setDraft(null);
    } catch (error) {
      showToast(`存檔失敗:${error.message}`);
    } finally {
      setBusy(false);
    }
  }, [busy, draft, showToast, story]);

  const patchNote = useCallback(
    async (note, patch) => {
      try {
        const payload = await requestJson(
          `${API_PATH}/notes/${encodeURIComponent(story.id)}/${encodeURIComponent(note.id)}`,
          { body: JSON.stringify(patch), headers: { "Content-Type": "application/json" }, method: "PATCH" },
        );
        setNotes((current) => current.map((item) => (item.id === payload.note.id ? payload.note : item)));
      } catch (error) {
        showToast(`更新失敗:${error.message}`);
      }
    },
    [showToast, story.id],
  );

  const removeNote = useCallback(
    async (note) => {
      if (!window.confirm("確定刪除這張便利貼?刪掉就找不回來。")) return;
      try {
        await requestJson(`${API_PATH}/notes/${encodeURIComponent(story.id)}/${encodeURIComponent(note.id)}`, {
          method: "DELETE",
        });
        setNotes((current) => current.filter((item) => item.id !== note.id));
        showToast("已刪除。");
      } catch (error) {
        showToast(`刪除失敗:${error.message}`);
      }
    },
    [showToast, story.id],
  );

  const startEdit = useCallback((note) => {
    setDraft({
      mode: "edit",
      noteId: note.id,
      pin: note.pin,
      flowStep: note.flowStep ?? null,
      fields: {
        kind: note.kind,
        trigger: note.trigger ?? "",
        eventName: note.eventName ?? "",
        params: note.params ?? "",
        note: note.note ?? "",
        author: note.author ?? "",
        status: note.status ?? "open",
      },
    });
  }, []);

  if (!visible) return null;

  const layer = h(
    "div",
    { className: "tn-layer", "data-tn-ignore": "" },
    armed && h("div", { className: "tn-arm-hint" }, "點畫面上要標註的位置(Esc 取消)"),
    rect &&
      notes.map((note, index) => {
        const noteRect = rectFor(note.flowStep);
        if (!noteRect) return null;
        return h(NoteMarker, {
          expanded: expanded.has(note.id),
          hidden: draft?.mode === "edit" && draft.noteId === note.id,
          key: note.id,
          note,
          onDelete: () => removeNote(note),
          onEdit: () => startEdit(note),
          onMove: (pin) => patchNote(note, { pin }),
          onToggle: () => toggleExpanded(note.id),
          onToggleStatus: () => patchNote(note, { status: note.status === "confirmed" ? "open" : "confirmed" }),
          ordinal: index + 1,
          rect: noteRect,
          writable,
        });
      }),
    rect &&
      draft &&
      rectFor(draft.flowStep) &&
      h(Composer, {
        busy,
        draft,
        events,
        onCancel: () => setDraft(null),
        onChange: (fields) => setDraft((current) => (current ? { ...current, fields: { ...current.fields, ...fields } } : current)),
        onSave: saveDraft,
        ordinal: draft.mode === "edit" ? notes.findIndex((note) => note.id === draft.noteId) + 1 : notes.length + 1,
        rect: rectFor(draft.flowStep),
      }),
    h(Launcher, {
      armed,
      count: notes.length,
      fileName,
      notes,
      onArm: () => {
        setDraft(null);
        setArmed((current) => !current);
      },
      onCollapseAll: () => setExpanded(new Set()),
      onExpandAll: () => setExpanded(new Set(notes.map((note) => note.id))),
      onFocus: (note) => setExpanded((current) => new Set(current).add(note.id)),
      onTogglePanel: () => setPanelOpen((current) => !current),
      panelOpen,
      writable,
    }),
    toast && h("div", { className: "tn-toast", role: "status" }, toast),
  );

  return createPortal(layer, document.body);
}

/* ------------------------------------------------------------------ */
/* 便利貼本體                                                            */
/* ------------------------------------------------------------------ */

function pinPosition(rect, pin) {
  return { x: rect.left + pin.xRatio * rect.width, y: rect.top + pin.yRatio * rect.height };
}

function cardPlacement(x, y) {
  const cardWidth = Math.min(300, window.innerWidth - 24);
  const flip = x + 28 + cardWidth > window.innerWidth - 12;
  return {
    left: flip ? Math.max(12, Math.min(x - 28 - cardWidth, window.innerWidth - 12 - cardWidth)) : x + 28,
    top: Math.max(12, Math.min(y - 20, window.innerHeight - 360)),
    side: flip ? "left" : "right",
  };
}

function NoteMarker({ expanded, hidden, note, onDelete, onEdit, onMove, onToggle, onToggleStatus, ordinal, rect, writable }) {
  const [dragPin, setDragPin] = useState(null);
  const dragState = useRef(null);
  const pin = dragPin ?? note.pin;
  const { x, y } = pinPosition(rect, pin);

  const onPointerDown = (event) => {
    if (!writable) return;
    event.preventDefault();
    dragState.current = { startX: event.clientX, startY: event.clientY, moved: false };
    const onMoveEvent = (moveEvent) => {
      const state = dragState.current;
      if (!state) return;
      if (!state.moved && Math.hypot(moveEvent.clientX - state.startX, moveEvent.clientY - state.startY) < 4) return;
      state.moved = true;
      setDragPin({
        xRatio: clamp01((moveEvent.clientX - rect.left) / rect.width),
        yRatio: clamp01((moveEvent.clientY - rect.top) / rect.height),
      });
    };
    const onUp = (upEvent) => {
      window.removeEventListener("pointermove", onMoveEvent);
      window.removeEventListener("pointerup", onUp);
      const state = dragState.current;
      dragState.current = null;
      if (state?.moved) {
        onMove({
          xRatio: clamp01((upEvent.clientX - rect.left) / rect.width),
          yRatio: clamp01((upEvent.clientY - rect.top) / rect.height),
        });
        setDragPin(null);
      } else {
        onToggle();
      }
    };
    window.addEventListener("pointermove", onMoveEvent);
    window.addEventListener("pointerup", onUp);
  };

  if (hidden) return null;
  const placement = cardPlacement(x, y);
  const confirmed = note.status === "confirmed";

  return h(
    Fragment,
    null,
    h(
      "button",
      {
        "aria-expanded": expanded,
        "aria-label": `便利貼 ${ordinal}:${KIND_LABEL[note.kind] ?? note.kind}`,
        className: `tn-pin tn-pin--${note.kind}${confirmed ? " tn-pin--confirmed" : ""}${expanded ? " tn-pin--open" : ""}`,
        onClick: writable ? undefined : onToggle,
        onPointerDown: writable ? onPointerDown : undefined,
        style: { left: `${x}px`, top: `${y}px` },
        title: writable ? "點一下展開,按住拖曳移動" : "點一下展開",
        type: "button",
      },
      ordinal,
    ),
    expanded &&
      h(
        "article",
        {
          className: `tn-card tn-card--${note.kind} tn-card--${placement.side}${confirmed ? " tn-card--confirmed" : ""}`,
          style: { left: `${placement.left}px`, top: `${placement.top}px` },
        },
        h(
          "header",
          { className: "tn-card__head" },
          h("span", { className: "tn-card__kind" }, KIND_LABEL[note.kind] ?? note.kind),
          h("span", { className: "tn-card__ordinal" }, `#${ordinal}`),
          h("button", { className: "tn-card__close", onClick: onToggle, title: "收合", type: "button" }, "×"),
        ),
        h(
          "dl",
          { className: "tn-card__body" },
          (note.screen || note.target?.label) &&
            h(Fragment, null, h("dt", null, "位置"), h("dd", null, [note.screen, note.target?.label && `「${note.target.label}」`].filter(Boolean).join(" · "))),
          note.trigger && h(Fragment, null, h("dt", null, "觸發行為"), h("dd", null, note.trigger)),
          (note.kind === "existing" || note.kind === "new") &&
            h(
              Fragment,
              null,
              h("dt", null, "事件名稱"),
              h(
                "dd",
                null,
                note.eventName
                  ? h("code", null, note.eventName)
                  : h("em", { className: "tn-card__pending" }, "留空:由 Claude 依命名規範命名"),
              ),
            ),
          note.params && h(Fragment, null, h("dt", null, "參數"), h("dd", { className: "tn-card__pre" }, note.params)),
          note.note && h(Fragment, null, h("dt", null, note.kind === "interaction" || note.kind === "info" ? "說明" : "補充"), h("dd", { className: "tn-card__pre" }, note.note)),
        ),
        h(
          "footer",
          { className: "tn-card__foot" },
          h("span", { className: "tn-card__author" }, h("i", { "aria-hidden": "true" }), note.author || "未署名", " · ", formatDate(note.updatedAt || note.createdAt)),
          h(
            "label",
            { className: "tn-card__status" },
            h("input", { checked: confirmed, disabled: !writable, onChange: onToggleStatus, type: "checkbox" }),
            confirmed ? "已確認" : "待確認",
          ),
        ),
        writable &&
          h(
            "div",
            { className: "tn-card__actions" },
            h("button", { className: "tn-btn tn-btn--ghost", onClick: onEdit, type: "button" }, "編輯"),
            h("button", { className: "tn-btn tn-btn--danger", onClick: onDelete, type: "button" }, "刪除"),
          ),
      ),
  );
}

/* ------------------------------------------------------------------ */
/* 填寫表單                                                              */
/* ------------------------------------------------------------------ */

function Composer({ busy, draft, events, onCancel, onChange, onSave, ordinal, rect }) {
  const { fields } = draft;
  const { x, y } = pinPosition(rect, draft.pin);
  const placement = cardPlacement(x, y);
  const [query, setQuery] = useState(fields.eventName);
  const [listOpen, setListOpen] = useState(false);
  const kindMeta = KINDS.find((kind) => kind.id === fields.kind) ?? KINDS[0];
  const isEvent = fields.kind === "existing" || fields.kind === "new";

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const pool = needle
      ? events.filter(
          (event) =>
            event.name.toLowerCase().includes(needle) ||
            (event.description ?? "").toLowerCase().includes(needle) ||
            (event.module ?? "").toLowerCase().includes(needle),
        )
      : events;
    return pool.slice(0, 8);
  }, [events, query]);
  const selected = events.find((event) => event.name === fields.eventName);
  const duplicate =
    fields.kind === "new" && fields.eventName.trim()
      ? events.find((event) => event.name.toLowerCase() === fields.eventName.trim().toLowerCase())
      : null;

  const field = (label, control, hint) =>
    h("label", { className: "tn-field" }, h("span", { className: "tn-field__label" }, label), control, hint && h("span", { className: "tn-field__hint" }, hint));

  return h(
    Fragment,
    null,
    h("span", { className: `tn-pin tn-pin--${fields.kind} tn-pin--open tn-pin--draft`, style: { left: `${x}px`, top: `${y}px` } }, ordinal),
    h(
      "form",
      {
        className: `tn-card tn-card--composer tn-card--${fields.kind} tn-card--${placement.side}`,
        onSubmit: (event) => {
          event.preventDefault();
          onSave();
        },
        style: { left: `${placement.left}px`, top: `${placement.top}px` },
      },
      h(
        "header",
        { className: "tn-card__head" },
        h("span", { className: "tn-card__kind" }, draft.mode === "create" ? "新便利貼" : "編輯便利貼"),
        h("span", { className: "tn-card__ordinal" }, `#${ordinal}`),
        h("button", { className: "tn-card__close", onClick: onCancel, title: "取消", type: "button" }, "×"),
      ),
      h(
        "div",
        { className: "tn-kinds", role: "radiogroup", "aria-label": "類型" },
        KINDS.map((kind) =>
          h(
            "button",
            {
              "aria-checked": fields.kind === kind.id,
              className: `tn-kinds__option${fields.kind === kind.id ? " is-active" : ""}`,
              key: kind.id,
              onClick: () => onChange({ kind: kind.id }),
              role: "radio",
              type: "button",
            },
            kind.label,
          ),
        ),
      ),
      h("p", { className: "tn-kind-hint" }, kindMeta.hint),
      draft.mode === "create" &&
        (draft.screen || draft.target?.label) &&
        h("p", { className: "tn-context" }, "位置:", [draft.screen, draft.target?.label && `「${draft.target.label}」`].filter(Boolean).join(" · ")),
      isEvent &&
        field(
          "觸發行為",
          h("input", {
            autoFocus: true,
            className: "tn-input",
            onChange: (event) => onChange({ trigger: event.target.value }),
            placeholder: "例:點「加好友」、進入好友頁",
            value: fields.trigger,
          }),
        ),
      fields.kind === "existing" &&
        h(
          "div",
          { className: "tn-field" },
          h("span", { className: "tn-field__label" }, "事件名稱(從埋點表挑)"),
          h(
            "div",
            { className: "tn-picker" },
            h("input", {
              className: "tn-input tn-input--mono",
              onBlur: () => window.setTimeout(() => setListOpen(false), 120),
              onChange: (event) => {
                setQuery(event.target.value);
                onChange({ eventName: event.target.value });
                setListOpen(true);
              },
              onFocus: () => setListOpen(true),
              placeholder: events.length ? "輸入關鍵字搜尋,例:invite、popup" : "清單載入中…",
              value: fields.eventName,
            }),
            listOpen &&
              matches.length > 0 &&
              h(
                "ul",
                { className: "tn-picker__list", role: "listbox" },
                matches.map((event) =>
                  h(
                    "li",
                    {
                      className: "tn-picker__item",
                      key: event.name,
                      onMouseDown: (mouseEvent) => {
                        mouseEvent.preventDefault();
                        onChange({ eventName: event.name });
                        setQuery(event.name);
                        setListOpen(false);
                      },
                      role: "option",
                    },
                    h("code", null, event.name),
                    h("span", null, event.description),
                    event.pending && h("em", { className: "tn-picker__pending", title: `由便利貼登記(${event.addedFrom || ""}),還沒進 PM 埋點表` }, "待進 PM 表"),
                  ),
                ),
              ),
          ),
          selected
            ? h("span", { className: "tn-field__hint" }, `${selected.pending ? "便利貼登記(待 PM 進表)" : "埋點表"}:${selected.description}${selected.params ? `;參數 ${selected.params}` : ""}`)
            : h("span", { className: "tn-field__hint" }, "找不到?可能是新的行為,切到「新埋點」。"),
        ),
      fields.kind === "new" &&
        field(
          "事件名稱(選填)",
          h("input", {
            className: "tn-input tn-input--mono",
            onChange: (event) => onChange({ eventName: event.target.value }),
            placeholder: "留空 → 由 Claude 依命名規範命名",
            value: fields.eventName,
          }),
          duplicate
            ? `⚠ 「${duplicate.name}」已經在事件清單裡(${duplicate.module || "—"};${duplicate.pending ? "由別的便利貼登記、還沒進 PM 表" : "PM 埋點表"})。存檔時會自動改成「既有埋點」。`
            : "規範:前綴_名稱_動作,例 SWG_InvitePopup_showed——前綴 3 個大寫字母(頁面／功能)、名稱每個詞首字大寫、動作小寫過去式(clicked／entered／showed／closed)。",
        ),
      isEvent &&
        field(
          "參數(選填)",
          h("textarea", {
            className: "tn-input",
            onChange: (event) => onChange({ params: event.target.value }),
            placeholder: "例:from＝friendPage／notification",
            rows: 2,
            value: fields.params,
          }),
        ),
      field(
        isEvent ? "補充(選填)" : "說明",
        h("textarea", {
          autoFocus: !isEvent,
          className: "tn-input",
          onChange: (event) => onChange({ note: event.target.value }),
          placeholder: isEvent ? "還有什麼要跟工程說的" : "寫下這裡的互動方式或補充",
          rows: 3,
          value: fields.note,
        }),
      ),
      h(
        "div",
        { className: "tn-row" },
        field(
          "作者",
          h("input", {
            className: "tn-input",
            onChange: (event) => onChange({ author: event.target.value }),
            placeholder: "你的名字或團隊",
            value: fields.author,
          }),
        ),
        h(
          "label",
          { className: "tn-card__status tn-card__status--form" },
          h("input", {
            checked: fields.status === "confirmed",
            onChange: (event) => onChange({ status: event.target.checked ? "confirmed" : "open" }),
            type: "checkbox",
          }),
          "已確認",
        ),
      ),
      h(
        "div",
        { className: "tn-card__actions" },
        h("button", { className: "tn-btn tn-btn--ghost", onClick: onCancel, type: "button" }, "取消"),
        h("button", { className: "tn-btn tn-btn--primary", disabled: busy, type: "submit" }, busy ? "存檔中…" : "存檔"),
      ),
    ),
  );
}

/* ------------------------------------------------------------------ */
/* 右下角的啟動列                                                          */
/* ------------------------------------------------------------------ */

function Launcher({ armed, count, fileName, notes, onArm, onCollapseAll, onExpandAll, onFocus, onTogglePanel, panelOpen, writable }) {
  return h(
    "div",
    { className: "tn-launcher" },
    panelOpen &&
      h(
        "section",
        { className: "tn-panel", "aria-label": "這一頁的便利貼" },
        h(
          "header",
          { className: "tn-panel__head" },
          h("strong", null, `這一頁的便利貼(${count})`),
          h(
            "span",
            { className: "tn-panel__tools" },
            h("button", { className: "tn-btn tn-btn--ghost", onClick: onExpandAll, type: "button" }, "全部展開"),
            h("button", { className: "tn-btn tn-btn--ghost", onClick: onCollapseAll, type: "button" }, "全部收合"),
          ),
        ),
        count === 0
          ? h("p", { className: "tn-panel__empty" }, writable ? "還沒有便利貼。按「＋ 新增便利貼」,再點畫面上的位置。" : "這一頁還沒有便利貼。")
          : h(
              "ol",
              { className: "tn-panel__list" },
              notes.map((note, index) =>
                h(
                  "li",
                  { key: note.id },
                  h(
                    "button",
                    { className: "tn-panel__item", onClick: () => onFocus(note), type: "button" },
                    h("span", { className: `tn-pin tn-pin--static tn-pin--${note.kind}${note.status === "confirmed" ? " tn-pin--confirmed" : ""}` }, index + 1),
                    h(
                      "span",
                      { className: "tn-panel__text" },
                      h("span", { className: "tn-panel__kind" }, KIND_LABEL[note.kind] ?? note.kind),
                      h("span", null, note.eventName || note.trigger || note.note || "(空白)"),
                    ),
                  ),
                ),
              ),
            ),
        h(
          "footer",
          { className: "tn-panel__foot" },
          writable
            ? h(Fragment, null, "存在倉庫 ", h("code", null, `design-system/tracking-notes/${fileName || "…"}`), ";總表 ", h("code", null, "INDEX.md"), "。")
            : "唯讀:這是靜態版 Storybook,只有設計師電腦上的 Storybook 才能新增或修改。",
        ),
      ),
    h(
      "div",
      { className: "tn-launcher__bar" },
      h(
        "button",
        { "aria-expanded": panelOpen, className: `tn-btn tn-btn--bar${panelOpen ? " is-active" : ""}`, onClick: onTogglePanel, type: "button" },
        "便利貼 ",
        h("span", { className: "tn-badge" }, count),
      ),
      writable &&
        h(
          "button",
          { className: `tn-btn tn-btn--bar tn-btn--add${armed ? " is-active" : ""}`, onClick: onArm, type: "button" },
          armed ? "取消新增" : "＋ 新增便利貼",
        ),
    ),
  );
}

/* ------------------------------------------------------------------ */
/* Storybook 掛載點                                                       */
/* ------------------------------------------------------------------ */

/* 便利貼不放在 story 的 React 樹裡,而是自己開一個 root 掛在 body 上:
   其他 decorator(例如 Prototype 檢視器的 UI Flow、流程走查模式)會整棵換掉 story 的內容,
   放在樹裡會跟著被丟掉。這裡只在每次 story 渲染時把最新的 context 交給它。 */
let trackingNotesRoot = null;
let trackingNotesQueued = false;
let latestContext = null;

function mountTrackingNotes(context) {
  latestContext = context;
  if (trackingNotesQueued) return;
  trackingNotesQueued = true;
  queueMicrotask(() => {
    trackingNotesQueued = false;
    if (!trackingNotesRoot) {
      const container = document.createElement("div");
      container.setAttribute("data-tn-root", "");
      document.body.appendChild(container);
      trackingNotesRoot = createRoot(container);
    }
    trackingNotesRoot.render(
      latestContext && latestContext.viewMode !== "docs" ? h(TrackingNotes, { context: latestContext }) : null,
    );
  });
}

/* 用 beforeEach 而不是 decorator 掛載:外層 decorator(UI Flow、流程走查模式)不呼叫 Story 時,
   內層 decorator 根本不會被執行;beforeEach 每次渲染 story(含 globals 改變)都會跑。 */
export const beforeEach = (context) => {
  mountTrackingNotes(context);
};

export const decorators = [
  (Story, context) => {
    mountTrackingNotes(context);
    return h(Story);
  },
];

export const globalTypes = {
  [GLOBAL_NAME]: { description: "埋點便利貼:show／hide" },
};

export const initialGlobals = {
  [GLOBAL_NAME]: "show",
};
