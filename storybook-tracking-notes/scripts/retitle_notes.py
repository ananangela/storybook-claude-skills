#!/usr/bin/env python3
"""Storybook 群組改名後，把便利貼檔案裡的標題一起改。

用法：python3 retitle_notes.py <tracking-notes 目錄> "<舊標題前綴>" "<新標題前綴>"
例：  python3 retitle_notes.py app/design-system/tracking-notes "Prototypes/好友功能/" "當次交付/2026-09_好友功能/"

- 流程走查的檔（flow-*.json）用流程代號當檔名，只改 story.title。
- 一般 story 的檔名跟 Storybook 的 story id 走，所以 story.id 與檔名都要跟著標題改
  （用 Storybook 的 sanitize 規則算新 id）。
改完請用 rebuild_index.mjs 重產 INDEX.md。不會動到 notes 內容。
"""
import json, re, sys
from pathlib import Path

PUNCT = re.compile(r"[ ’–—―′¿'`~!@#$%^&*()_|+\-=?;:'\",.<>\{\}\[\]\\/]", re.I)

def sanitize(s: str) -> str:
    # 對應 @storybook/csf 的 sanitize：小寫、標點換 -、合併、去頭尾
    s = PUNCT.sub("-", s.lower())
    s = re.sub(r"-+", "-", s)
    return s.strip("-")

def file_stem(story_id: str) -> str:
    # 對應 server.mjs 的 storyFileStem：保留字母數字底線連字號
    stem = re.sub(r"[^\w-]+", "-", story_id)
    stem = re.sub(r"-+", "-", stem).strip("-")
    return stem[:160]

def main():
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(1)
    d, old, new = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    changed = renamed = 0
    for p in sorted(d.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        story = data.get("story") or {}
        title = story.get("title", "")
        if not title.startswith(old):
            continue
        story["title"] = new + title[len(old):]
        changed += 1
        target = p
        if not p.name.startswith("flow-"):
            old_id, prefix_old, prefix_new = story.get("id", ""), sanitize(old.rstrip("/")), sanitize(new.rstrip("/"))
            if old_id.startswith(prefix_old):
                story["id"] = prefix_new + old_id[len(prefix_old):]
                target = p.with_name(file_stem(story["id"]) + ".json")
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if target != p:
            target.write_text(text, encoding="utf-8"); p.unlink(); renamed += 1
            print(f"改名 {p.name} → {target.name}")
        else:
            p.write_text(text, encoding="utf-8")
    print(f"改了 {changed} 份標題，其中 {renamed} 份連檔名一起改。接著請重產 INDEX.md。")

if __name__ == "__main__":
    main()
