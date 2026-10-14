---
name: handoff-preflight
description: 交付前檢查（handoff preflight）：推任何交付資料夾（PRD／FLOW_SPEC／UI_SPEC／DATA_SPEC／PRODUCTION_HANDOFF／ACCEPTANCE／IMPLEMENTATION_GUIDE ＋ Storybook 原型）到雲端之前一律先跑，未通過不得推。抓五類交付後才會被工程發現的問題：原型文案沒寫進文件、被取代的舊規則還留在程式或文件、畫面的失敗／空狀態／權限／排序／更新時機沒回答、「第 N 條」指到不存在或已取代的定案、交付版本紀錄落後。觸發詞：交付、推上去、交接、handoff、給工程、改了定案、取代、新功能交付資料夾。
---

# 交付前檢查（handoff-preflight）

2026-10-02 好友功能交付後，工程開發第一天提出約 57 個問題，其中一半以上可以在交付前擋下。這個 skill 把那次的五種根本原因變成每次交付前的固定關卡。

## 什麼時候跑

- **每一次**把交付資料夾（含 `docs/` 與原型）推到雲端之前。未通過不推。
- 改了任何定案、文案、原型行為之後，在 commit 之前。

```bash
python3 ~/.claude/skills/handoff-preflight/scripts/preflight.py <交付資料夾>
```

輸出 `[錯誤]` 必修；`[提醒]` 看過確認即可。exit code 0 才算通過。

## 五道關卡

| # | 關卡 | 擋什麼 | 自動或人工 |
|---|---|---|---|
| 1 | 文案同步 | 原型裡的 Toast、推播標題／內文、彈窗標題／內文，文件裡找不到（`${...}` 對到文件的 ○○、{暱稱}、N、XX） | 自動 |
| 2 | 舊規則殘留 | 已被取代的說法還留在程式、原型註解或文件裡 | 自動（清單要人維護，見下） |
| 3 | 狀態覆蓋 | UI_SPEC 的 State Coverage 表：每個 route 都要回答 成功回饋／動作失敗／載入失敗／空狀態／權限／排序／更新時機，不能空白 | 自動檢查表格完整；內容人工回答 |
| 4 | 定案引用 | 「第 N 條」指到不存在或已移到變更紀錄的定案；「Open Product Decisions 第 N 項」超出清單 | 自動 |
| 5 | 既有工具 | deliverable-doc-rules 五條規則、原型資料夾契約、交付版本紀錄沒落後、型別檢查、token | 自動（設定檔的 commands） |

## 三條工作規則（自動抓不到，靠自己守）

1. **改原型和改文件同一次完成。** 改了任何畫面行為或文案，同一個 commit 裡把七份文件提到同一件事的地方一起改；不留到交付前補。
2. **規則被取代時，全面搜尋一次並登記。** 新定案取代舊做法時：搜尋程式、註解、流程走查、七份文件裡的舊說法全部改掉，並把舊說法加進 `handoff-preflight.json` 的 `superseded`（`phrase` 用夠獨特的字串，`replacedBy` 寫取代它的定案）。之後舊說法被誰寫回來都會被擋。
3. **補文件章節時不自己編規則。** 為了滿足模板或驗證器補章節，查不到定案依據的句子一律放進人工審核清單（Open Product Decisions），不寫成聽起來合理的規則。State Coverage 表回答不出來的格子也一樣：寫「人工審核清單第 N 項」，並在清單補一項。

## 新功能第一次設定

在交付資料夾放 `handoff-preflight.json`（路徑都相對於交付資料夾）：

```json
{
  "name": "功能名稱",
  "repoRoot": "../../../../..",
  "docs": ["docs/PRD.md", "docs/FLOW_SPEC.md", "docs/UI_SPEC.md", "docs/DATA_SPEC.md", "docs/PRODUCTION_HANDOFF.md", "docs/ACCEPTANCE.md", "docs/IMPLEMENTATION_GUIDE.md"],
  "codeDirs": ["../功能程式資料夾", "."],
  "copy": {
    "dirs": ["../功能程式資料夾"],
    "calls": ["setToast"],
    "components": ["LockScreenPushStandIn", "Popup"],
    "ignore": ["原型", "（示意）"]
  },
  "superseded": [],
  "stateCoverage": {
    "doc": "docs/UI_SPEC.md",
    "heading": "State Coverage",
    "columns": ["畫面", "成功回饋", "動作失敗", "載入失敗", "空狀態", "權限", "排序", "更新時機"]
  },
  "decisions": { "doc": "docs/PRODUCTION_HANDOFF.md", "heading": "Decisions", "openHeading": "Open Product Decisions" },
  "commands": [
    { "name": "交付文件五條規則", "run": "python3 ~/.claude/skills/deliverable-doc-rules/scripts/check_doc.py <七份文件路徑>" },
    { "name": "原型資料夾契約", "run": "python3 ~/.claude/skills/storybook-product-prototype/scripts/validate_prototype.py <交付資料夾>" },
    { "name": "交付版本紀錄沒有落後", "run": "python3 ~/.claude/skills/storybook-product-prototype/scripts/validate_prototype.py <交付資料夾> --verify-manifest", "hint": "改過文件後重跑 --handoff-ready --changelog" },
    { "name": "型別檢查", "run": "npx tsc --noEmit", "cwd": "app" }
  ]
}
```

- `copy.components`：專案裡承載推播、彈窗文案的元件名稱；`ignore` 放原型專用、不會上線的提示（正規表示式）。
- UI_SPEC 要有 `## State Coverage` 表，第一欄用反引號寫 route id（可一列多個），每個 route 都要出現。
- 好友功能的設定可當範本：`app/src/pages/proposals/handoff/handoff-preflight.json`。

## 交付前的狀態清單（寫 State Coverage 時逐一回答）

- 每個會送出資料的按鈕：成功時畫面怎麼變、Toast 寫什麼；失敗時怎麼呈現、能不能重試、重試做什麼。
- 每個畫面：資料取不到時怎樣；第一次進入、0 筆時長怎樣；需要哪個系統權限、拒絕後怎樣。
- 每份清單：依什麼排序；處理過的列留在原位還是消失。
- 每份資料：什麼時候重新取（進入畫面、收到推播、從下一頁返回）。

## 第六類：有沒有登記進 Overall（2026-10-07 起）

交付時 Overall（`總覽/UI Flow`、`總覽/Prototype`）必須已含這個需求。設定檔加：

```json
"overall": { "registry": "../../../stories/overview/overallPrototypeFlow.ts", "tokens": ["<需求>PrototypeRoutes", "<需求>PrototypeTransitions"] }
```

檢查器確認合併檔有 import 這些名稱；沒有就擋下，提示到 `FEATURES` 加一筆（同一畫面在兩個需求各有 id 時補 `ALIASES`）。

## 第七類：埋點便利貼快照有沒有過期（2026-10-14 起）

便利貼與事件清單是全 App 一份（`design-system/tracking-notes/`、`tracking-events/`），不搬進交付資料夾；交付資料夾只放一份**自動產生的快照** `docs/TRACKING_NOTES.md`（這次功能的便利貼：畫面、觸發、事件名、參數、狀態、是否已進 PM 表）。

- `handoff-preflight.json` 加 `"trackingNotes": { "match": ["<需求名>", "^Pages/(頁名|頁名)"], "output": "docs/TRACKING_NOTES.md" }`；`match` 是比對便利貼檔 `story.title` 的正則。
- 檢查器跑 `node app/scripts/export-tracking-notes.mjs <交付資料夾> --check`，快照缺或過期就不通過；修法＝不帶 `--check` 跑一次重產。封存腳本會自動重產。
- 腳本複本在 `storybook-tracking-notes` skill 的 `scripts/`；路徑不同用 `trackingNotes.script` 指定（相對 repoRoot）。
