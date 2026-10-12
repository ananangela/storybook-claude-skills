#!/usr/bin/env node
// 重產便利貼總表 INDEX.md。用法：node rebuild_index.mjs <storybook 專案的 app 目錄>
// 直接呼叫該專案 .storybook/tracking-notes/server.mjs 裡的 regenerateTrackingNotesIndex，確保格式與 Storybook 寫出來的一致。
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const appDir = resolve(process.argv[2] ?? ".");
const server = await import(pathToFileURL(resolve(appDir, ".storybook/tracking-notes/server.mjs")).href);
const dir = resolve(appDir, server.defaultTrackingNotesDir ?? "design-system/tracking-notes");
const eventsFile = server.defaultTrackingEventsFile ? resolve(appDir, server.defaultTrackingEventsFile) : null;
if (eventsFile && server.syncTrackingEventsFromNotes) {
  const result = await server.syncTrackingEventsFromNotes(dir, eventsFile);
  console.log(`事件清單：新登記 ${result.added.length}、移除 ${result.removed.length}、待 PM 進表 ${result.pending.length}`);
}
await server.regenerateTrackingNotesIndex(dir, eventsFile);
console.log(`INDEX.md 已重產：${dir}/INDEX.md`);
