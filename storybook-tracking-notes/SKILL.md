---
name: storybook-tracking-notes
description: >-
  Storybook「埋點便利貼」：讓 PM、設計師、工程直接在 Storybook 的 story 畫面或流程走查上貼便利貼（既有埋點／新埋點／互動說明／補充資訊），存成倉庫裡的 JSON ＋ 自動彙整的 INDEX.md，Claude 讀得到、跟著版本走。本 Skill 含可複製的 addon 原始碼、安裝步驟、資料格式、Claude 讀取與回填規則、群組改名時的維護腳本、Figma 便利貼匯入做法。**請在以下情境啟用**：使用者提到「便利貼」「埋點便利貼」「tracking notes」「PM 在 Storybook 貼註解」「讀便利貼」「幫便利貼命名」「便利貼 INDEX」「把 Figma 便利貼搬進 Storybook」「新專案也要有便利貼」「改了 Storybook 群組名便利貼要跟著改」。與 storybook-tracking-handoff 的分工：那個 skill 負責把埋點寫進 FLOW_SPEC／PRODUCTION_HANDOFF 交付文件；本 Skill 負責便利貼本身（收集、儲存、讀取、維護）。本 Skill 不發明事件名、不改既有事件、不替 PM 決定要埋什麼。
---

# Storybook 埋點便利貼（Tracking Notes）

## 這是什麼

一個自製的 Storybook addon（外掛）。每個 story 畫面右下角有「＋ 新增便利貼」，點畫面上的位置就貼一張綠色便利貼，功能對應 Figma 的埋點便利貼，但存在倉庫裡：

- 一般 story：`design-system/tracking-notes/<storyId>.json`
- 流程走查（一步一格的看板）：`design-system/tracking-notes/flow-<流程代號>.json`，一條流程一份，不管從哪個入口進去貼的都存同一份
- 截圖：`captures/<noteId>.webp`
- 總表：`INDEX.md`，每次存檔自動重產。**Claude 要看全部便利貼先讀這份。**
- 全 App 流程圖（總覽／UI Flow，2026-10-13 起也是工具列「UI Flow」看到的那張）也是一個便利貼看板：`data-flow-board="overall"`，每張頁面卡、狀態卡都是一步；在上面貼的存 `flow-overall.json`。流程走查上貼過的便利貼會搬到對應的卡上顯示（唯讀，點綠色圓點看內容；縮圖裡沒有那個狀態的畫成空心、位置概略）。
- 事件清單 `design-system/tracking-events/<app>.json`：「既有埋點」下拉的來源；有名字的新埋點存檔時**自動登記**進來（`pending: true`＝還沒進 PM 表）。

只有設計師電腦上跑的 `storybook dev` 能寫（伺服器端在 `server.mjs`）；同一個網址進來的所有人都能看、能加。`storybook build` 的靜態版唯讀。工具列有「便利貼」按鈕可整頁隱藏；工具列切到 Prototype 檢視器的其他模式（UI Flow／Docs／Components／Data）時，外層的便利貼不顯示（UI Flow 嵌進來的流程圖有自己的一組）。

## 什麼時候用這個 Skill

| 情境 | 做法 |
|---|---|
| 要把便利貼讀進來寫文件、命名、回填 | 看「Claude 的處理方式」 |
| 新專案要裝便利貼 | 看「安裝到另一個 Storybook 專案」 |
| Storybook 群組改名、流程搬家 | 看「維護：改名與搬家」 |
| PM 在 Figma 貼了埋點便利貼要搬進來 | 讀 `references/figma-import.md` |
| 便利貼要進交付文件的埋點欄 | 先用本 Skill 讀，再交給 `storybook-tracking-handoff` |

## 一張便利貼的欄位

| 欄位 | 意思 |
|---|---|
| `kind` | `existing` 既有埋點（事件清單裡已有，沿用原名）／`new` 新埋點（貼的當下清單裡沒有；存檔後自動登記進事件清單並標 `pending`，之後別的功能就當既有埋點挑）／`interaction` 互動說明／`info` 補充資訊。基準是全 App 一份事件清單，不是某個功能 |
| `trigger` | 觸發行為，例：點「加好友」 |
| `eventName` | 事件名。既有埋點從 `design-system/tracking-events/<app>.json` 挑；新埋點可留空 ＝ 交給 Claude 依該專案的命名規則命名 |
| `params` | 參數，例：`from＝friendPage／notification` |
| `note` | 補充 |
| `author`、`status` | 誰貼的；`open` 待確認／`confirmed` 已確認 |
| `pin` | 在手機畫面外框裡的相對位置（0–1）。貼在流程走查上時以那一步的畫面框為基準 |
| `flowStep` | 流程走查的步驟代號；一般 story 沒有。步驟被刪時便利貼留在檔裡但不顯示 |
| `screen`、`target` | 貼的當下畫面標題、點到的元件文字 |
| `capture` | 截圖路徑 |

檔案結構：`{ version, story: { id, title, name }, notes: [ … ] }`。`story.title` 是貼的當下的 Storybook 標題，只給人看，不是查找鍵；查找鍵是檔名（流程代號或 story id）。

## Claude 的處理方式

1. 先讀 `INDEX.md` 拿全貌，再依需要開個別 JSON 與截圖。
2. `kind: new` 且 `eventName` 空白：依**該專案**的命名規則提名字（規則檔在 `design-system/tracking-events/README.md`，範例見 `references/naming-rule-example.md`；不同 App 規則不同，不要套別的專案的），回填到便利貼：用 `PATCH /__tracking_notes/notes/<storyId>/<noteId>`，或直接改 JSON 再跑 `scripts/rebuild_index.mjs`。
3. `kind: existing` 一律沿用，不改名。
4. 有名字的新埋點會由 server 自動登記進事件清單（`syncTrackingEventsFromNotes`）；「新埋點」填了清單裡已有的名字會在存檔時自動改成既有埋點，「既有埋點」手打了清單裡沒有的名字會自動改成新埋點。PM 的上游表更新後重新匯入，同名覆蓋、`pending` 消失。手動同步：`node scripts/sync-tracking-events.mjs`（複本在本 skill 的 `scripts/`）。「既有／新」的基準是**全 App 一份事件清單**，不是某個功能：A 功能第一次用到＝新（A 的交付負責實作、PM 進表），B 功能再用到＝既有；便利貼記的是貼的當下，不回頭改，INDEX 會補標現況。
5. `status: open` 是 PM 還沒拍板的，寫進文件時標「待確認」。
6. 寫進交付文件（FLOW_SPEC 轉場表埋點欄、PRODUCTION_HANDOFF 埋點節）由 `storybook-tracking-handoff` 接手。
7. commit 時只加便利貼相關路徑（`design-system/tracking-notes/`、`tracking-events/`），不混進別的工作。檔名含中文要先 `git config core.quotePath false`。

## 安裝到另一個 Storybook 專案

前提：Storybook 9、React、Vite builder。

1. 把 `assets/addon/` 整個資料夾複製成專案的 `.storybook/tracking-notes/`。
2. `.storybook/main.ts`：
   - `addons` 加入 `resolve(process.cwd(), ".storybook/tracking-notes/preset.js")`
   - `viteFinal` 裡 `plugins.push(createTrackingNotesPlugin())`（從 `./tracking-notes/server.mjs` import）
   - `staticDirs` 要包含 `../design-system`，靜態版才讀得到 JSON
3. 改 `preview.js` 開頭兩個常數：`EVENTS_URL` 指向該專案的既有埋點清單（`/tracking-events/<app>.json`）；`ANCHOR_SELECTORS` 第一個換成該專案手機預覽外框的 class。
4. 建 `design-system/tracking-notes/`，把 `assets/README.template.md` 複製進去當 README，把專案名稱、流程代號檔案位置改掉。
5. 事件清單：`design-system/tracking-events/<app>.json`，格式 `{ events: [ { name, description, params, module, source } ] }`；可用 `POST /__tracking_notes/import-events` 匯入 TSV，或直接寫檔。沒有清單也能用，只是「既有埋點」下拉會是空的。路徑不是預設的 `invoice-manager.json` 時，`createTrackingNotesPlugin({ eventsFile: "design-system/tracking-events/<app>.json" })`。
5b. 把本 skill `scripts/sync-tracking-events.mjs` 複製到專案的 `scripts/`（它 import `../.storybook/tracking-notes/server.mjs`）；封存／交付前跑一次，會列出還沒進 PM 表的事件。
6. 相依套件：`html-to-image`（截圖）、`@storybook/icons`。
7. 啟動後確認：畫面右下角有「＋ 新增便利貼」，工具列有「便利貼」按鈕，`GET /__tracking_notes/status` 回 200。

## 交付資料夾的快照（2026-10-14 起）

便利貼與事件清單**不搬進交付資料夾**（全 App 一份是「既有／新」判斷的基準）。交付資料夾只放一份自動產生的快照 `docs/TRACKING_NOTES.md`：

```bash
node scripts/export-tracking-notes.mjs <交付資料夾>          # 產生／重產
node scripts/export-tracking-notes.mjs <交付資料夾> --check  # 只檢查有沒有過期（交付前檢查用）
```

- 交付資料夾的 `handoff-preflight.json` 加 `"trackingNotes": { "match": ["<需求名>", "^Pages/(頁名|頁名)"], "cards": ["^friends:"], "output": "docs/TRACKING_NOTES.md" }`：`match` 比對便利貼檔的 `story.title`；`cards` 給全 App 流程圖那一份用——它所有需求共用一個檔（`flow-overall.json`），用 `flowStep`（卡的 id，需求前綴開頭）篩出這次的。
- 快照欄位：類型、畫面、點的位置、觸發、事件名、參數、補充、狀態、事件清單狀態（已在 PM 表／已登記待進表／不在清單）。
- 腳本複本在本 skill `scripts/`，裝進專案 `scripts/`（它用 `../design-system/…` 找來源）。`handoff-preflight` skill 的第七類會核對快照是否過期；封存腳本依 `deliveryName` 自動重產。

## 維護：改名與搬家

- **改 Storybook 群組名**（例：`Prototypes/好友功能/` → `當次交付/2026-09_好友功能/`）：
  ```bash
  python3 scripts/retitle_notes.py <app>/design-system/tracking-notes "舊前綴/" "新前綴/"
  node scripts/rebuild_index.mjs <app>
  ```
  流程走查的檔只改標題；一般 story 的檔會連 story id 與檔名一起改（story id 是從標題算出來的）。改完到 Storybook 的 `index.json` 確認新 id 存在。
- **流程搬家**（例如交付結束併回總覽）：流程代號不變就不用動便利貼；代號變了要改檔名 `flow-<新代號>.json` 與 `story.id`。
- **步驟被刪或重排**：便利貼靠 `flowStep` 代號找步驟，代號不變就不受影響。

## 限制

- 不替 PM 決定要埋什麼；沒名字的新埋點才由 Claude 命名，且要回填讓 PM 看得到。
- 靜態版唯讀；PM 從區網貼的便利貼檔案落在設計師電腦，要由設計師 commit。
- 位置是相對比例，畫面改版太大時便利貼可能偏掉，以 `target` 文字與截圖為準。

## 版本紀錄

- 2026-10-14：便利貼貼在全 App 流程圖上（`flow-overall.json`，`flowStep`＝頁面卡／狀態卡 id）；舊的走查便利貼搬過去（`migratedFrom`）。交付資料夾放自動產生的快照 `docs/TRACKING_NOTES.md`（`export-tracking-notes.mjs`），交付前檢查核對過期。
- 2026-10-13：全 App 流程圖（UI Flow）當便利貼看板；工具列檢視器其他模式時外層便利貼不顯示；新埋點自動登記進事件清單（pending）、重複名字雙向自動修正、下拉標「待進 PM 表」、INDEX 補標現況；`scripts/sync-tracking-events.mjs`。
- 2026-10-07：全域 skill 建立；`retitle_notes.py`、`rebuild_index.mjs`；addon 支援 `data-flow-board-story-title`。
