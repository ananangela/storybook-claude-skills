#!/usr/bin/env python3
"""Drift check for analytics tracking on prototype flows.

TEMPLATE COPY — this file ships with the storybook-tracking-handoff skill.
Copy it into the target repo (conventionally `tools/lint_tracking.py`) and wire
`npm run ds:tracking` + pre-commit there; CI cannot read the skill directory.
The repo copy is canonical for that repo once installed.

The delivery package already carries tracking: the trigger ↔ event mapping lives
on the flow metadata, and the docs print it. Nothing watched it. Tokens have
`ds:lint`; a tracking row that goes stale looks exactly like one that is still
true, and it ships in the same package, so it is believed.

What goes wrong without this check, in the order it actually happens:

  1. Someone adds a transition. The 埋點 column has no cell for it, so nobody
     decides whether it is tracked. Silence reads as "not tracked" — but nobody
     ruled that.
  2. Someone removes a trigger. The docs keep printing an event for a control
     that no longer exists.
  3. Someone renames an event in the flow metadata but not in the docs, or the
     other way round. The two halves disagree and both look authoritative.

`不埋` and `—` are decisions and pass. An empty cell is not a decision.

Usage: python3 lint_tracking.py <target-root> [--strict]

Scans every `<target-root>/src/prototypes/*/` that has both a `*Flow.ts` and a
`docs/FLOW_SPEC.md`, so it covers prototypes added later without being edited.
"""
import glob
import os
import re
import sys

RULES = {
    'tracking-undecided':
        '轉場表的「埋點」欄是空的；要埋什麼、或明確 `不埋`，都要有人裁決（FLOW_SPEC.md § 埋點）',
    'trigger-undocumented':
        '流程資料有這條轉場，轉場表沒有；埋點掛在 trigger 上，表上沒有就等於沒人看得到',
    'trigger-orphan':
        '轉場表有這個 trigger，流程資料沒有；多半是轉場被刪掉、文件沒跟上',
    'tracking-mismatch':
        '流程資料與轉場表對同一條轉場的埋點講法不一致；兩邊都會被當成規格',
    'tracking-missing-in-handoff':
        '這個事件沒有出現在 PRODUCTION_HANDOFF.md 的 § 埋點；工程實際讀的是那一份',
    'tracking-params-missing-in-handoff':
        '這條轉場的參數值沒有出現在 PRODUCTION_HANDOFF.md；同一個事件從不同路徑送不同的值，漏一個就送錯',
    'table-header-missing':
        '轉場表找不到必要的欄名；欄名是機器讀的欄位名，翻掉會讓檢查靜默通過（skill references/workflow.md §3）',
}

TRIGGER_HEADER = 'Trigger'
TRACKING_HEADER = '埋點'
NOT_TRACKED = {'不埋', '—', '-', '–'}


def strip_comments(text):
    """Remove // and /* */ so a comment can never be mistaken for a field."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def split_objects(body):
    """Split a TS array body into its top-level { … } blocks."""
    blocks, depth, start = [], 0, None
    for i, ch in enumerate(body):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(body[start:i + 1])
                start = None
    return blocks


def read_flow_transitions(path):
    text = open(path, encoding='utf-8').read()
    m = re.search(r'Transitions\s*=\s*\[(.*?)\]\s*satisfies', text, re.S)
    if not m:
        return None
    out = []
    for block in split_objects(m.group(1)):
        b = strip_comments(block)

        def field(name):
            hit = re.search(name + r':\s*"([^"]*)"', b)
            return hit.group(1) if hit else None

        trigger = field('trigger')
        if trigger:
            out.append({
                'trigger': trigger,
                'from': field('from'),
                'to': field('to'),
                'tracking': field('tracking'),
                'params': field('trackingParams'),
            })
    return out


def read_spec_table(path):
    """Return {trigger: 埋點 cell} from FLOW_SPEC's Transitions table.

    Returns None when the table or a required header is absent, so a renamed
    header fails loudly instead of checking zero rows and passing.
    """
    text = open(path, encoding='utf-8').read()
    m = re.search(r'^##\s+Transitions\s*$(.*?)(?=^##\s)', text, re.S | re.M)
    if not m:
        return None
    rows = [ln for ln in m.group(1).splitlines() if ln.strip().startswith('|')]
    if len(rows) < 2:
        return None

    def cells(line):
        return [c.strip() for c in line.strip().strip('|').split('|')]

    header = cells(rows[0])
    if TRIGGER_HEADER not in header or TRACKING_HEADER not in header:
        return None
    ti, ki = header.index(TRIGGER_HEADER), header.index(TRACKING_HEADER)

    table = {}
    for line in rows[2:]:
        c = cells(line)
        if len(c) <= max(ti, ki):
            continue
        trigger = c[ti].strip('` ')
        table[trigger] = re.sub(r'[`*]', '', c[ki]).strip()
    return table


def mentions(text, needle):
    """Whole-token match. `balance_switch` must not be satisfied by
    `balance_switched` — a substring test passes a renamed event silently,
    which is the exact failure this linter exists to catch."""
    return re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', text) is not None


def check(folder, findings):
    name = os.path.basename(folder)
    flow_files = [p for p in glob.glob(os.path.join(folder, '*Flow.ts'))
                  if 'FlowExport' not in os.path.basename(p)]
    spec = os.path.join(folder, 'docs', 'FLOW_SPEC.md')
    handoff = os.path.join(folder, 'docs', 'PRODUCTION_HANDOFF.md')
    if not flow_files or not os.path.isfile(spec):
        return

    def add(rule, where, detail):
        findings.append((rule, where, detail))

    transitions = read_flow_transitions(flow_files[0])
    if transitions is None:
        add('trigger-undocumented', os.path.relpath(flow_files[0]),
            '找不到 Transitions 陣列')
        return

    table = read_spec_table(spec)
    if table is None:
        add('table-header-missing', os.path.relpath(spec),
            f'§ Transitions 的表需要 `{TRIGGER_HEADER}` 與 `{TRACKING_HEADER}` 兩個欄名')
        return

    handoff_text = open(handoff, encoding='utf-8').read() if os.path.isfile(handoff) else ''

    for t in transitions:
        trigger, cell = t['trigger'], table.get(t['trigger'])
        where = f'{name} · {trigger}'

        if cell is None:
            add('trigger-undocumented', os.path.relpath(spec),
                f'{where}（{t["from"]} → {t["to"]}）')
            continue
        if cell == '':
            add('tracking-undecided', os.path.relpath(spec), where)
            continue

        documented = None if cell in NOT_TRACKED else cell
        if documented != t['tracking']:
            add('tracking-mismatch', os.path.relpath(spec),
                f'{where}：流程資料 {t["tracking"] or "（不埋）"}、'
                f'轉場表 {documented or "（不埋）"}')
            continue

        if t['tracking']:
            if not mentions(handoff_text, t['tracking']):
                add('tracking-missing-in-handoff', os.path.relpath(handoff),
                    f'{where} → {t["tracking"]}')
            if t['params'] and not mentions(handoff_text, t['params']):
                add('tracking-params-missing-in-handoff', os.path.relpath(handoff),
                    f'{where} → {t["params"]}')

    known = {t['trigger'] for t in transitions}
    for trigger in table:
        if trigger not in known:
            add('trigger-orphan', os.path.relpath(spec), f'{name} · {trigger}')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    strict = '--strict' in sys.argv
    root = args[0] if args else '.'

    folders = sorted(
        d for d in glob.glob(os.path.join(root, 'src', 'prototypes', '*'))
        if os.path.isdir(d)
    )
    findings = []
    for folder in folders:
        check(folder, findings)

    print(f'Tracking lint target: {os.path.abspath(root)}')
    print(f'  prototypes_scanned: {len(folders)}')
    print(f'  rules_checked: {len(RULES)}')
    print(f'  findings: {len(findings)}')
    print(f'  strict mode: {"on" if strict else "off"}')
    print()

    if findings:
        print('Issues:')
        for rule, where, detail in findings:
            print(f'- {where}  {detail}')
            print(f'    ⚠ {RULES[rule]}  [{rule}]')
        print()
        print(f'Tracking lint FAILED — {len(findings)} 項。')
        return 1 if strict else 0

    print('Tracking lint passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
