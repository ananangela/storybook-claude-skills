# storybook-claude-skills

給 Claude Code 用的 Storybook 工作 skill。裝到自己電腦的 `~/.claude/skills/` 底下，Claude 就會在對話裡自動啟用。

| Skill | 做什麼 |
|---|---|
| `storybook-tracking-notes` | 埋點便利貼：PM 直接在 Storybook 畫面上貼便利貼，存進倉庫，Claude 讀得到、跟著版本走。含外掛原始碼、安裝步驟、資料格式、維護腳本、Figma 便利貼匯入做法。 |
| `storybook-flow-storyboard` | 流程走查：一條流程一步一格，每格是真的畫面元件停在那一步，便利貼貼在這裡。含看板元件、範本、檢查器。 |

## 安裝（Mac，終端機貼一行）

```bash
mkdir -p ~/.claude/skills && git clone https://github.com/ananangela/storybook-claude-skills.git /tmp/scs && cp -R /tmp/scs/storybook-tracking-notes /tmp/scs/storybook-flow-storyboard ~/.claude/skills/ && rm -rf /tmp/scs
```

裝完重開一個 Claude Code 對話。提到「便利貼」或「流程走查」就會啟用，也可以直接打 `/storybook-tracking-notes`、`/storybook-flow-storyboard`。

之後有更新，再跑一次同一行就是覆蓋成最新版。

## 第一次在一個 Storybook 專案用

- 便利貼：跟 Claude 說「幫這個專案裝便利貼」。
- 流程走查：跟 Claude 說「用流程走查 skill 幫 ○○ 需求做流程走查」。

## 前提

- Storybook 9 以上、React、Vite。
- 便利貼要能寫入，只有在本機跑 `storybook dev` 的那台電腦；靜態版唯讀。
