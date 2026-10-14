// 埋點便利貼的伺服器端:把便利貼寫進倉庫檔案。
//
// 只在 `storybook dev`(設計師電腦上的 Storybook)有作用;`storybook build`
// 出來的靜態版沒有這一段,那時便利貼是唯讀的,前端會改成直接讀
// staticDirs 送出來的同一批 JSON(design-system 是 staticDir,所以
// `design-system/tracking-notes/<story>.json` 會被當成 `/tracking-notes/<story>.json`)。
//
// 檔案:
//   design-system/tracking-notes/<storyId>.json   每個 story 一份,便利貼本體
//   design-system/tracking-notes/captures/*.webp  貼便利貼當下的畫面截圖
//   design-system/tracking-notes/INDEX.md         自動彙整的總表,給 PM／工程／Claude 讀
//   design-system/tracking-events/invoice-manager.json  事件清單;便利貼的新埋點會自動登記進來(pending＝還沒進 PM 表)
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

export const defaultTrackingNotesApiPath = "/__tracking_notes";
export const defaultTrackingNotesDir = "design-system/tracking-notes";
/** 事件清單(「既有埋點」下拉選單的來源;便利貼的新埋點會自動登記進來)。 */
export const defaultTrackingEventsFile = "design-system/tracking-events/invoice-manager.json";

export const TRACKING_NOTE_KINDS = ["existing", "new", "interaction", "info"];
export const TRACKING_NOTE_KIND_LABELS = {
  existing: "既有埋點",
  new: "新埋點",
  interaction: "互動說明",
  info: "補充資訊",
};
const STATUSES = ["open", "confirmed"];
const MAX_TEXT = 2000;
const MAX_SHORT = 200;
const MAX_REQUEST_BYTES = 3 * 1024 * 1024;
const MAX_CAPTURE_BYTES = 1.5 * 1024 * 1024;

class HttpError extends Error {
  constructor(message, statusCode) {
    super(message);
    this.statusCode = statusCode;
  }
}

/** story id 轉檔名:保留中英數、底線、連字號,其他一律換成連字號。 */
export function storyFileStem(storyId) {
  const stem = String(storyId ?? "")
    .replace(/[^\p{L}\p{N}_-]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 160);
  if (!stem) throw new HttpError("story id 不合法。", 400);
  return stem;
}

function text(value, max = MAX_TEXT) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

function ratio(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new HttpError("pin 座標不合法。", 400);
  return Math.min(1, Math.max(0, number));
}

function pickKind(value) {
  return TRACKING_NOTE_KINDS.includes(value) ? value : "info";
}

function pickStatus(value) {
  return STATUSES.includes(value) ? value : "open";
}

function normalizeStory(value) {
  if (!value || typeof value !== "object" || !text(value.id, MAX_SHORT)) {
    throw new HttpError("缺少 story 資訊。", 400);
  }
  return {
    id: text(value.id, MAX_SHORT),
    title: text(value.title, MAX_SHORT),
    name: text(value.name, MAX_SHORT),
  };
}

function normalizeFields(input, base = {}) {
  const source = input && typeof input === "object" ? input : {};
  const next = { ...base };
  if ("kind" in source) next.kind = pickKind(source.kind);
  if ("trigger" in source) next.trigger = text(source.trigger, MAX_SHORT);
  if ("eventName" in source) next.eventName = text(source.eventName, MAX_SHORT);
  if ("params" in source) next.params = text(source.params);
  if ("note" in source) next.note = text(source.note);
  if ("author" in source) next.author = text(source.author, 80);
  if ("status" in source) next.status = pickStatus(source.status);
  if ("screen" in source) next.screen = text(source.screen, MAX_SHORT);
  /* 流程走查看板:便利貼貼在哪一步(步驟代號)。位置比例以那一步的手機畫面框為基準。 */
  if ("flowStep" in source) next.flowStep = source.flowStep == null ? null : text(source.flowStep, 80);
  if ("pin" in source && source.pin && typeof source.pin === "object") {
    next.pin = { xRatio: ratio(source.pin.xRatio), yRatio: ratio(source.pin.yRatio) };
  }
  return next;
}

async function readJson(path, fallback) {
  if (!existsSync(path)) return fallback;
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return fallback;
  }
}

async function saveCapture(dir, noteId, dataUrl) {
  if (typeof dataUrl !== "string") return null;
  const match = /^data:image\/(webp|png|jpeg);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl);
  if (!match) return null;
  const buffer = Buffer.from(match[2], "base64");
  if (buffer.length === 0 || buffer.length > MAX_CAPTURE_BYTES) return null;
  const extension = match[1] === "jpeg" ? "jpg" : match[1];
  await mkdir(join(dir, "captures"), { recursive: true });
  const fileName = `${noteId}.${extension}`;
  await writeFile(join(dir, "captures", fileName), buffer);
  return `captures/${fileName}`;
}

function formatDate(iso) {
  return typeof iso === "string" ? iso.slice(0, 10) : "";
}

function cell(value) {
  return String(value ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, "<br>") || "—";
}

function eventPrefix(name) {
  const match = /^([A-Za-z0-9]+)_/.exec(name);
  return match ? match[1] : "";
}

/**
 * 便利貼裡有名字的「新埋點」自動登記進事件清單——之後任何功能貼便利貼時,
 * 下拉選單就挑得到它(當「既有埋點」),不用等 PM 把埋點表更新。
 *   - 清單裡已有同名的(不管來源)→ 不動。
 *   - 新登記的標 `pending: true`(＝還沒進 PM 的埋點表),`source` 記是哪張便利貼;
 *     之後從 PM 埋點表匯入時同名會被匯入的覆蓋,pending 自然消失。
 *   - 來源是便利貼、但那張便利貼已刪或改名 → 從清單移除(清單裡只留現況)。
 * 回傳 { added, removed, pending }(都是事件名陣列)。
 */
export async function syncTrackingEventsFromNotes(notesDir, eventsFile) {
  const data = await readJson(eventsFile, null);
  if (!data || !Array.isArray(data.events)) return { added: [], removed: [], pending: [] };
  const entries = (await readdir(notesDir).catch(() => [])).filter((name) => name.endsWith(".json")).sort();
  const fromNotes = new Map();
  for (const fileName of entries) {
    const file = await readJson(join(notesDir, fileName), null);
    if (!file || !Array.isArray(file.notes)) continue;
    const storyTitle = String(file.story?.title ?? "");
    const parts = storyTitle.split("/").map((part) => part.trim()).filter(Boolean);
    const group = parts.length > 1 ? parts[1] : parts[0] ?? "";
    for (const note of file.notes) {
      if (note.kind !== "new" || typeof note.eventName !== "string") continue;
      const name = note.eventName.trim();
      if (!name || fromNotes.has(name)) continue;
      fromNotes.set(name, {
        name,
        description: note.trigger || note.note || "",
        params: note.params || "",
        module: group || eventPrefix(name),
        source: `note:${fileName}#${note.id}`,
        pending: true,
        noteStatus: note.status ?? "open",
        addedFrom: storyTitle,
        addedAt: String(note.updatedAt || note.createdAt || "").slice(0, 10),
      });
    }
  }
  const byName = new Map(data.events.map((event) => [event.name, event]));
  const added = [];
  const removed = [];
  for (const [name, entry] of fromNotes) {
    const current = byName.get(name);
    if (!current) {
      byName.set(name, entry);
      added.push(name);
    } else if (typeof current.source === "string" && current.source.startsWith("note:")) {
      byName.set(name, { ...current, ...entry });
    }
  }
  for (const [name, event] of byName) {
    if (typeof event.source === "string" && event.source.startsWith("note:") && !fromNotes.has(name)) {
      byName.delete(name);
      removed.push(name);
    }
  }
  const events = [...byName.values()];
  const pending = events.filter((event) => event.pending).map((event) => event.name);
  if (JSON.stringify(events) !== JSON.stringify(data.events)) {
    data.events = events;
    data.updatedAt = new Date().toISOString().slice(0, 10);
    await writeFile(eventsFile, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  }
  return { added, removed, pending };
}

/** 重新產生 INDEX.md:一個 story 一節,每張便利貼一列。給 eventsFile 會順便標每個事件在事件清單裡的狀態。 */
export async function regenerateTrackingNotesIndex(dir, eventsFile = null) {
  const eventList = eventsFile ? (await readJson(eventsFile, null))?.events ?? [] : [];
  const eventByName = new Map((Array.isArray(eventList) ? eventList : []).map((event) => [event.name, event]));
  const pendingCount = [...eventByName.values()].filter((event) => event.pending).length;
  await mkdir(dir, { recursive: true });
  const entries = (await readdir(dir)).filter((name) => name.endsWith(".json")).sort();
  const files = [];
  for (const name of entries) {
    const data = await readJson(join(dir, name), null);
    if (data && Array.isArray(data.notes) && data.notes.length > 0) files.push({ name, data });
  }
  files.sort((a, b) =>
    `${a.data.story?.title}/${a.data.story?.name}`.localeCompare(
      `${b.data.story?.title}/${b.data.story?.name}`,
      "zh-Hant",
    ),
  );

  const total = files.reduce((sum, file) => sum + file.data.notes.length, 0);
  const confirmed = files.reduce(
    (sum, file) => sum + file.data.notes.filter((note) => note.status === "confirmed").length,
    0,
  );
  const lines = [
    "# 埋點便利貼總表",
    "",
    "> 這份檔案由 Storybook 的「埋點便利貼」自動產生,**不要手改**;要改內容請回 Storybook 改那張便利貼。",
    "> 資料來源是同目錄的 `*.json`(一個 story 一份),截圖在 `captures/`。",
    "",
    `- 便利貼總數:${total}(已確認 ${confirmed},待確認 ${total - confirmed})`,
    `- 最後更新:${new Date().toLocaleString("sv-SE").slice(0, 16)}`,
    ...(eventsFile ? [`- 新埋點已自動登記進事件清單、還沒進 PM 埋點表的:${pendingCount} 筆(事件清單裡 \`pending: true\` 的那些)`] : []),
    "",
    "類型說明:**既有埋點** ＝ 事件清單(tracking-events)裡已經有的事件,沿用原名;**新埋點** ＝ 貼的當下清單裡還沒有的事件,存檔後自動登記進清單,之後別的功能就當既有埋點挑(事件名稱空白代表交給 Claude 依命名規範命名);**互動說明** ＝ 說明這裡怎麼互動;**補充資訊** ＝ 其他要給工程的話。",
    "判斷基準是**全 App 一份事件清單**,不是某個功能:A 功能第一次用到＝新埋點(A 的交付負責實作、PM 進表),B 功能再用到＝既有埋點(只是多一個觸發點)。",
    "",
  ];

  for (const { name, data } of files) {
    const story = data.story ?? {};
    lines.push(`## ${story.title || "(未命名)"} / ${story.name || ""}`);
    lines.push("");
    lines.push(`- Story id:\`${story.id ?? ""}\` · 檔案:\`${name}\``);
    lines.push("");
    lines.push("| # | 類型 | 畫面 | 點的位置 | 觸發行為 | 事件名稱 | 參數 | 補充 | 作者 | 日期 | 狀態 | 截圖 |");
    lines.push("|---|---|---|---|---|---|---|---|---|---|---|---|");
    data.notes.forEach((note, index) => {
      const listed = note.eventName ? eventByName.get(String(note.eventName).trim()) : null;
      const listState = !note.eventName || !eventsFile
        ? ""
        : !listed
          ? "<br>(不在事件清單)"
          : listed.pending
            ? "<br>(已登記事件清單,待 PM 進表)"
            : note.kind === "new"
              ? "<br>(已在 PM 埋點表)"
              : "";
      const eventName = note.eventName
        ? `\`${note.eventName}\`${listState}`
        : note.kind === "new"
          ? "(待 Claude 命名)"
          : "—";
      lines.push(
        `| ${index + 1} | ${TRACKING_NOTE_KIND_LABELS[note.kind] ?? note.kind} | ${cell(note.screen)} | ${cell(note.target?.label)} | ${cell(note.trigger)} | ${eventName} | ${cell(note.params)} | ${cell(note.note)} | ${cell(note.author)} | ${formatDate(note.updatedAt || note.createdAt)} | ${note.status === "confirmed" ? "已確認" : "待確認"} | ${note.capture ? `[圖](${note.capture})` : "—"} |`,
      );
    });
    lines.push("");
  }

  if (files.length === 0) {
    lines.push("(目前還沒有任何便利貼。)", "");
  }

  await writeFile(join(dir, "INDEX.md"), `${lines.join("\n")}\n`, "utf8");
}

function sendJson(response, statusCode, payload) {
  response.statusCode = statusCode;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.end(JSON.stringify(payload));
}

async function readBody(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > MAX_REQUEST_BYTES) throw new HttpError("內容太大(超過 3 MB)。", 413);
    chunks.push(buffer);
  }
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    throw new HttpError("內容不是合法的 JSON。", 400);
  }
}

export function createTrackingNotesStore({ cwd = process.cwd(), dir = defaultTrackingNotesDir, eventsFile = defaultTrackingEventsFile } = {}) {
  const root = resolve(cwd, dir);
  const eventsPath = eventsFile ? resolve(cwd, eventsFile) : null;

  async function loadStory(storyId) {
    const stem = storyFileStem(storyId);
    const path = join(root, `${stem}.json`);
    const data = await readJson(path, { version: 1, story: { id: storyId }, notes: [] });
    if (!Array.isArray(data.notes)) data.notes = [];
    return { data, path, stem };
  }

  async function persist(path, data) {
    await mkdir(root, { recursive: true });
    await writeFile(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
    if (eventsPath) await syncTrackingEventsFromNotes(root, eventsPath).catch(() => {});
    await regenerateTrackingNotesIndex(root, eventsPath);
  }

  return {
    root,
    async list(storyId) {
      const { data, stem } = await loadStory(storyId);
      return { version: 1, file: `${stem}.json`, story: data.story, notes: data.notes };
    },
    async create(payload) {
      const story = normalizeStory(payload?.story);
      const { data, path, stem } = await loadStory(story.id);
      const now = new Date().toISOString();
      const id = randomUUID().slice(0, 8);
      const fields = normalizeFields(payload?.note, {
        kind: "info",
        trigger: "",
        eventName: "",
        params: "",
        note: "",
        author: "",
        status: "open",
        screen: "",
        pin: { xRatio: 0.5, yRatio: 0.5 },
      });
      if (!payload?.note?.pin) throw new HttpError("缺少 pin 座標。", 400);
      const rawAnchor = payload?.note?.anchor;
      const anchor =
        rawAnchor && typeof rawAnchor === "object"
          ? {
              selector: text(rawAnchor.selector, MAX_SHORT),
              cssWidth: Number(rawAnchor.cssWidth) || 0,
              cssHeight: Number(rawAnchor.cssHeight) || 0,
            }
          : null;
      const rawTarget = payload?.note?.target;
      const target =
        rawTarget && typeof rawTarget === "object"
          ? { tag: text(rawTarget.tag, 40), label: text(rawTarget.label, 80) }
          : null;
      const capture = await saveCapture(root, id, payload?.capture);
      const note = { id, ...fields, anchor, target, capture, createdAt: now, updatedAt: now };
      data.story = story;
      data.notes.push(note);
      await persist(path, data);
      return { note, file: `${stem}.json` };
    },
    async update(storyId, noteId, patch) {
      const { data, path } = await loadStory(storyId);
      const index = data.notes.findIndex((note) => note.id === noteId);
      if (index === -1) throw new HttpError("找不到這張便利貼。", 404);
      const current = data.notes[index];
      const next = { ...current, ...normalizeFields(patch, current), updatedAt: new Date().toISOString() };
      data.notes[index] = next;
      await persist(path, data);
      return { note: next };
    },
    async remove(storyId, noteId) {
      const { data, path } = await loadStory(storyId);
      const index = data.notes.findIndex((note) => note.id === noteId);
      if (index === -1) throw new HttpError("找不到這張便利貼。", 404);
      const [removed] = data.notes.splice(index, 1);
      if (removed.capture) {
        await rm(join(root, removed.capture), { force: true }).catch(() => {});
      }
      await persist(path, data);
      return { ok: true, id: noteId };
    },
  };
}

/** Vite plugin:掛在 main.ts 的 viteFinal。 */
export function createTrackingNotesPlugin(options = {}) {
  const apiPath = options.apiPath ?? defaultTrackingNotesApiPath;
  const store = createTrackingNotesStore({ cwd: options.cwd, dir: options.dir, eventsFile: options.eventsFile });

  async function handle(request, response) {
    const url = new URL(request.url ?? "/", "http://storybook.local");
    const pathname = url.pathname.startsWith(apiPath) ? url.pathname.slice(apiPath.length) : url.pathname;
    const segments = pathname.split("/").filter(Boolean).map((segment) => decodeURIComponent(segment));
    const method = request.method ?? "GET";

    if (segments[0] === "status" && method === "GET") {
      return sendJson(response, 200, { writable: true, dir: options.dir ?? defaultTrackingNotesDir });
    }
    // 從瀏覽器把 PM 埋點表的內容丟進來(text/plain POST 不用 CORS 預檢):存成 TSV,
    // 之後用 scripts/import-tracking-events.mjs 合併進 tracking-events/invoice-manager.json。
    if (segments[0] === "import-events" && method === "POST") {
      const sheet = text(url.searchParams.get("sheet") ?? "sheet", 60).replace(/[^\p{L}\p{N}_-]+/gu, "-") || "sheet";
      const chunks = [];
      let bytes = 0;
      for await (const chunk of request) {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        bytes += buffer.length;
        if (bytes > 5 * 1024 * 1024) throw new HttpError("內容太大(超過 5 MB)。", 413);
        chunks.push(buffer);
      }
      const importsDir = resolve(options.cwd ?? process.cwd(), "design-system/tracking-events/imports");
      await mkdir(importsDir, { recursive: true });
      const fileName = `${new Date().toISOString().slice(0, 10)}-${sheet}.tsv`;
      await writeFile(join(importsDir, fileName), Buffer.concat(chunks), "utf8");
      response.setHeader("Access-Control-Allow-Origin", "*");
      return sendJson(response, 201, { file: `design-system/tracking-events/imports/${fileName}`, bytes });
    }
    if (segments[0] === "notes") {
      if (segments.length === 1 && method === "GET") {
        const storyId = url.searchParams.get("story");
        if (!storyId) throw new HttpError("缺少 story 參數。", 400);
        return sendJson(response, 200, await store.list(storyId));
      }
      if (segments.length === 1 && method === "POST") {
        return sendJson(response, 201, await store.create(await readBody(request)));
      }
      if (segments.length === 3 && method === "PATCH") {
        return sendJson(response, 200, await store.update(segments[1], segments[2], await readBody(request)));
      }
      if (segments.length === 3 && method === "DELETE") {
        return sendJson(response, 200, await store.remove(segments[1], segments[2]));
      }
    }
    throw new HttpError("沒有這個路徑。", 404);
  }

  return {
    name: options.name ?? "ds-tracking-notes-api",
    configureServer(server) {
      server.middlewares.use(apiPath, (request, response) => {
        handle(request, response).catch((error) => {
          const statusCode = error instanceof HttpError ? error.statusCode : 500;
          sendJson(response, statusCode, {
            error: error instanceof Error ? error.message : "未知錯誤。",
          });
        });
      });
    },
  };
}
