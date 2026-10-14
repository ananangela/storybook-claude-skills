---
name: storybook-flow-storyboard
description: >-
  Storybook「流程走查」（Flow Storyboard）：一條流程照人實際操作的順序一步一格橫著排，每格是真的畫面元件停在那一步的狀態，格與格之間寫「做了什麼」；PM 在這裡貼埋點便利貼（便利貼跟流程存 flow-<代號>.json），右上角 Prototype 工具的「流程走查」模式與全 App 流程圖都讀同一份。本 Skill 含看板元件原始碼、步驟資料格式、三處登記方式（流程總表、側邊欄 story、prototype meta）、與全 App 流程圖的步驟↔畫面對照、檢查器。**請在以下情境啟用**：使用者提到「流程走查」「一步一格」「storyboard」「幫這個需求做流程走查」「這條流程走一遍」「PM 要在流程上貼埋點」「新需求（例如探索）還沒有流程走查」「流程走查的步驟代號」「便利貼貼在哪一步」。分工：節點圖（所有畫面與跳轉線）是 storybook-product-prototype 的 UI Flow 契約；便利貼本身是 storybook-tracking-notes；本 Skill 只管「一步一格」這一層。不自創畫面、不自創過場：每一格都必須是既有元件的某個起始狀態。
---

# Storybook 流程走查（Flow Storyboard）

## 這是什麼

2026-09-30 使用者定案：節點加箭頭的圖看不出一步一步的操作，PM 也沒辦法在圖上貼埋點。所以每一條流程另外做成「走查看板」：

- 一條流程一個看板，照人實際操作的順序一步一格橫著排，可以分成好幾列（例如「A 送出邀請」「B 對方接受」）。
- 每一格是**真的畫面元件**，用 `initial*`／`storyboard` 這類起始狀態停在那一步；不是截圖、不另外畫。看板把它鎖成不可操作。
- 格與格之間寫「做了什麼」（`action`），每格下面一句規則（`note`）。
- 左上角標這一步是誰的畫面：我／對方／系統畫面／小程序端。系統畫面與小程序端用虛線框（本次不含頁面設計）。
- 埋點便利貼貼在某一步的畫面上，存 `design-system/tracking-notes/flow-<流程代號>.json`，記「第幾步・哪個畫面、點了哪顆按鈕」。
- **2026-10-13 起走查併進 UI Flow**：全 App 流程圖把每一步畫成頁面卡底下的「狀態卡」（一條走查一列、照步驟順序、線接起來，卡上寫「做了什麼 → 變成什麼狀態」），右上角「流程走查清單」點一條就一步一步走（底部 ◀ ▶）。工具列的「流程走查」模式已拿掉（「UI Flow」就是它）；側邊欄的流程走查 story 已拿掉（`HandoffStoryboards.stories.tsx` 加 `tags: ["!dev"]`，資料照舊給 UI Flow 讀；要加回來就拿掉那行）。走查的資料檔、`id` 契約、便利貼檔名都不變——本 Skill 管的「一步一格」資料就是狀態卡與一步一步的來源。
- 步驟 ↔ 卡的對照在 `src/stories/overview/storyboardStepRoutes.ts`：`routeForScreen`（元件＋起始狀態 → 哪一頁）、`variantKey`（除了決定頁面的 props 外還帶狀態 props → 狀態卡）、`storyboardStepCards`（每一步對到頁面卡或狀態卡 id）。新元件要加進 `routeForScreen` 的 switch，不然那一步不會出現在圖上。

## 檔案（以好友功能為例，`app/src/pages/proposals/handoff/`）

| 檔案 | 內容 |
|---|---|
| `FlowStoryboard.tsx` ＋ `.css` | 看板元件（本 Skill `assets/` 有複本，新專案直接複製） |
| `<需求>Storyboards.tsx` | 每條流程的步驟：`export const xxx = (): FlowStoryboardBoard => ({ title, summary, rows })` |
| `<需求>StoryboardIndex.tsx` | 流程總表：`{ id, title, related, build }`，`id` 是契約（便利貼檔名用它，**不改**） |
| `HandoffStoryboards.stories.tsx` | 側邊欄的 story，一條流程一則，`args: board("<id>")` |
| `<需求>PrototypeMeta.ts` | `storyboards: <需求>PrototypeStoryboards`（Inspector 的流程走查模式讀這個） |
| `src/stories/overview/storyboardStepRoutes.ts` | 步驟 ↔ 全 App 流程圖的畫面（`routeForScreen`：元件＋起始狀態 → route id） |

## 一步的格式

```ts
{ id: "friends", title: "好友頁：邀請", action: "點「好友」列", actor: "me", note: "上方三顆入口、待回覆的好友邀請、你可能認識的人。", screen: <ProposalFlow initialScreen="friends" /> }
```

- `id`：這條流程內唯一、穩定；便利貼記它。改了代號等於便利貼掉了。
- `title`：畫面名稱，格式「畫面：狀態」。
- `action`：從上一步到這一步做了什麼；第一步可省略。寫法用「點「按鈕文字」」最好，全 App 流程圖能自動對到按鈕。
- `actor`：`me`（預設）／`other`（另一支手機）／`system`（作業系統或第三方 App）／`external`（小程序端）。
- `screen`：既有元件停在那一步。狀態要靠元件的 `initial*`／`storyboard` props；元件沒有那個起始狀態就先在元件加（那是原型的工作），不要用截圖或假畫面代替。
- 不自創過場：等待、處理中、動畫一律沿用現行 App（記憶 no-invented-transitions）。

## 建一條流程的步驟

1. 先讀該需求的 FLOW_SPEC 轉場表，列出這條流程經過的畫面與每一跳的觸發；一跳＝一格（判斷也可以是一格，用 `note` 寫條件）。
2. 在 `<需求>Storyboards.tsx` 寫 `export const <流程> = (): FlowStoryboardBoard => ({ title, summary, rows: [{ label?, steps: [...] }] })`。需要「對方的手機」時用另一組 fixtures（例如 `otherPhone`）。
3. 在 `<需求>StoryboardIndex.tsx` 加一筆 `{ id, title, related, build }`。`related` 寫這條流程會經過的 story title：寫到群組（`Pages/好友頁`）＝這一頁出現在流程裡；寫到某一則（`Pages/好友頁/完整流程：推播 → 好友頁`）＝那一則本身就是這條流程，Inspector 切到它時預設就畫。
4. 在 `HandoffStoryboards.stories.tsx` 加 `export const X: Story = { name: "<title>", args: board("<id>") }`。
5. `<需求>PrototypeMeta.ts` 的 `storyboards` 用 index 產生（`render: () => <FlowStoryboard {...buildStoryboard(entry)} />`），不用另外改。
6. 全 App 流程圖要能顯示這條流程的便利貼：到 `storyboardStepRoutes.ts` 的 `routeForScreen` 補這個需求的元件↔route 規則，並把 index 加進 `storyboardIds`。
7. 跑檢查器：`python3 scripts/check_storyboards.py <handoff 資料夾> [tracking-notes 目錄]`。
8. 導覽頁（`HandoffIndex.tsx`）的「流程走查」區加一列連到這則 story。

## 檢查器會抓什麼

- 同一條流程裡步驟代號重複、沒有 `title` 或 `screen`、`actor` 不在四種之內。
- index 的 `id` 與 stories 的 `board("<id>")` 對不上；index 有的流程沒有 story。
- 便利貼 `flow-<id>.json` 裡的 `flowStep` 在看板裡找不到（那張便利貼會留在檔裡但畫面不顯示）。
- 步驟 `action` 沒寫「點「…」」形式只提醒，不擋。

## 規則

- 流程代號與步驟代號是契約：便利貼靠它們，改了就掉。名稱、文字、順序可以改。
- 畫面只能是既有元件的起始狀態；要新狀態先改元件，再回來排步驟。
- 一條流程只講一件事（一個目標、一條主路徑）；分支另開一條流程，或在 `note` 寫「若…則…」。
- 需求狀態變了（設計中→開發中→已上線）只改 story title 的群組前綴，用 storybook-tracking-notes 的 `retitle_notes.py` 同步便利貼標題。
