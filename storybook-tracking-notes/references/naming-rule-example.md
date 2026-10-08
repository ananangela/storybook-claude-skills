# 既有埋點清單（給「埋點便利貼」的下拉選單用）

`invoice-manager.json` 是 Storybook 裡「埋點便利貼」選「既有埋點」時的選項來源。
一個事件一筆：`name`（事件名）、`description`（觸發時機）、`params`（參數）、`module`（所屬功能）、`source`（這筆從哪裡來）。

## 事件的定義以 PM 的埋點表為準

這裡**只是挑選用的副本**，不是事件定義。計算條件、完整參數、上線版本都以 PM 維護的《發票載具 APP 埋點表》為準；兩邊不一致時改這裡，不要改埋點表。

## 從 PM 的埋點表更新

埋點表是需要登入的 Google Sheet，程式抓不到，所以走「匯出 → 匯入」：

1. 在 Google Sheet 打開要匯入的那個工作表 → 檔案 → 下載 → 逗號分隔值（.csv）。
2. 在 `app/` 目錄執行：

```bash
node scripts/import-tracking-events.mjs ~/Downloads/埋點表.csv
```

腳本會自動找「事件名／觸發時機／參數／頁面」這幾欄（欄名不同會印出來讓你確認），
把結果合併進 `invoice-manager.json`：同名事件以匯入的為準，匯入表裡沒有的既有事件保留。
匯完看一眼 `git diff`，再重新整理 Storybook 就會出現在下拉選單裡。

## 命名規則（新埋點照這個取名）

依 PM 提供的《Firebase 事件命名規則》（HackMD，2026-09-24 提供；原文是股市籌碼 K 線的規範，發票載具沿用同一套，既有的 `SWG_InvitePopup_showed` 就是這個格式）：

```
前綴_名稱_動作      例：SWG_InvitePopup_showed、Toolkit_WidgetSocial_clicked
```

| 段 | 規則 | 例 |
|---|---|---|
| 前綴 | 觸發事件的頁面／功能縮寫，**3 個大寫英數字**（發票載具現況也有較長的，如 `Toolkit`、`WGT`）；不隸屬任何頁面可留空 | `SWG`（碼上有你）、`WGT`（Widget） |
| 名稱 | 觸發事件的 UI 元件或條件，**每個詞首字母大寫**（PascalCase），可加功能性形容詞；**禁止顏色、形狀、位置**等外觀形容詞（改版就會失效） | `InvitePopup`、`FriendPage`、`CopyLink` |
| 動作 | **全小寫、過去式動詞** | `clicked`、`entered`、`showed`、`closed`、`accepted`、`succeed` |

- 頁面縮寫不可與現有的重複；新功能的縮寫先查 `invoice-manager.json` 裡已有的前綴。
- 善用縮寫縮短長度（`Btn`、`Acct`、`Pwd`、`Intro`）。
- 完整規範與該 App 的頁面縮寫表：（PM 提供的命名規範文件，連結放在專案自己的 tracking-events/README.md）
- PM 的埋點表（需登入）：https://docs.google.com/spreadsheets/d/<SHEET_ID> — 相關工作表：「埋點表」「新埋點」「活動埋點」「已刪除埋點」。

## 從瀏覽器直接抓（不用下載 CSV）

埋點表要登入才看得到，但登入後可以用「內嵌 HTML 表格」的網址開它，不會觸發下載：

```
https://docs.google.com/spreadsheets/d/<SHEET_ID>/gviz/tq?tqx=out:html&sheet=埋點表
```

在那一頁的開發者工具主控台執行下面這段，就會把表格整理成 TSV 複製到剪貼簿；貼到 `imports/<日期>-tracking-sheet.tsv` 後跑上面的匯入指令即可（`.tsv` 也吃）。

```js
const rows=[...document.querySelectorAll('table tr')].map(tr=>[...tr.querySelectorAll('td,th')].map(td=>td.innerText.trim().replace(/\s+/g,' ')));
let page='';const out=['PAGE\tNAME\tDEF\tPARAMS\tTRIGGER'];
for(const r of rows.slice(1)){if(r[0])page=r[0];const name=(r[1]||'').trim();if(!/^[A-Za-z][A-Za-z0-9_\-]*$/.test(name))continue;
const def=[r[2],r[3]].filter((v,i,a)=>v&&a.indexOf(v)===i).join(' | ');out.push([page,name,def,[r[4],r[5]].filter(Boolean).join(' / '),r[6]||''].join('\t'));}
await navigator.clipboard.writeText(out.join('\n'));
```

## 目前內容

- 2026-09-24：從 PM 的《發票載具APP公用表單 › 埋點表》整表匯入（見 `imports/2026-09-24-tracking-sheet.tsv`），依「頁面名稱」分模組。
- 碼上有你（前綴 `SWG`）31 個事件不在埋點表裡，仍是 2026-09-16 讀 iOS／Android 程式碼整理的清單；PM 補進埋點表後重跑匯入會以表為準。
- 「新埋點」「活動埋點」兩張工作表的內容都已包含在埋點表裡，不另外匯入。
