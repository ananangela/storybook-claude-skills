#!/usr/bin/env python3
"""流程走查檢查器。

用法：python3 check_storyboards.py <handoff 資料夾> [tracking-notes 目錄]
  - 讀 <資料夾>/*Storyboards.tsx：每條流程的步驟代號是否唯一、有沒有 title／screen、actor 是否合法
  - 讀 <資料夾>/*StoryboardIndex.tsx 與 *Storyboards.stories.tsx：index 的 id 與 story 的 board("<id>") 是否對得上
  - 有給 tracking-notes 目錄時：flow-<id>.json 的 flowStep 是否都存在
退出碼 1 ＝ 有錯。
"""
import json, re, sys
from pathlib import Path

ACTORS = {"me", "other", "system", "external"}

def boards_from_source(src: str):
    """回傳 {匯出名: [steps]}；step = {id,title,action,actor,has_screen}。用括號配對切出每個 export 區塊。"""
    out = {}
    for m in re.finditer(r"export const (\w+) = \(\): FlowStoryboardBoard => \(\{", src):
        name, start = m.group(1), m.end()
        depth, i = 1, start
        while i < len(src) and depth:
            c = src[i]
            if c == "{": depth += 1
            elif c == "}": depth -= 1
            i += 1
        block = src[start:i]
        steps = []
        for s in re.finditer(r'\{\s*id:\s*"([^"]+)"\s*,\s*title:\s*"([^"]+)"', block):
            # 步驟物件可能跨好幾行：從這個 { 配對到它的 }，在整段裡找欄位
            j, depth = s.start(), 0
            k = j
            while k < len(block):
                if block[k] == "{": depth += 1
                elif block[k] == "}":
                    depth -= 1
                    if depth == 0: break
                k += 1
            obj = block[j:k + 1]
            steps.append({
                "id": s.group(1), "title": s.group(2),
                "action": (re.search(r'action:\s*"([^"]*)"', obj) or [None, None])[1],
                "actor": (re.search(r'actor:\s*"([^"]*)"', obj) or [None, None])[1],
                "has_screen": "screen:" in obj,
            })
        out[name] = steps
    return out

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    folder = Path(sys.argv[1]).resolve()
    notes_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    errors, warns = [], []

    boards = {}
    for p in folder.glob("*Storyboards.tsx"):
        boards.update(boards_from_source(p.read_text(encoding="utf-8")))
    if not boards:
        errors.append(f"{folder} 沒有 *Storyboards.tsx（或裡面沒有 export const x = (): FlowStoryboardBoard => (...) 這種匯出）")

    for name, steps in boards.items():
        ids = [s["id"] for s in steps]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup: errors.append(f"[{name}] 步驟代號重複：{sorted(dup)}")
        for s in steps:
            if not s["has_screen"]: errors.append(f"[{name}] 步驟 {s['id']} 沒有 screen")
            if s["actor"] and s["actor"] not in ACTORS: errors.append(f"[{name}] 步驟 {s['id']} 的 actor「{s['actor']}」不在 {sorted(ACTORS)}")
            if s["action"] and "「" not in s["action"]:
                warns.append(f"[{name}] 步驟 {s['id']} 的 action「{s['action']}」沒有「按鈕文字」，全 App 流程圖可能對不到按鈕")

    index_src = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("*StoryboardIndex.tsx"))
    index = dict(re.findall(r'\{\s*id:\s*"([^"]+)"\s*,\s*title:\s*"[^"]+"\s*,\s*related:[^\n]*?build:\s*boards\.(\w+)', index_src))
    stories_src = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("*Storyboards.stories.tsx"))
    story_ids = set(re.findall(r'board\("([^"]+)"\)', stories_src))
    for fid, fn in index.items():
        if fn not in boards: errors.append(f"index 的 {fid} 指到 boards.{fn}，但 *Storyboards.tsx 沒有這個匯出")
        if story_ids and fid not in story_ids: errors.append(f"index 有 {fid}，側邊欄 story 沒有 board(\"{fid}\")")
    for sid in story_ids:
        if sid not in index: errors.append(f"story 用了 board(\"{sid}\")，index 沒有這個代號")

    if notes_dir and notes_dir.is_dir():
        for fid, fn in index.items():
            p = notes_dir / f"flow-{fid}.json"
            if not p.is_file(): continue
            data = json.loads(p.read_text(encoding="utf-8"))
            step_ids = {s["id"] for s in boards.get(fn, [])}
            for n in data.get("notes", []):
                st = n.get("flowStep")
                if st and st not in step_ids:
                    errors.append(f"便利貼 {p.name} 的 {n.get('id')} 貼在步驟「{st}」，看板裡沒有這一步（便利貼不會顯示）")

    print(f"流程走查檢查：{folder.name}　流程 {len(index)} 條、步驟 {sum(len(v) for v in boards.values())} 格")
    if warns:
        print(f"  ~ 提醒 {len(warns)} 項（action 沒寫「按鈕文字」，全 App 流程圖可能對不到按鈕）：" + "；".join(w.split("的 action")[0].split("] ")[1] for w in warns[:6]) + ("…" if len(warns) > 6 else ""))
    if errors:
        print(f"\n❌ {len(errors)} 項要修")
        for e in errors: print("  - " + e)
        return 1
    print("✅ 通過")
    return 0

if __name__ == "__main__":
    sys.exit(main())
