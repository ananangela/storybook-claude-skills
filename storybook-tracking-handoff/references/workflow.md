# 模式 B：逐案流程與文件範本

一個功能案跑一次。前提：目標 repo 已有 storybook-product-prototype 的原型結構，且該 app 已有命名規範（沒有先跑 module-table.md）。

## 1. 比對：PM 清單 ↔ flow triggers

逐條轉場對既有清單，分四類：

| 類 | 意思 | 動作 |
|---|---|---|
| **沿用** | 行為已有事件（含行為搬家、語意不變） | 直接掛，參數值照舊 |
| **既有加參數** | 既有事件多一個參數值涵蓋新路徑 | 掛既有事件，該路徑的值寫進 `trackingParams` |
| **新事件** | 清單裡沒有的全新行為 | 依規範**提議**名字，PM 拍板才算數 |
| **不埋** | 使用者操作但 PM 裁決不送 | 埋點欄寫 `不埋` |

比對是語意判斷、量不出來 —— 所以**建議與裁決分兩欄**，AI 只填建議欄。

三個比對時的固定動作：

- **埋點找不到可掛的 trigger** → 先懷疑流程表漏了轉場。行為在 PRD 裡存在但表上沒畫（例：離開某狀態的唯一路徑）就是缺口，補轉場（`flowLine` 依專案規則選 key 或 reference），並在 FLOW_SPEC 註明是何時、為何補的。
- **清單裡的事件綁的元件已被移除** → 失聯事件，必須浮出來給 PM：事件是搬家（沿用）還是退役。
- **同一事件從多條路送不同值** → 每條路各自一列，值寫在各自的 trigger 上；漏一條就送錯。

## 2. flow metadata

轉場型別加兩個**選填**欄位（省略＝不埋，是裁決不是漏填）：

```ts
/**
 * analytics 事件名。省略 ＝ 這條轉場不埋（PM 裁決，不是漏填）。
 * 這裡只存「trigger ↔ 事件名」的對應關係；事件的完整定義（計算條件、
 * 可用參數）以公司既有埋點表為準，不在這裡複製一份 —— 複製就會分岔。
 */
tracking?: string;
/** 這條轉場要送的參數值。同一事件從不同路徑送不同值，所以值屬於對應關係。 */
trackingParams?: string;
```

## 3. FLOW_SPEC.md

**轉場表**加第七欄 `埋點`（欄名 `Trigger` 與 `埋點` 是 lint 的機器契約，不可翻譯）：

```
| From | To | Trigger | 說明 | Kind | Flow line | 埋點 |
| `picker-month` | `picker-all` | `allTimeChip.click` | 選歷年 | primary | key | **`balance_switch`** |
| `picker-all` | `commit-delay` | `allTimeChip.committed` | 歷年已提交 | outcome | key | — |
| `picker-month` | `home-month` | `scrim.click` | 點遮罩收合 | return | reference | 不埋 |
```

欄名對照行補一句：`埋點 ＝ 這條轉場要送的 analytics 事件名（不埋 ＝ 使用者操作但經 PM 裁決不送；— ＝ 不是使用者操作，沒有埋點的位置）`。

**§ 埋點** 一節放在 Transitions 之後：埋幾個點、一張「觸發／事件名／參數」小表、然後逐條寫適用的發送規則（tracking-rules.md §5）與沿用理由。只寫結論與工程需要的因果，不寫討論過程。

## 4. PRODUCTION_HANDOFF.md

**§ 埋點** 放在 App/Web Implementation Notes 附近，格式：

```
## 埋點

**這一案埋 N 個點。** PM 裁決，<日期>。

| 觸發 | 使用者做了什麼 | 事件名 | 參數 | 何時送 |
|---|---|---|---|---|

- **沿用既有事件，不要取新名字。**（一句因果：行為搬家、數據要接得起來）
- **參數語意。**（若參數名與字面語意相反 —— 例如 from 記的是切換到哪 —— 一句話擋住，並註明照舊送不要改）
- **只有跨狀態的切換才送，○○不送。**（點名這一案最容易綁錯的觸發）
- **不要重複送。**（點名後續狀態節點）
- **系統自動行為不送。**（點名這一案的還原／自動情境）
- **事件的完整定義以公司既有埋點表為準**（註明讀取日），這裡只記對應關係。
- 其他操作**經 PM 裁決不埋**，見 FLOW_SPEC § 埋點。那是裁決結果，不是漏填。
```

待 PM 的問題寫進 Open Product Decisions，並註明「未答之前照○○實作」讓工程不被擋。

## 5. 流程圖

專案的每個流程輸出面（StaticFlow story、Prototype Inspector…）都要顯示事件名，**一個都不能漏** —— 只改一張，看另一張的人就拿到舊資訊。

改完必須**渲染並量測**：取所有邊線標籤與卡片的邊界框，兩兩檢查重疊，與改動前的基準比對。標籤加高（疊第二行）或加寬（同行附加）各有撞法，哪個安全取決於該圖的避障邏輯 —— 量了才知道。Playwright 開 `iframe.html?id=<story>`，`getBoundingClientRect` 全量比對即可。

## 6. 接檢查與收尾

1. `scripts/lint_tracking.py` 複製進目標 repo `tools/`，接 `npm run ds:tracking`（`--strict`）。
2. 掛進 pre-commit（repo 內 hooks 目錄 + `git config core.hooksPath`），與該 repo 既有檢查並排。
3. **逐條破壞測試**：清空埋點欄、刪一列、改事件名、翻譯欄名…七條規則每條都要親眼看到它咬人。特別驗「改成相似名」（`balance_switch` → `balance_switched`）—— 子字串比對會放過它。
4. 已送出的文件若被更正，寫變更通知：哪條規則變了、埋點受不受影響、哪三份文件更新了。

## 7. Figma 同步（手動）

Figma 稿上的埋點備注是手動同步的 —— 用 Figma MCP 讀節點文字核對措辭與交付文件一致，特別是發送規則的那幾句。要把卡片畫進 Figma，交給 Figma 埋點標注 skill，給它同一份對應表。
