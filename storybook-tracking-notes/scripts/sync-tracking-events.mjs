#!/usr/bin/env node
// 把便利貼裡有名字的「新埋點」登記進事件清單(design-system/tracking-events/invoice-manager.json),順便重產便利貼總表 INDEX.md。
// Storybook 每次存便利貼都會自動做同一件事;這支給手動或封存前跑。用法:node scripts/sync-tracking-events.mjs
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const app = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const server = await import(new URL("../.storybook/tracking-notes/server.mjs", import.meta.url).href);
const notesDir = resolve(app, server.defaultTrackingNotesDir);
const eventsFile = resolve(app, server.defaultTrackingEventsFile);
const result = await server.syncTrackingEventsFromNotes(notesDir, eventsFile);
await server.regenerateTrackingNotesIndex(notesDir, eventsFile);
console.log(`新登記 ${result.added.length} 筆:${result.added.join("、") || "—"}`);
console.log(`移除 ${result.removed.length} 筆:${result.removed.join("、") || "—"}`);
console.log(`待 PM 進表 ${result.pending.length} 筆:${result.pending.join("、") || "—"}`);
