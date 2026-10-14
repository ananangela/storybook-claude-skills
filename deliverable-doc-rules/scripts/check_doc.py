#!/usr/bin/env python3
"""交付文件五條硬規則的檢查器。

用法:
  python3 check_doc.py <檔案或資料夾…> [--json]

規則:
  R1 不能有建議或模糊地帶(「人工審核清單」一節除外)
  R2 不能出現使用者與 AI 的溝通過程
  R3 每一顆按鈕都要在「互動與跳轉表」裡有明確的互動方式與跳轉目的地
  R4 必須有「prototype 假資料不得上線、正式版接真實資料」的聲明
  R5 不能有讀者點不到的本機路徑或 localhost 連結

只回報,不改寫。exit code:0 全過;1 有違規。
"""
from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TERMS_FILE = HERE / "ambiguous_terms.txt"

R2_TERMS = [
    "使用者說", "使用者指示", "使用者認為", "使用者提出", "使用者指出", "使用者決定", "使用者定案", "使用者回饋", "使用者 20",
    "我覺得", "我建議", "我推薦", "我偏向", "我認為", "我的理解",
    "你說", "你提到", "你覺得", "你給的", "你剛",
    "討論了", "幾輪", "原本想", "後來改", "稍早曾", "作廢", "抱歉", "誤會", "對話", "聊到", "上一則", "前一則",
]

R5_PATTERNS = [
    r"localhost", r"127\.0\.0\.1", r"(?<![\w/])~/", r"/Users/", r"/private/tmp", r"(?<![\w])/tmp/", r"file://", r"\b[A-Z]:\\",
]

# 產品／功能名稱:內含的字串不算模糊詞或溝通過程(例如「碼上有你說明」裡的「你說」)。
# 比對前先把這些名稱從該行拿掉,避免誤判。專案有新名稱就加進來。
PRODUCT_NAMES = ["碼上有你", "馬上有你"]

# 人工審核清單一節的標題關鍵字:這一節允許 R1 的模糊詞
REVIEW_SECTION_KEYS = ["人工審核清單", "人工審核", "Manual Review", "Open Product Decisions"]
# 變更紀錄一節允許出現日期與版本,但仍不允許 R2 的過程詞

SUPPORTED = {".md", ".html", ".htm", ".txt", ".tsx", ".ts"}


@dataclass
class Finding:
    rule: str
    file: str
    line: int
    text: str
    hint: str


def load_terms() -> list[str]:
    terms = []
    for raw in TERMS_FILE.read_text(encoding="utf-8").splitlines():
        t = raw.strip()
        if t and not t.startswith("#"):
            terms.append(t)
    return terms


def html_to_lines(src: str) -> list[str]:
    """把 HTML 拆成「一個區塊一行」的純文字,行號對應原始檔的近似行。"""
    # 保留換行位置:把區塊結尾換成換行,再去標籤
    src = re.sub(r"<(script|style)[^>]*>.*?</\1>", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S | re.I)
    # 連結網址也要檢查(R5):把 href／src 的值留成文字
    src = re.sub(r'<(a|img|iframe|source)\b[^>]*?(?:href|src)="([^"]*)"[^>]*>', lambda m: m.group(0) if m.group(2).lower().startswith("data:") else f"{m.group(0)} {m.group(2)} ", src, flags=re.I)
    src = re.sub(r"<br\s*/?>", "\n", src, flags=re.I)
    # 表格:一列一行,儲存格之間用「 | 」,行首補「|」,讓 R3 的表頭偵測與空格檢查對 HTML 表也有效
    src = re.sub(r"<tr\b[^>]*>", "\n| ", src, flags=re.I)
    src = re.sub(r"</t[dh]>", " | ", src, flags=re.I)
    src = re.sub(r"</(p|li|tr|h[1-6]|div|figcaption|section)>", "\n", src, flags=re.I)
    src = re.sub(r"<[^>]+>", "", src)
    return [html.unescape(l) for l in src.split("\n")]


def tsx_string_lines(src: str) -> list[str]:
    """只掃字串字面值與 JSX 文字,程式邏輯不算。"""
    out = []
    for i, line in enumerate(src.split("\n")):
        strings = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|`([^`]*)`', line)
        jsx_text = re.findall(r">([^<>{}]+)<", line)
        pieces = [s for tup in strings for s in tup if s] + jsx_text
        out.append(" ".join(pieces))
    return out


def get_lines(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        return html_to_lines(src)
    if path.suffix.lower() in {".tsx", ".ts"}:
        return tsx_string_lines(src)
    return src.split("\n")


def section_of(lines: list[str]) -> list[str]:
    """回傳每一行所屬的章節標題(取最近一個標題行)。
    人工審核清單一節若有子標題(### 1. …),子標題仍算在清單內,直到出現同級或更高一級的標題為止。"""
    current = ""
    review_level = None  # 進入人工審核清單時的標題層級(# 的數量;非 markdown 標題視為 2)
    result = []
    for l in lines:
        s = l.strip()
        m = re.match(r"^(#{1,6})\s+", s)
        is_heading = bool(m) or bool(re.match(r"^[一二三四五六七八九十]+、", s)) or (len(s) < 30 and any(k in s for k in REVIEW_SECTION_KEYS))
        if is_heading:
            level = len(m.group(1)) if m else 2
            if review_level is not None and level > review_level:
                pass  # 清單內的子標題,維持在清單內
            else:
                current = s
                review_level = level if any(k in s for k in REVIEW_SECTION_KEYS) else None
        result.append(current)
    return result


def check_file(path: Path, terms: list[str]) -> list[Finding]:
    lines = get_lines(path)
    sections = section_of(lines)
    findings: list[Finding] = []
    rel = str(path)

    in_table_header_seen = False
    table_ok = False
    table_empty_cells = []
    table_ref_cells = []
    r4_ok = False
    lower_all = "\n".join(lines).lower()

    for idx, line in enumerate(lines, start=1):
        s = line.strip()
        if not s:
            continue
        sec = sections[idx - 1]
        in_review = any(k in sec for k in REVIEW_SECTION_KEYS)

        # R1
        if not in_review:
            # 引號內是逐字照抄的介面文案或既有名稱(例如區塊標題「你可能認識的人」),
            # 不是文件自己的模糊語氣,比對前先拿掉,避免誤判。
            bare = re.sub(r"[「『\"][^「『\"」』]*[」』\"]", "", s)
            for _name in PRODUCT_NAMES:
                bare = bare.replace(_name, "")
            for t in terms:
                if t.lower() in bare.lower():
                    findings.append(Finding("R1", rel, idx, s[:120], f"模糊詞「{t}」:改成定案句,或搬進「人工審核清單」"))
                    break
            if re.search(r"[？?]\s*$", s) and not s.startswith("|"):
                findings.append(Finding("R1", rel, idx, s[:120], "問句:文件裡不能留問題,搬進「人工審核清單」"))

        # R2
        s_r2 = s
        for _name in PRODUCT_NAMES:
            s_r2 = s_r2.replace(_name, "")
        for t in R2_TERMS:
            if t in s_r2:
                findings.append(Finding("R2", rel, idx, s[:120], f"溝通過程「{t}」:只寫結果與日期,不寫誰說的、怎麼談的"))
                break

        # R5
        for pat in R5_PATTERNS:
            if re.search(pat, s, flags=re.I):
                findings.append(Finding("R5", rel, idx, s[:120], "本機路徑或 localhost:換成讀者點得到的連結(Figma／artifact／共用 Storybook／git 相對路徑),或把內容直接嵌進文件"))
                break

        # R3 table detection (markdown or html-flattened row)
        if "互動方式" in s and ("跳轉" in s or "目的地" in s or "結果" in s):
            in_table_header_seen = True
            table_ok = True
        if in_table_header_seen and s.startswith("|") and "---" not in s and "互動方式" not in s:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if any(c in {"", "—", "-", "待補", "？", "?"} for c in cells):
                table_empty_cells.append((idx, s[:120]))
            # 每一格自足:不能交叉參照或用佔位詞
            for c in cells:
                if c in {"同上", "一律可用", "無", "無條件", "皆可"} or re.search(r"見\s*(第\s*)?[0-9０-９一二三四五六七八九十]+[a-zA-Z節]?", c):
                    table_ref_cells.append((idx, s[:120], c))
                    break

    # R4(只看正文,不看 <a href> 的網址)
    if re.search(r"(假資料|fixtures?|prototype\s*資料|示範資料)", lower_all) and re.search(r"(真實資料|真實的資料|api|後端|正式資料)", lower_all) and re.search(r"(不得|不能|不可|禁止)", lower_all):
        r4_ok = True
    if not r4_ok:
        findings.append(Finding("R4", rel, 1, "", "缺少假資料聲明:「原型中的名單／數字皆為 prototype 假資料,不得用於正式版;正式版一律接真實資料(API／後端)」"))

    # R3
    if not table_ok:
        findings.append(Finding("R3", rel, 1, "", "找不到「互動與跳轉表」(欄位:畫面｜元素｜互動方式｜跳轉／結果｜條件或狀態)"))
    for idx, s in table_empty_cells:
        findings.append(Finding("R3", rel, idx, s, "互動表有空格:每一格都要填,填不出來就進「人工審核清單」"))
    for idx, s, c in table_ref_cells:
        findings.append(Finding("R3", rel, idx, s, f"互動表儲存格「{c}」是交叉參照或佔位詞:把內容寫出來(條件沒有限制就寫「任何狀態下都可點」)"))

    return findings


def iter_files(args: list[str]):
    for a in args:
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix.lower() in SUPPORTED and "node_modules" not in f.parts:
                    yield f
        elif p.exists():
            yield p


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    terms = load_terms()
    all_findings: list[Finding] = []
    for f in iter_files(paths):
        all_findings.extend(check_file(f, terms))

    if as_json:
        print(json.dumps([asdict(x) for x in all_findings], ensure_ascii=False, indent=2))
    else:
        if not all_findings:
            print("✅ 五條規則全部通過")
        else:
            by_rule: dict[str, list[Finding]] = {}
            for x in all_findings:
                by_rule.setdefault(x.rule, []).append(x)
            names = {"R1": "模糊地帶(需人工審核)", "R2": "溝通過程", "R3": "按鈕路徑", "R4": "假資料聲明", "R5": "本機連結"}
            for rule in ["R1", "R2", "R3", "R4", "R5"]:
                items = by_rule.get(rule, [])
                if not items:
                    continue
                print(f"\n[{rule}] {names[rule]}:{len(items)} 處")
                for x in items:
                    loc = f"{x.file}:{x.line}"
                    print(f"  - {loc}  {x.text}" if x.text else f"  - {loc}")
                    print(f"      → {x.hint}")
            r1 = len(by_rule.get("R1", []))
            print(f"\n❌ 未通過。{'有 ' + str(r1) + ' 項模糊地帶需要人工審核。' if r1 else ''}")
    return 0 if not all_findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
