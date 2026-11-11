# storybook-claude-skills

給 Claude Code 用的 Storybook 工作 skill。裝到自己電腦的 `~/.claude/skills/` 底下，Claude 就會在對話裡自動啟用。

| Skill | 做什麼 |
|---|---|
| `storybook-tracking-notes` | 埋點便利貼：PM 直接在 Storybook 畫面或 UI Flow 上貼便利貼，存進倉庫，Claude 讀得到、跟著版本走。新埋點自動登記進事件清單（不用等 PM 更新埋點表）。含外掛原始碼、安裝步驟、資料格式、維護與同步腳本、Figma 便利貼匯入做法。 |
| `handoff-preflight` | 交付前檢查：推交付資料夾前必跑。文案有沒有寫進文件、舊規則殘留、State Coverage、定案引用、版本紀錄、Overall 登記、便利貼快照過期、側欄狀態群組與頁面狀態標籤一致，八類。 |
| `storybook-product-prototype` | 交付資料夾契約：PRD／FLOW_SPEC／UI_SPEC／DATA_SPEC／PRODUCTION_HANDOFF／ACCEPTANCE／IMPLEMENTATION_GUIDE ＋ 原型、節點圖、Prototype 檢視器；含驗證器。 |
| `deliverable-doc-rules` | 交付文件五條硬規則與檢查器（不留模糊地帶、不留對話過程、每顆按鈕有去處、假資料聲明、沒有點不到的連結）。 |
| `storybook-tracking-handoff` | 把埋點寫進 FLOW_SPEC 轉場表與 PRODUCTION_HANDOFF 埋點節，並用 lint 看住不脫鉤。 |
| `storybook-flow-storyboard` | 流程走查：一條流程一步一格，每格是真的畫面元件停在那一步。這份資料就是 UI Flow 裡「狀態卡」與「一步一步」的來源。含看板元件、範本、檢查器。 |

## 安裝

**建議放在專案裡**：把六個資料夾複製到你的 Storybook 倉庫根目錄 `.claude/skills/` 底下、進版控。Claude Code 會自動讀到，clone 的人不用再各自安裝，版本跟著倉庫走。skill 文件裡的檢查指令就是以這個位置寫的（`python3 .claude/skills/<skill>/scripts/...`，從倉庫根目錄執行）。

```bash
git clone --depth 1 https://github.com/ananangela/storybook-claude-skills.git /tmp/scs && mkdir -p .claude/skills && cp -R /tmp/scs/storybook-tracking-notes /tmp/scs/storybook-flow-storyboard /tmp/scs/handoff-preflight /tmp/scs/storybook-product-prototype /tmp/scs/deliverable-doc-rules /tmp/scs/storybook-tracking-handoff .claude/skills/ && rm -rf /tmp/scs
```

也可以裝到自己電腦的全域位置 `~/.claude/skills/`（把上面的 `.claude/skills/` 換成 `~/.claude/skills/`）。交付前檢查的腳本看到 `~/.claude/skills/<skill>/` 的舊寫法時，會優先改用倉庫裡的複本（有的話）。

六個要一起裝、裝在同一個位置，因為交付前檢查會呼叫另外兩個 skill 的檢查器。裝完重開一個 Claude Code 對話。提到「便利貼」「流程走查」「交付」「交付前檢查」「交接文件」就會啟用，也可以直接打 `/storybook-tracking-notes`、`/storybook-flow-storyboard`、`/handoff-preflight`、`/storybook-product-prototype`。

之後有更新，再跑一次同一行就是覆蓋成最新版。

## 第一次在一個 Storybook 專案用

- 便利貼：跟 Claude 說「幫這個專案裝便利貼」。
- 流程走查：跟 Claude 說「用流程走查 skill 幫 ○○ 需求做流程走查」。

## 前提

- Storybook 9 以上、React、Vite。
- 便利貼要能寫入，只有在本機跑 `storybook dev` 的那台電腦；靜態版唯讀。

## 更新

- 2026-11-11：改為建議放在專案 `.claude/skills/`；SKILL.md 的指令路徑改成倉庫相對路徑；交付前檢查腳本相容舊的全域路徑寫法。倉庫改為公開（MIT）。

- 2026-10-14：流程走查正式併入 UI Flow（側邊欄無獨立頁、便利貼搬到 flow-overall.json、快照 cards 篩選、文件改字）。
- 2026-10-14：原型契約 skill 的檢視器更新到最新版（UI Flow 嵌入全 App 流程圖、流程走查模式拿掉、Data 多埋點事件區；meta 可給 unifiedFlowStoryId／flowScope）。
- 2026-10-14：加入交付用的四個 skill（handoff-preflight、storybook-product-prototype、deliverable-doc-rules、storybook-tracking-handoff）；便利貼快照腳本。

- 2026-10-13：便利貼 ＝ 新埋點自動登記事件清單、重複名字自動修正、UI Flow 當便利貼看板；流程走查 ＝ 併進 UI Flow（狀態卡、一步一步）。裝過的人再跑一次安裝那一行就是最新版。
