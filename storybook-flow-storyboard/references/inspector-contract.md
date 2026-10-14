# Prototype Inspector 的「流程走查」模式契約


> **2026-10-13 起**：檢視器的「流程走查」模式已拿掉，`storyboards` 陣列仍要給——全 App 流程圖用它畫狀態卡與「一步一步」，便利貼也靠它對位。契約不變。

`parameters.prototype.storyboards` 是陣列，每項：

```ts
{ id: string; title: string; related?: string[]; render: () => ReactNode }
```

- `id`：流程代號，與便利貼檔名 `flow-<id>.json` 相同。
- `related`：這條流程會經過的 story title（可寫到群組或某一則）。切到某個 story 時，Inspector 用它排序：寫到那一則的最相關、預設就畫；只寫到群組的其次；都沒有的排最後、顯示「這一頁沒有對應的流程」。
- `render`：回傳 `<FlowStoryboard {...props} />`。
- 選了哪條流程記在網址 globals `prototypeFlowBoard`；換 story 會改回「這則畫面出現的第一條」。

便利貼外掛的看板偵測：畫面上有 `[data-flow-board="<id>"]` 時，便利貼改成跟流程存；每一步是 `[data-flow-step="<stepId>"]`，位置以該步的 `.ds-flow-storyboard__frame` 為基準（比例）。看板可用 `data-flow-board-story-title` 指定便利貼檔案裡的 story 標題（全 App 流程圖用）。
