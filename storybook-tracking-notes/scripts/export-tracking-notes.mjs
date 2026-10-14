#!/usr/bin/env node
// 把屬於「這次交付」的便利貼篩出來，產一份快照 docs/TRACKING_NOTES.md 放進交付資料夾（工程打開資料夾就看得到這次的埋點）。
// 來源永遠是 design-system/tracking-notes/（全 App 一份，不搬）；快照是產生的，不手改。
// 用法：node scripts/export-tracking-notes.mjs <交付資料夾> [--check]
//   --check：不寫檔，只比對現有快照是否過期（交付前檢查用；過期回傳 1）
// 交付資料夾的 handoff-preflight.json 要有：
//   "trackingNotes": { "match": ["好友功能", "^Pages/(好友頁|個人頁)"], "cards": ["^friends:"], "output": "docs/TRACKING_NOTES.md" }
//   match＝比對便利貼檔 story.title 的正則（任一符合就算這次的）；cards＝全 App 流程圖那一份裡，flowStep（卡 id）符合的才算；output 省略＝docs/TRACKING_NOTES.md
import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const check = args.includes("--check");
const folderArg = args.find((a) => !a.startsWith("--"));
if (!folderArg) {
  console.error("用法：node scripts/export-tracking-notes.mjs <交付資料夾> [--check]");
  process.exit(2);
}
const folder = resolve(folderArg);
const cfgPath = join(folder, "handoff-preflight.json");
if (!existsSync(cfgPath)) {
  console.error(`找不到 ${cfgPath}`);
  process.exit(2);
}
const cfg = JSON.parse(readFileSync(cfgPath, "utf8"));
const tn = cfg.trackingNotes;
if (!tn || !Array.isArray(tn.match) || tn.match.length === 0) {
  console.error("handoff-preflight.json 沒有 trackingNotes.match，不知道哪些便利貼算這次的。");
  process.exit(2);
}
const patterns = tn.match.map((m) => new RegExp(m));
/* 全 App 流程圖的便利貼都存在同一份（story.title＝總覽/UI Flow），用 flowStep（卡的 id）再篩一次：cards＝正則，例 ["^friends:"] */
const cardPatterns = Array.isArray(tn.cards) ? tn.cards.map((m) => new RegExp(m)) : [];
const outPath = join(folder, tn.output ?? "docs/TRACKING_NOTES.md");
const notesDir = resolve(appDir, "design-system/tracking-notes");
const eventsFile = resolve(appDir, "design-system/tracking-events/invoice-manager.json");
const events = existsSync(eventsFile) ? JSON.parse(readFileSync(eventsFile, "utf8")).events ?? [] : [];
const eventByName = new Map(events.map((e) => [e.name, e]));

const KIND = { existing: "既有埋點", new: "新埋點", interaction: "互動說明", info: "補充資訊" };
const cell = (v) => String(v ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, "<br>") || "—";
const listState = (note) => {
  if (!note.eventName) return note.kind === "new" ? "待命名" : "—";
  const hit = eventByName.get(String(note.eventName).trim());
  if (!hit) return "不在事件清單";
  if (hit.pending) return "已登記，待 PM 進表";
  return "已在 PM 埋點表";
};

const files = readdirSync(notesDir).filter((n) => n.endsWith(".json")).sort();
const picked = [];
for (const name of files) {
  const data = JSON.parse(readFileSync(join(notesDir, name), "utf8"));
  const title = String(data.story?.title ?? "");
  if (!Array.isArray(data.notes)) continue;
  let notes = data.notes;
  if (!patterns.some((re) => re.test(title))) {
    if (cardPatterns.length === 0) continue;
    notes = notes.filter((n) => typeof n.flowStep === "string" && cardPatterns.some((re) => re.test(n.flowStep)));
  }
  if (notes.length === 0) continue;
  picked.push({ name, data: { ...data, notes } });
}
const total = picked.reduce((n, f) => n + f.data.notes.length, 0);
const pendingNames = new Set();
const eventNames = new Set();
for (const f of picked) for (const n of f.data.notes) if (n.eventName) { eventNames.add(n.eventName); if (eventByName.get(n.eventName)?.pending) pendingNames.add(n.eventName); }

const body = [];
body.push(`# ${cfg.name ?? folder.split("/").pop()}：埋點便利貼快照`, "");
body.push("> 這份是從 `design-system/tracking-notes/` 自動篩出來的快照，**不要手改**；要改內容回 Storybook 改那張便利貼，再跑 `node scripts/export-tracking-notes.mjs <交付資料夾>`。交付前檢查會核對它有沒有過期。", "");
body.push(`- 便利貼：${total} 張（${picked.length} 條流程／畫面）`);
body.push(`- 事件：${eventNames.size} 個；其中 ${pendingNames.size} 個已登記在 Storybook 事件清單、還沒進 PM 埋點表${pendingNames.size ? "：" + [...pendingNames].map((n) => `\`${n}\``).join("、") : ""}`);
body.push("- 「既有／新」以全 App 一份事件清單為準：新埋點＝這次交付負責實作、PM 進表；既有埋點＝沿用原名，只是多一個觸發點。", "");
for (const { name, data } of picked) {
  body.push(`## ${data.story?.title ?? ""} / ${data.story?.name ?? ""}`, "");
  body.push(`- 來源：\`design-system/tracking-notes/${name}\``, "");
  body.push("| # | 類型 | 畫面 | 點的位置 | 觸發行為 | 事件名稱 | 參數 | 補充 | 狀態 | 事件清單 |");
  body.push("|---|---|---|---|---|---|---|---|---|---|");
  data.notes.forEach((n, i) => {
    body.push(`| ${i + 1} | ${KIND[n.kind] ?? n.kind} | ${cell(n.screen)} | ${cell(n.target?.label)} | ${cell(n.trigger)} | ${n.eventName ? `\`${n.eventName}\`` : n.kind === "new" ? "（待命名）" : "—"} | ${cell(n.params)} | ${cell(n.note)} | ${n.status === "confirmed" ? "已確認" : "待確認"} | ${listState(n)} |`);
  });
  body.push("");
}
if (picked.length === 0) body.push("（這次交付還沒有任何便利貼。）", "");
const content = body.join("\n") + "\n";

if (check) {
  const current = existsSync(outPath) ? readFileSync(outPath, "utf8") : null;
  if (current === content) {
    console.log(`快照是最新的：${outPath}（${total} 張）`);
    process.exit(0);
  }
  console.error(current === null ? `還沒有快照：${outPath}` : `快照過期：${outPath}`);
  console.error(`請跑：node scripts/export-tracking-notes.mjs ${folderArg}`);
  process.exit(1);
}
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, content, "utf8");
console.log(`已寫入 ${outPath}：${total} 張便利貼、${eventNames.size} 個事件、${pendingNames.size} 個待 PM 進表`);
