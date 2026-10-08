# 把 Figma 上的埋點便利貼匯進 Storybook

PM 若已在 Figma 的 UI Flow 版面貼了埋點便利貼，可以整批轉成 Storybook 便利貼，貼在流程走查對應那一步的觸發元素上。2026-10-01 在發票載具專案做過一次（30 張、10 條流程）。

## 步驟

1. **讀 Figma**：用 Figma MCP `get_screenshot`（maxDimension 開大，例如 12634）下載整個版面，再用 `sips` 裁區塊逐張讀便利貼文字；或用 `get_metadata` 列出便利貼節點。Figma 便利貼顏色慣例：綠＝新埋點、灰＝既有埋點、黃＝埋點異動（轉成 kind `existing` ＋ note「埋點異動：…」）、粉／藍＝共用埋點（兩個入口同一事件）。
2. **對位**：在瀏覽器開流程走查 story，用 JS 量每個目標元素在 `[data-flow-step] .ds-flow-storyboard__frame` 內的相對位置（xRatio／yRatio），同時記下步驟代號 `flowStep` 與元素文字 `target`。
3. **寫入**：對 Storybook 開發伺服器 `POST /__tracking_notes/notes`，body 含 `story: { id: "flow-<流程代號>", title, name }`、`flowStep`、`pin: { xRatio, yRatio }`、`target`、`kind`、`trigger`、`eventName`、`params`、`note`、`author`、`status`。由伺服器寫檔並重產 INDEX。
4. **標來源**：`status` 設 `confirmed`、`author` 寫「PM（Figma 埋點便利貼）」、`note` 尾巴加「來源：Figma 埋點便利貼 YYYY-MM-DD」。
5. **同步事件清單**：新事件名加進 `design-system/tracking-events/<app>.json`，`source` 標 `figma-tracking-board-<日期>`。
6. **commit**：便利貼檔名含中文時 `git config core.quotePath false`，否則 replay 腳本會看到跳脫字元。

## 注意

- 只有 `storybook dev` 能寫；靜態版唯讀。
- 不要發明事件名；Figma 便利貼上沒寫名字的，留空交給命名規則處理，並在 note 註明。
- 匯入前先確認流程走查的步驟代號沒改過，不然 `flowStep` 對不上、便利貼會留在檔裡但畫面不顯示。
