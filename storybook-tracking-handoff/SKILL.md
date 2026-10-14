---
name: storybook-tracking-handoff
description: >-
  把埋點（tracking／analytics event）做成 Storybook 交付包的一部分：以 PM 的既有埋點清單為唯一事件定義來源，把「觸發點 ↔ 事件名 ↔ 參數值」掛在原型 flow metadata 的 trigger id 上，寫進 FLOW_SPEC 的轉場表埋點欄與 PRODUCTION_HANDOFF 的埋點節，讓流程圖的邊線顯示事件名，並以 lint_tracking.py 持續看住兩邊不脫鉤。**請務必在以下情境啟用此 Skill**：使用者提到「交付文件要有埋點」「埋點跟著 UI flow」「幫原型加埋點」「埋點欄」「tracking 進 handoff」「埋點檢查」「埋點清單比對」「從既有埋點表歸納命名規範／模組代碼表」，或已有 storybook-product-prototype 產出的原型、想讓埋點資訊跟 design token 一樣隨交付包給前端工程時。本 Skill 處理「Storybook 原型與交付文件」這一側；若要把埋點卡與連接線畫進 Figma 設計稿，那是 Figma 埋點標注 skill（如 invoicemanager-event）的範圍，兩者共用同一份 app 命名規範檔。本 Skill 不發明事件名、不修改既有事件、不代替 PM 決定要埋什麼。
---

# Storybook 埋點交付

## 這個 Skill 在做什麼

輸入是三樣既有的東西加一份決定：

1. **原型的 flow metadata**（`*Flow.ts`，storybook-product-prototype 的產物）—— 每條轉場有固定 `trigger` id
2. **該 app 的既有埋點清單**（PM 維護，通常是 Google Sheet）—— 事件定義的唯一來源
3. **該 app 的命名規範檔**（沒有就先跑 `references/module-table.md` 的歸納程序產一份草案）
4. **PM 對這一案的裁決**（要埋哪些、沿用哪些）

輸出是四樣，全部長在既有的交付包裡，不另開新包：

1. flow metadata 的 `tracking` / `trackingParams` 欄位（掛在 trigger 上）
2. `FLOW_SPEC.md` 轉場表的**埋點欄** + **§ 埋點** 一節
3. `PRODUCTION_HANDOFF.md` 的 **§ 埋點** 一節（工程實際讀的那份）
4. `lint_tracking.py` 接進目標 repo 的 npm script 與 pre-commit —— 讓以上三者永遠對得上

## 硬規則（違反任何一條就是做錯了）

- **不發明事件名。** 事件名只有兩個來源：既有清單（沿用），或 PM 依規範命名的新事件。
- **既有一律沿用，新增才套規範。** 分界不在「這次改版動了多少」，而在「需不需要一個新的事件名」。行為搬家（換元件、換位置）但語意不變 → 沿用，歷史數據才接得起來。
- **repo 只存對應關係**（trigger ↔ 事件名 ↔ 這條路送的參數值）。事件的完整定義（計算條件、全部參數）留在 PM 的清單 —— 複製一份進 repo 就會分岔。
- **埋點掛在 trigger id 上，不掛在元件上。** 同一顆元件在不同位置是不同行為；trigger 是程式在用的契約，改文案改版面不會脫鉤。
- **每條轉場都要有裁決。** `不埋` 與 `—`（非使用者操作）是裁決，空白不是。
- 通用發送規則見 `references/tracking-rules.md`，寫文件時逐條對照。

## 前置確認

開工前確認四樣輸入，缺哪樣就問，不要猜：

- 目標 repo 是否有 `src/prototypes/<案名>/`、`*Flow.ts`、`docs/FLOW_SPEC.md` 與 `docs/PRODUCTION_HANDOFF.md`（storybook-product-prototype 的結構）。沒有原型就沒有可掛的 trigger —— 這個 skill 幫不上，Figma 稿那側請用 Figma 埋點標注 skill。
- 既有埋點清單怎麼拿。Google Sheet 公開連結可直接抓 CSV，指令在 `references/module-table.md`。
- 命名規範檔在哪。**發票載具**：用該 app 自己的《埋點命名規範》。**沒有規範的 app**：先跑 `references/module-table.md` 歸納一份草案給 PM 確認。
- 這一案 PM 的裁決。沒有的話，先做出「觸發點 × 既有事件」比對表給 PM 勾，**建議欄與裁決欄分開**，AI 只填建議欄。

## 執行流程

依序走六步，細節與文件範本在 `references/workflow.md`。

1. **假設先行。** 這一案上線後要回答什�麼問題？回答不了任何問題的 event 不埋。**不要掃元件長 event** —— 那會埋一堆沒人看的點，還漏掉畫面上沒有的（後端事件、A/B 分組）。
2. **比對。** PM 清單 ↔ flow triggers，分四類：沿用／既有加參數／新事件／不埋。**埋點找不到可掛的 trigger 時，先懷疑流程表漏了一條轉場** —— 行為存在但沒畫出來，是這個比對最常照出的缺口，補轉場而不是硬掛。
3. **寫進三處。** flow metadata（`tracking`／`trackingParams` 選填欄位，型別裡加）、FLOW_SPEC（埋點欄 + § 埋點）、PRODUCTION_HANDOFF（§ 埋點）。格式範本照抄 `references/workflow.md`，欄名 `Trigger` 與 `埋點` 是機器讀的契約，不可翻譯。
4. **流程圖。** 若專案的流程圖（StaticFlow story／Prototype Inspector）支援在邊線顯示事件名，加上去之後**必須渲染並量測邊界框**，與改動前基準比對重疊數 —— 標籤變高變寬都可能壓到鄰居，肉眼看不出來。專案有幾個輸出面就全部檢查，不要只改一張。
5. **接檢查。** 把 `scripts/lint_tracking.py` 複製進目標 repo 的 `tools/`，接 npm script（`ds:tracking`）與 pre-commit。**逐條刻意破壞驗證會咬人**之後才算接好 —— 一個永遠通過的檢查等於沒有檢查。
6. **變更通知。** 任何已送出的文件事後被更正（規則改了、事件改了），產一段可直接貼給工程的變更通知，說清楚**哪條規則變了、埋點有沒有受影響**。只改檔案不通知，拿到舊版的人不會知道。

## 收尾自檢

- [ ] 每個埋的 event 都回答得了一個具體問題；每條轉場都有裁決（埋／不埋／—）。
- [ ] 事件名全部來自既有清單或 PM 命名，沒有任何一個是這裡發明的。
- [ ] 同一事件從不同路徑送不同參數值時，每條路的值都寫在對應的 trigger 上。
- [ ] `lint_tracking.py --strict` 綠燈，且破壞測試證實七條規則都會咬人。
- [ ] 流程圖每個輸出面都改到，且量測後重疊數不多於基準。
- [ ] 系統自動行為（App 重開還原、背景同步）預設不送；要送的都有 PM 裁決並以參數標明來源。
- [ ] 需要通知的變更都有通知稿。

## 參考檔案

- `references/tracking-rules.md` —— 共用規則：三段式命名、動詞表、參數規則、發送規則、沿用政策。跨 app 一致，改動需事業群層級同意。
- `references/module-table.md` —— 模式 A：從既有埋點表歸納一個 app 的模組代碼表與問題清單。每個 app 跑一次。
- `references/workflow.md` —— 模式 B：逐案流程、比對四類、FLOW_SPEC 與 HANDOFF 的文件範本原文。
- `scripts/lint_tracking.py` —— 防脫鉤檢查（範本；複製進目標 repo 的 `tools/` 使用，CI 讀不到 skill 目錄）。
