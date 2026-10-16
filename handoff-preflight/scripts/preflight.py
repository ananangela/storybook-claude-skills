#!/usr/bin/env python3
"""交付前檢查（handoff preflight）。

用法：python3 preflight.py <交付資料夾>   （資料夾裡要有 handoff-preflight.json）
      python3 preflight.py --status-all <倉庫根目錄> [stories 目錄，預設 app/src]
                                        （只跑第八類「狀態一致」，一次看所有需求）

把「原型改了文件沒跟上、舊規則沒清乾淨、狀態沒想完、定案編號指錯」這幾類問題變成機器抓。
任何一項 [錯誤] 都要修好才能推交付文件；[提醒] 要看過、確認沒問題。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

CJK = re.compile(r"[一-鿿]")
PLACEHOLDER = "〇"


# ---------------------------------------------------------------- 小工具
def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def section(text: str, heading: str) -> str:
    """回傳某個 ## 標題底下到下一個同級或更高標題為止的內容。"""
    m = re.search(rf"^(#+)\s+{re.escape(heading)}\s*$", text, re.M)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return rest[: end.start()] if end else rest


def without_section(text: str, heading: str) -> str:
    body = section(text, heading)
    return text.replace(body, "\n" * body.count("\n")) if body else text


def table_rows(block: str) -> list[list[str]]:
    rows = []
    for line in block.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def scan_string(src: str, i: int) -> tuple[str, int]:
    """從 src[i] 的引號開始讀一個 JS 字串或樣板字串，${...} 換成佔位符。回傳 (內容, 結束位置)。"""
    quote = src[i]
    out, j = [], i + 1
    while j < len(src):
        ch = src[j]
        if ch == "\\":
            out.append(src[j + 1] if j + 1 < len(src) else "")
            j += 2
            continue
        if ch == quote:
            return "".join(out), j + 1
        if quote == "`" and src.startswith("${", j):
            depth, k = 1, j + 2
            while k < len(src) and depth:
                if src[k] in "\"'`":
                    _, k = scan_string(src, k)
                    continue
                depth += {"{": 1, "}": -1}.get(src[k], 0)
                k += 1
            out.append(PLACEHOLDER)
            j = k
            continue
        out.append(ch)
        j += 1
    return "".join(out), j


def literals_in(expr: str) -> list[str]:
    found, j = [], 0
    while j < len(expr):
        if expr[j] in "\"'`":
            s, j = scan_string(expr, j)
            found.append(s)
        else:
            j += 1
    return found


def balanced(src: str, i: int, open_ch: str, close_ch: str) -> int:
    depth, j = 0, i
    while j < len(src):
        ch = src[j]
        if ch in "\"'`":
            _, j = scan_string(src, j)
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(src)


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def norm_doc(text: str) -> str:
    text = re.sub(r"○+|\{[^{}\n]{1,20}\}|(?<![A-Za-z])(N|XX)(?![A-Za-z])", PLACEHOLDER, text)
    return norm(text)


# ---------------------------------------------------------------- 檢查
def check_copy(cfg, root: Path, docs_text: str, errors, notes):
    """原型裡的使用者文案（Toast、推播、彈窗）一定要寫在文件裡。"""
    copy = cfg.get("copy", {})
    calls = copy.get("calls", ["setToast"])
    components = copy.get("components", [])
    ignore = [re.compile(p) for p in copy.get("ignore", [])]
    doc_norm = norm_doc(docs_text)
    seen: dict[str, str] = {}
    for d in copy.get("dirs", []):
        for f in sorted((root / d).resolve().rglob("*.tsx")):
            if ".stories." in f.name:
                continue
            src = read(f)
            for call in calls:
                for m in re.finditer(rf"\b{re.escape(call)}\(\s*", src):
                    k = m.end()
                    if k < len(src) and src[k] in "\"'`":
                        s, _ = scan_string(src, k)
                        seen.setdefault(s, f"{f.relative_to(root)}（{call}）")
            for comp in components:
                for m in re.finditer(rf"<{re.escape(comp)}\b", src):
                    end = balanced(src, m.start(), "<", ">")
                    tag = src[m.start():end]
                    for am in re.finditer(r"\b(title|body|text|message)=", tag):
                        v = am.end()
                        if v >= len(tag):
                            continue
                        if tag[v] in "\"'`":
                            vals = [scan_string(tag, v)[0]]
                        elif tag[v] == "{":
                            vals = literals_in(tag[v + 1: balanced(tag, v, "{", "}") - 1])
                        else:
                            vals = []
                        for s in vals:
                            seen.setdefault(s, f"{f.relative_to(root)}（{comp} {am.group(1)}）")
    checked = 0
    for s, where in sorted(seen.items()):
        key = norm(s)
        if len(key.replace(PLACEHOLDER, "")) < 4 or not CJK.search(key):
            continue
        if any(p.search(s) for p in ignore):
            continue
        checked += 1
        # 程式裡 ${...} 的位置在文件裡可能是一段說明（例如「○○ 的名單已滿」），所以佔位符可以對到任意短字串。
        pattern = ".{0,40}?".join(re.escape(part) for part in key.split(PLACEHOLDER))
        if not re.search(pattern, doc_norm):
            errors.append(f"[文案] 「{s}」在原型裡（{where}），文件裡找不到。把它寫進 UI_SPEC 的文案表，或改原型。")
    notes.append(f"文案：比對了 {checked} 句 Toast／推播／彈窗文案。")


def check_superseded(cfg, root: Path, files: list[Path], errors, notes):
    """被取代的舊說法不能還留在程式或文件裡。"""
    allow = re.compile(cfg.get("supersededAllowLine", r"取代|取消|不再|原本|原為|改為|變更紀錄"))
    entries = cfg.get("superseded", [])
    for f in files:
        text = read(f)
        if f.suffix == ".md":
            text = without_section(text, "變更紀錄")
        for n, line in enumerate(text.splitlines(), 1):
            if allow.search(line):
                continue
            for e in entries:
                if e["phrase"] in line:
                    errors.append(f"[舊規則] {f.resolve().relative_to(root)}:{n} 還寫著「{e['phrase']}」，已由{e['replacedBy']}取代。")
    notes.append(f"舊規則：比對了 {len(entries)} 個已被取代的說法。")


def check_states(cfg, folder: Path, errors, notes):
    """每一個畫面都要回答：成功、失敗、載入失敗、空狀態、權限、排序、更新時機。"""
    sc = cfg.get("stateCoverage")
    if not sc:
        return
    flow = next(iter(sorted(folder.glob("*PrototypeFlow.ts"))), None)
    ids = []
    if flow:
        m = re.search(r"RouteIds\s*=\s*\[(.*?)\]", read(flow), re.S)
        ids = re.findall(r"\"([a-z0-9-]+)\"", m.group(1)) if m else []
    doc = folder / sc["doc"]
    block = section(read(doc), sc["heading"])
    rows = table_rows(block)
    if not rows:
        errors.append(f"[狀態] {sc['doc']} 沒有「{sc['heading']}」狀態覆蓋表。")
        return
    header, body = rows[0], rows[1:]
    missing_cols = [c for c in sc["columns"] if c not in header]
    if missing_cols:
        errors.append(f"[狀態] 狀態覆蓋表少了欄位：{'、'.join(missing_cols)}。")
    covered = {}
    for r in body:
        rid = re.findall(r"`([a-z0-9-]+)`", r[0])
        for x in rid:
            covered[x] = r
        for c, cell in zip(header, r):
            if not cell or cell in {"-", "—", "?", "？"}:
                errors.append(f"[狀態] {r[0]} 的「{c}」是空的：每一格都要回答，用不到寫「不適用」。")
    for rid in ids:
        if rid not in covered:
            errors.append(f"[狀態] 畫面 `{rid}` 不在狀態覆蓋表裡。")
    notes.append(f"狀態：{len(ids)} 個畫面、{len(header) - 1} 個面向。")


def check_refs(cfg, folder: Path, doc_files: list[Path], errors, warnings, notes):
    """「第 N 條」要指到還有效的定案；「第 N 項」要指到人工審核清單裡真的有的項目。"""
    rc = cfg.get("decisions")
    if not rc:
        return
    handoff = folder / rc["doc"]
    text = read(handoff)
    active = {int(r[0]) for r in table_rows(section(text, rc["heading"])) if r and r[0].isdigit()}
    changelog = section(text, "變更紀錄")
    retired = {int(x) for x in re.findall(r"第 (\d+) 條", changelog)}
    opd_items = len(re.findall(r"^###\s+\d+\.", section(text, rc.get("openHeading", "Open Product Decisions")), re.M))
    for f in doc_files:
        body = without_section(read(f), "變更紀錄")
        for n, line in enumerate(body.splitlines(), 1):
            for num in map(int, re.findall(r"(?:第 |定案 ?)(\d+)(?: 條)", line)):
                if num in active:
                    continue
                if num in retired:
                    if not re.search(r"取代|取消|不再", line):
                        warnings.append(f"[定案] {f.name}:{n} 引用第 {num} 條，但它已被取代（見變更紀錄）。")
                else:
                    errors.append(f"[定案] {f.name}:{n} 引用第 {num} 條，定案表裡沒有這一條。")
            for num in map(int, re.findall(r"Open Product Decisions 第 (\d+) 項", line)):
                if num > opd_items:
                    errors.append(f"[定案] {f.name}:{n} 指到人工審核清單第 {num} 項，但清單只有 {opd_items} 項。")
    notes.append(f"定案：{len(active)} 條有效、{len(retired)} 條已取代、人工審核清單 {opd_items} 項。")


def check_overall(cfg, folder: Path, errors, notes):
    """當次交付的流程資料有沒有被 Overall 的合併檔 import（總覽/UI Flow 與 Prototype 要在交付時就完整）。"""
    ov = cfg.get("overall")
    if not ov:
        notes.append("Overall：這份設定沒有 overall 區塊，跳過（新需求請加 overall.registry 與 overall.tokens）。")
        return
    reg = (folder / ov["registry"]).resolve()
    if not reg.is_file():
        errors.append(f"[Overall] 找不到合併檔 {reg}")
        return
    text = read(reg)
    missing = [t for t in ov.get("tokens", []) if t not in text]
    if missing:
        errors.append(f"[Overall] 流程資料還沒登記進 {reg.name}：缺 " + "、".join(missing) + "。在 FEATURES 加一筆（需要時補 ALIASES）再交付。")
    else:
        notes.append(f"Overall：{reg.name} 已 import " + "、".join(ov.get("tokens", [])) + "。")


def check_tracking_notes(cfg, folder: Path, root: Path, errors, notes):
    """交付資料夾裡的埋點便利貼快照（docs/TRACKING_NOTES.md）有沒有過期（2026-10-14 起）。來源在 design-system/tracking-notes/，快照由腳本產生。"""
    tn = cfg.get("trackingNotes")
    if not tn:
        notes.append("便利貼快照：這份設定沒有 trackingNotes 區塊，跳過（有便利貼的功能請加 trackingNotes.match）。")
        return
    script = (root / tn.get("script", "app/scripts/export-tracking-notes.mjs")).resolve()
    if not script.is_file():
        errors.append(f"[便利貼快照] 找不到產生腳本 {script}（複本在 storybook-tracking-notes skill 的 scripts/）。")
        return
    proc = subprocess.run(["node", str(script), str(folder), "--check"], cwd=script.parent.parent, capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-2:]
    if proc.returncode != 0:
        errors.append("[便利貼快照] " + " / ".join(tail))
    else:
        notes.append("便利貼快照：" + (tail[-1] if tail else "最新"))


# ---------------------------------------------------------------- 第八類：狀態一致（2026-10-16 起）
# 側欄依狀態分組：story title 以「設計中/」「開發中/」「已上線/」開頭，底下是 YYYY-MM_功能名。
# 畫面本體只有一份在 Pages，用 tags 標 status-designing／status-delivered／status-live（左上角標籤）。
# 兩邊要一致：改群組的人要同時改頁面標籤，而且只在 PM 說上線後才動。
STATUS_GROUPS = ("設計中", "開發中", "已上線")
EXPECTED_TAG = {"設計中": "status-designing", "開發中": "status-delivered", "已上線": "status-live"}
STATUS_TAGS = set(EXPECTED_TAG.values())
GROUP_RE = re.compile(r"^(設計中|開發中|已上線)/([^/]+)")
META_START_RE = re.compile(r"(?:const\s+meta\b[^=\n]*=\s*|export\s+default\s+)(\{)")
TITLE_RE = re.compile(r"""\btitle\s*[:=]\s*["'`]([^"'`\n]+)["'`]""")


class StoryInfo:
    def __init__(self, file: Path, title: str, tag: str | None):
        self.file, self.title, self.tag = file, title, tag


def story_meta(src: str) -> tuple[str | None, str | None]:
    """回傳 (meta 的 title, meta 層 tags 裡的 status-* 標籤)。MDX 只有 <Meta title>。"""
    m = META_START_RE.search(src)
    if m:
        start = m.start(1)
        meta = src[start: balanced(src, start, "{", "}")]
    else:
        mdx = re.search(r"<Meta\b[^>]*>", src)
        meta = mdx.group(0) if mdx else ""
    t = TITLE_RE.search(meta)
    if not t:
        return None, None
    tag = None
    tm = re.search(r"\btags\s*:\s*\[([^\]]*)\]", meta)
    if tm:
        for x in re.findall(r"""["'`]([^"'`]+)["'`]""", tm.group(1)):
            if x in STATUS_TAGS:
                tag = x
    return t.group(1), tag


def scan_stories(base: Path) -> list[StoryInfo]:
    out = []
    for f in sorted(base.rglob("*")):
        if not f.is_file() or "node_modules" in f.parts:
            continue
        if not (f.name.endswith((".stories.tsx", ".stories.ts", ".stories.jsx", ".stories.js")) or f.suffix == ".mdx"):
            continue
        title, tag = story_meta(read(f))
        if title:
            out.append(StoryInfo(f, title, tag))
    return out


def under(f: Path, d: Path) -> bool:
    try:
        f.relative_to(d)
        return True
    except ValueError:
        return False


def pages_for(name: str, index: list[StoryInfo], dirs: list[Path], titles: list[str]) -> list[StoryInfo]:
    """這個需求「所屬的頁」＝ 明確列出的 Pages 標題 ∪ 指定資料夾底下的 Pages story ∪ 群組 story 自己帶了狀態標籤的。"""
    pages: dict[Path, StoryInfo] = {}
    for s in index:
        g = GROUP_RE.match(s.title)
        if g and g.group(2) == name and s.tag:
            pages[s.file] = s
        if s.title in titles:
            pages[s.file] = s
        if s.title.startswith("Pages/") and any(under(s.file, d) for d in dirs):
            pages[s.file] = s
    return [pages[k] for k in sorted(pages)]


def status_issues(name: str, index: list[StoryInfo], pages: list[StoryInfo], root: Path):
    """核心比對。回傳 (group, errors, warnings, notes)。"""
    errors, warnings, notes = [], [], []

    def rel(f: Path) -> str:
        return str(f.resolve().relative_to(root)) if under(f.resolve(), root) else str(f)

    groups: dict[str, Path] = {}
    for s in index:
        g = GROUP_RE.match(s.title)
        if g and g.group(2) == name:
            groups.setdefault(g.group(1), s.file)
    if not groups:
        notes.append(f"狀態一致：側欄找不到「設計中／開發中／已上線 / {name}」，跳過（deliveryName 要跟側欄的需求資料夾同名）。")
        return None, errors, warnings, notes
    if len(groups) > 1:
        errors.append(f"[狀態一致] 「{name}」同時出現在 " + "、".join(f"「{g}」（{rel(f)}）" for g, f in sorted(groups.items())) + "。同一個需求只能在一個群組，請統一。")
        return None, errors, warnings, notes
    group = next(iter(groups))
    expected = EXPECTED_TAG[group]
    for p in pages:
        shown = p.tag or "沒有狀態標籤"
        if group == "已上線" and p.tag != "status-live":
            errors.append(f"[狀態一致] 群組是「已上線/{name}」，但「{p.title}」是 {shown}（{rel(p.file)}）→ 改成 tags: [\"status-live\"]。")
        elif group != "已上線" and p.tag == "status-live":
            errors.append(f"[狀態一致] 群組是「{group}/{name}」，但「{p.title}」是 status-live（{rel(p.file)}）→ 改回 tags: [\"{expected}\"]；若 PM 已說上線，就把群組也改成「已上線」（兩邊要同一次改）。")
        elif p.tag != expected:
            warnings.append(f"[狀態一致] 群組是「{group}/{name}」，「{p.title}」是 {shown}（{rel(p.file)}），通常應為 {expected}。")
    if pages:
        notes.append(f"狀態一致：「{name}」在「{group}」，比對了 {len(pages)} 頁的狀態標籤（應為 {expected}）。")
    else:
        notes.append(f"狀態一致：「{name}」在「{group}」，找不到帶狀態標籤的頁（畫面還沒進 Pages），只確認了群組。")
    return group, errors, warnings, notes


def status_pages(cfg, folder: Path, name: str, index: list[StoryInfo]) -> list[StoryInfo]:
    """從設定推這個需求所屬的頁：status.pages（明確列 Pages 標題）＋ status.pageDirs（預設＝codeDirs）底下的 Pages story。"""
    st = cfg.get("status", {})
    dirs = [(folder / d).resolve() for d in st.get("pageDirs", cfg.get("codeDirs", ["."]))]
    return pages_for(name, index, dirs, st.get("pages", []))


def check_status(cfg, folder: Path, root: Path, errors, warnings, notes):
    """第八類：這個需求的側欄群組與它所屬 Pages 頁的 status-* 標籤要一致。"""
    st = cfg.get("status", {})
    index = scan_stories((root / st.get("storiesDir", "app/src")).resolve())
    name = cfg.get("deliveryName") or st.get("deliveryName")
    if not name:
        own = {GROUP_RE.match(s.title).group(2) for s in index if under(s.file, folder) and GROUP_RE.match(s.title)}
        if len(own) != 1:
            notes.append("狀態一致：設定沒有 deliveryName、資料夾裡也推不出唯一的需求名，跳過。")
            return
        name = own.pop()
    _, e, w, n = status_issues(name, index, status_pages(cfg, folder, name, index), root)
    errors.extend(e)
    warnings.extend(w)
    notes.extend(n)


def status_all(root: Path, stories_rel: str = "app/src") -> int:
    """整個倉庫跑一次狀態一致：每個側欄需求都比對（有 handoff-preflight.json 的用它的對應；沒有的用群組 story 所在資料夾推）。"""
    root = root.resolve()
    stories_dir = (root / stories_rel).resolve()
    index = scan_stories(stories_dir)
    configs: dict[str, tuple[Path, dict]] = {}
    for cfg_path in sorted(stories_dir.rglob("handoff-preflight.json")):
        cfg = json.loads(read(cfg_path))
        if cfg.get("deliveryName"):
            configs[cfg["deliveryName"]] = (cfg_path.parent, cfg)
    names = sorted({GROUP_RE.match(s.title).group(2) for s in index if GROUP_RE.match(s.title)})
    total_errors = 0
    print(f"狀態一致檢查：{root}（{len(names)} 個需求）\n")
    for name in names:
        if name in configs:
            folder, cfg = configs[name]
            pages = status_pages(cfg, folder, name, index)
            how = f"對應來自 {folder.relative_to(root)}/handoff-preflight.json"
        else:
            dirs = sorted({s.file.parent for s in index if GROUP_RE.match(s.title) and GROUP_RE.match(s.title).group(2) == name})
            pages = pages_for(name, index, dirs, [])
            how = "沒有 handoff-preflight.json，用群組 story 所在資料夾推"
        group, e, w, n = status_issues(name, index, pages, root)
        print(f"{'❌' if e else '✅'} {group or '?'} / {name}（{how}）")
        for p in pages:
            print(f"     · {p.title}：{p.tag or '沒有狀態標籤'}")
        for x in n:
            print("     " + x)
        for x in w:
            print("   [提醒] " + x)
        for x in e:
            print("   [錯誤] " + x)
        total_errors += len(e)
    print()
    if total_errors:
        print(f"❌ 狀態不一致：{total_errors} 項要修（改群組的人要同時改頁面標籤，只在 PM 說上線後才動）。")
        return 1
    print("✅ 所有需求的側欄群組與頁面狀態標籤一致。")
    return 0


def run_commands(cfg, root: Path, errors, notes):
    for c in cfg.get("commands", []):
        proc = subprocess.run(c["run"], shell=True, cwd=root / c.get("cwd", "."), capture_output=True, text=True)
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        if proc.returncode != 0:
            hint = f"（{c['hint']}）" if c.get("hint") else ""
            errors.append(f"[工具] {c['name']} 沒過{hint}：" + " / ".join(tail))
        else:
            notes.append(f"工具：{c['name']} 通過。")


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--status-all":
        return status_all(Path(sys.argv[2] if len(sys.argv) > 2 else "."), *sys.argv[3:4])
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    folder = Path(sys.argv[1]).resolve()
    cfg_path = folder / "handoff-preflight.json"
    if not cfg_path.is_file():
        print(f"找不到 {cfg_path}。每個交付資料夾要放一份 handoff-preflight.json，範本見 skill 的 SKILL.md。")
        return 2
    cfg = json.loads(read(cfg_path))
    root = (folder / cfg.get("repoRoot", ".")).resolve()
    doc_files = [(folder / d).resolve() for d in cfg["docs"]]
    extra_docs = [(folder / d).resolve() for d in cfg.get("extraDocs", [])]
    docs_text = "\n".join(read(p) for p in doc_files + extra_docs)
    code_files = [p for d in cfg.get("codeDirs", []) for p in sorted((folder / d).resolve().rglob("*")) if p.suffix in {".ts", ".tsx", ".js"} and p.is_file()]

    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    check_copy({"copy": {**cfg.get("copy", {}), "dirs": [str((folder / d).relative_to(root)) for d in cfg.get("copy", {}).get("dirs", [])]}}, root, docs_text, errors, notes)
    check_superseded(cfg, root, doc_files + extra_docs + code_files, errors, notes)
    check_states(cfg, folder, errors, notes)
    check_refs(cfg, folder, doc_files, errors, warnings, notes)
    check_overall(cfg, folder, errors, notes)
    check_tracking_notes(cfg, folder, root, errors, notes)
    check_status(cfg, folder, root, errors, warnings, notes)
    run_commands(cfg, root, errors, notes)

    print(f"交付前檢查：{cfg.get('name', folder.name)}\n")
    for n in notes:
        print("  · " + n)
    if warnings:
        print(f"\n[提醒] {len(warnings)} 項（看過、確認沒問題即可）")
        for w in warnings:
            print("  - " + w)
    if errors:
        print(f"\n❌ 未通過：{len(errors)} 項要修")
        for e in errors:
            print("  - " + e)
        return 1
    print("\n✅ 全部通過，可以交付。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
