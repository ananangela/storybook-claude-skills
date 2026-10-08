# 埋點便利貼（Tracking Notes）

Storybook 每個 story 畫面右下角的「＋ 新增便利貼」。PM、設計師、工程點畫面上的位置就能貼一張綠色便利貼，功能對應 Figma 上的埋點便利貼，但存在這個倉庫裡，所以 Claude 讀得到，也跟著版本走。

## 檔案

| 檔案 | 內容 |
|---|---|
| `<storyId>.json` | 一個 story 一份，裡面是這一頁的所有便利貼（程式寫入，不要手改） |
| `flow-<流程代號>.json` | 貼在「流程走查」看板上的便利貼，**一條流程一份**：不管是從側邊欄的流程走查、還是從任何一則畫面右上角 Prototype → 流程走查 進去貼的，都存在這裡、看到的都一樣。流程代號見 `src/pages/proposals/handoff/friendsStoryboardIndex.tsx` |
| `captures/<noteId>.webp` | 貼便利貼當下的手機畫面截圖，讀便利貼時對照用 |
| `INDEX.md` | 自動彙整的總表，每次存檔都重新產生。**要一眼看完全部便利貼就讀這份。** |

## 一張便利貼有什麼

| 欄位 | 意思 |
|---|---|
| `kind` | `existing` 既有埋點（沿用埋點表的事件）／`new` 新埋點／`interaction` 互動說明／`info` 補充資訊 |
| `trigger` | 觸發行為，例：點「加好友」 |
| `eventName` | 事件名稱。既有埋點從 `design-system/tracking-events/invoice-manager.json` 挑；新埋點可留空 ＝ **交給 Claude 依命名規範命名** |
| `params` | 參數，例：`from＝friendPage／notification` |
| `note` | 補充或說明 |
| `author`、`status` | 誰貼的；`open` 待確認／`confirmed` 已確認（卡片上的勾勾） |
| `pin` | 在手機畫面外框裡的相對位置（0–1），視窗大小改變也貼在同一處。貼在流程走查上時，是以**那一步的手機畫面框**為基準，流程多一步或縮放改了都不會跑掉 |
| `flowStep` | 貼在流程走查的哪一步（步驟代號）；一般 story 上的便利貼沒有這個欄位。那一步被刪掉時便利貼會留在檔裡但畫面上不顯示 |
| `screen`、`target` | 貼的當下畫面上的標題、點到的元件文字，讓人不看截圖也知道貼在哪。流程走查上會是「第 N 步・畫面名」 |
| `capture` | 截圖路徑 |

## 給 Claude 的處理方式

1. 先讀 `INDEX.md` 拿全貌，再依需要開個別 JSON 與截圖。
2. `kind: new` 且 `eventName` 空白的，依 PM 的《Firebase 事件命名規則》（見 `../tracking-events/README.md`：`前綴_名稱_動作`，例 `SWG_InvitePopup_showed`）提名字，**回填到便利貼**（PATCH 或直接改 JSON 再重跑索引），並在交付文件的互動與跳轉表寫上事件名。
3. `kind: existing` 一律沿用，不改名。
4. `status: open` 的是 PM 還沒拍板的，寫進文件時標「待確認」。

## 怎麼運作

- 便利貼的寫入由 Storybook 開發伺服器（`.storybook/tracking-notes/server.mjs`）處理，所以**只有設計師電腦上跑的 Storybook 能新增或修改**；同一個網址進來的所有人都能看、能加。
- `storybook build` 出來的靜態版沒有伺服器，便利貼變成唯讀（讀 staticDirs 送出的同一批 JSON）。
- 工具列上的「便利貼」按鈕可以整頁隱藏，截圖或審看畫面時用。
