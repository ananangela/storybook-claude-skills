#!/usr/bin/env python3
"""Validate the folder contract for a Storybook product prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path


REQUIRED_DOCS = [
    "PRD.md",
    "FLOW_SPEC.md",
    "UI_SPEC.md",
    "DATA_SPEC.md",
    "PRODUCTION_HANDOFF.md",
    "ACCEPTANCE.md",
    "IMPLEMENTATION_GUIDE.md",
]

REQUIRED_DOC_HEADINGS = {
    "PRD.md": ["Product Summary", "Problem", "Users", "Goals", "Non-Goals", "Core Journeys"],
    "FLOW_SPEC.md": ["Source Of Truth", "Route Map", "Transitions"],
    "UI_SPEC.md": ["Design Principle", "Interaction", "Accessibility"],
    "DATA_SPEC.md": ["Source Of Truth", "Fixture Inventory", "API Replacement Points"],
    "PRODUCTION_HANDOFF.md": [
        "Target Surfaces",
        "Prototype To Frontend Map",
        "Web Implementation Notes",
        "App Implementation Notes",
        "API And Data Contracts",
        "Frontend Handoff Acceptance",
        "Integration Ownership",
        "Storybook-Only Boundaries",
    ],
    "ACCEPTANCE.md": ["Storybook", "Interaction", "Frontend Handoff", "Engineering"],
    "IMPLEMENTATION_GUIDE.md": [
        "Implementation Order",
        "Frontend Transfer Checklist",
        "Required Verification",
    ],
}

# Any bracketed span is unresolved scaffold guidance, except markdown links
# ("](" follows), task-list markers, and spans inside code (stripped before
# matching in validate_docs).
PLACEHOLDER_PATTERN = re.compile(r"\[(?!(?:x|X| )?\])[^\]\n]+\](?!\()")

# Headings the current contract expects but older prototypes may predate.
# Missing ones are warnings by default and errors under --strict-style, so
# prototypes created before this contract keep validating.
NEW_DOC_HEADINGS = {
    "UI_SPEC.md": ["Component Map", "Component Gaps", "Token Binding"],
    "PRODUCTION_HANDOFF.md": [
        "Scope Classification",
        "Design System Continuity",
        "Shared Domain And UI State Model",
        "Open Product Decisions",
        "Review Status",
    ],
    "DATA_SPEC.md": ["Data Schemas (JSON Schema)", "State And Branch Fixtures"],
    "ACCEPTANCE.md": ["Data", "Production Integration Acceptance"],
}

# Acceptance criteria carry stable three-tier ids. Only bullet leaders are
# read so prose mentions like `AC-S-*` in guidance text never false-positive.
AC_ID_TOKEN_PATTERN = re.compile(r"^\s*[-*]\s+(AC-[^\s:]+)", re.MULTILINE)
AC_ID_VALID_PATTERN = re.compile(r"^AC-([SHP])-(\d{3})$")
AC_P_LINE_PATTERN = re.compile(r"^\s*[-*]\s+(AC-P-\d{3})\b(.*)$")

# Doc↔code cross-checks only trust ids written as top-level list-item leaders
# (`- `id`:` at column 0) so inline code in prose and nested explanation
# bullets cannot false-positive.
DOC_ID_BULLET_PATTERN = re.compile(r"^[-*]\s*`([a-z0-9][a-z0-9-]*)`\s*:", re.MULTILINE)
FIXTURE_BULLET_PATTERN = re.compile(r"^[-*]\s*`([A-Za-z_$][\w$]*)`\s*:", re.MULTILINE)
TABLE_FIRST_CELL_PATTERN = re.compile(r"^\s*\|\s*`([^`|]+)`\s*\|", re.MULTILINE)
EXPORT_CONST_PATTERN = re.compile(r"export\s+const\s+([A-Za-z_$][\w$]*)")

COMPONENT_NAME_PATTERN = re.compile(r"`([A-Z][A-Za-z0-9]+)`")
IMPORT_PATTERN = re.compile(r"import\s+(?:[^'\"]*?from\s+)?['\"]([^'\"]+)['\"]")
IMPORT_CLAUSE_PATTERN = re.compile(
    r"import\s+([^'\"]*?)\s+from\s+['\"][^'\"]+['\"]", re.DOTALL
)
NO_REUSABLE_PATTERN = re.compile(r"^\s*[-*]\s*No reusable components:", re.MULTILINE)
COLOR_LITERAL_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
VAR_FALLBACK_PATTERN = re.compile(
    r"var\((--[A-Za-z0-9-]+)\s*,\s*(?:[^()]|\([^()]*\))*\)"
)

# meta.components (optional composition contract) checks pull values with
# targeted regexes from a brace-COUNTED block — the non-greedy transition
# object regex is never reused here because nested objects truncate it.
COMPONENT_ORIGIN_VALUES = {"local", "promoted", "shared"}

# Framework-specific file locations; every other checked file is shared.
FRAMEWORK_FILE_PATTERNS = {
    "react": {
        "component": "*Prototype.tsx",
        "story": "*Prototype.stories.tsx",
        "static flow export": "*PrototypeFlowExport.tsx",
        "static flow story": "*PrototypeFlowExport.stories.tsx",
    },
    "vue": {
        "component": "*Prototype.vue",
        "story": "*Prototype.stories.ts",
        "static flow export": "*PrototypeFlowExport.vue",
        "static flow story": "*PrototypeFlowExport.stories.ts",
    },
}


def detect_prototype_framework(folder: Path) -> tuple[str, str | None]:
    react_component = find_one(folder, FRAMEWORK_FILE_PATTERNS["react"]["component"])
    vue_component = find_one(folder, FRAMEWORK_FILE_PATTERNS["vue"]["component"])
    if react_component is not None and vue_component is not None:
        return (
            "mixed",
            f"folder mixes frameworks: found both {react_component.name} and "
            f"{vue_component.name}; pass an explicit --framework react or --framework vue",
        )
    if vue_component is not None:
        return "vue", None
    return "react", None
COMPONENT_ROUTE_PATTERN = re.compile(r"\broute\s*:\s*['\"]([^'\"]+)['\"]")
COMPONENT_ORIGIN_PATTERN = re.compile(r"\borigin\s*:\s*['\"]([^'\"]+)['\"]")
COMPONENT_STORY_ID_PATTERN = re.compile(r"\bstoryId\s*:\s*['\"]([^'\"]+)['\"]")
COMPONENT_ENTRY_KEY_PATTERN = re.compile(r"\b(?:name|origin)\s*:")


def find_one(folder: Path, pattern: str) -> Path | None:
    matches = sorted(folder.glob(pattern))
    return matches[0] if matches else None


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def read(path: Path) -> str:
    return path.read_text(errors="replace")


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def quoted_strings(value: str) -> list[str]:
    return [match[0] or match[1] for match in re.findall(r'"([^"]+)"|\'([^\']+)\'', value)]


def scan_matching_bracket(text: str, start: int) -> int:
    """Index just past the bracket matching ``text[start]``, or ``-1``.

    Walks the source so nested brackets and brackets inside string literals do
    not terminate the span early. A non-greedy regex cannot do this: a
    transition object that carries a nested ``sourceAnchor: { ... }`` closes at
    the inner brace, silently hiding every key declared after it.
    """
    opener = text[start]
    closer = {"[": "]", "{": "}"}[opener]
    depth = 0
    index = start
    length = len(text)
    while index < length:
        char = text[index]
        if char in "\"'`":
            quote = char
            index += 1
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == quote:
                    break
                index += 1
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return -1


def extract_array_body(text: str, suffix: str) -> str:
    """Body of ``export const <name><suffix> = [ ... ]``.

    Accepts any tail (``as const``, ``satisfies T[]``, or a bare literal) AND a
    leading type annotation (``: T[] =``) so the declaration style never decides
    whether cross-checks run. Missing the annotated form is silent and
    expensive: an annotated transitions array parses as empty, so every
    per-transition check below simply never runs on it.
    """
    match = re.search(
        rf"export\s+const\s+\w+{re.escape(suffix)}\s*(?::[^=;\n]+)?=\s*\[", text
    )
    if not match:
        return ""
    start = text.rindex("[", match.start(), match.end())
    end = scan_matching_bracket(text, start)
    return text[start + 1 : end - 1] if end != -1 else ""


def split_top_level_objects(body: str) -> list[str]:
    """Top-level ``{ ... }`` bodies inside an array literal."""
    objects: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        if body[index] == "{":
            end = scan_matching_bracket(body, index)
            if end == -1:
                break
            objects.append(body[index + 1 : end - 1])
            index = end
            continue
        index += 1
    return objects


def extract_const_string_array(text: str, suffix: str) -> list[str]:
    return quoted_strings(extract_array_body(text, suffix))


def extract_object_array_ids(text: str, suffix: str) -> list[str]:
    """``id`` of every top-level object in ``export const <name><suffix> = [...]``.

    Route and flow-node ids also live here, and this is the shape the Prototype
    Inspector actually consumes (``flow.routes[].id``). Reading it keeps the
    validator's idea of a valid transition target aligned with the runtime's.
    """
    ids: list[str] = []
    for obj in split_top_level_objects(extract_array_body(text, suffix)):
        value = extract_string_property(obj, "id")
        if value:
            ids.append(value)
    return ids


def extract_transition_objects(text: str) -> list[str]:
    return split_top_level_objects(extract_array_body(text, "Transitions"))


def extract_flow_screen_ids(flow_text: str) -> list[str]:
    """Every screen id the flow metadata declares, across both id layers.

    Layer one is the component's own navigation routes (`*RouteIds`,
    `*FlowNodeIds`); layer two is the board screens rendered as UI Flow cards
    (`flow.routes[].id`, `flow.nodes[].id`), which a prototype may decompose
    more finely — one navigation route plus a dialog or toast state. Both are
    legitimate targets for a transition and legitimate keys for
    `meta.components.routes`, so checks must accept either.
    """
    ids: list[str] = []
    for value in (
        extract_const_string_array(flow_text, "RouteIds")
        + extract_const_string_array(flow_text, "FlowNodeIds")
        + extract_object_array_ids(flow_text, "Routes")
        + extract_object_array_ids(flow_text, "FlowNodes")
    ):
        if value not in ids:
            ids.append(value)
    return ids


def extract_string_property(object_text: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(['\"])(.*?)\1", object_text)
    return match.group(2) if match else None


def extract_int_property(object_text: str, key: str) -> int | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(\d+)\b", object_text)
    return int(match.group(1)) if match else None


def extract_route_viewport(object_text: str) -> dict | None:
    """``viewport: { width, height }`` of one route object, or None when absent.

    Returns the raw parse — width/height may be None when the declaration is
    malformed; callers decide whether that is an error (validator) or a skip
    (exporter).
    """
    match = re.search(r"\bviewport\s*:\s*\{", object_text)
    if not match:
        return None
    start = object_text.rindex("{", match.start(), match.end())
    end = scan_matching_bracket(object_text, start)
    if end == -1:
        return None
    body = object_text[start + 1 : end - 1]
    return {
        "width": extract_int_property(body, "width"),
        "height": extract_int_property(body, "height"),
    }


def _parse_viewport_body(body: str) -> dict:
    return {
        "formFactor": extract_string_property(body, "formFactor"),
        "width": extract_int_property(body, "width"),
        "height": extract_int_property(body, "height"),
    }


def extract_flow_viewport(flow_text: str) -> dict | None:
    """The flow-level viewport declaration, or None for legacy flows.

    Scaffolded flows export a ``<feature>Viewport`` const referenced from the
    Flow object; hand-authored flows may inline ``viewport: { ... }`` on the
    Flow object instead. The exported type alias also matches the ``Viewport =
    {`` pattern, but its body (``width: number``) parses to all-None and is
    skipped. Returned fields may individually be None for malformed
    declarations — callers decide whether that is an error or a skip.
    """
    for match in re.finditer(r"Viewport\s*=\s*\{", flow_text):
        start = flow_text.rindex("{", match.start(), match.end())
        end = scan_matching_bracket(flow_text, start)
        if end == -1:
            continue
        parsed = _parse_viewport_body(flow_text[start + 1 : end - 1])
        if any(value is not None for value in parsed.values()):
            return parsed

    flow_match = re.search(r"Flow\s*=\s*\{", flow_text)
    if flow_match:
        start = flow_text.rindex("{", flow_match.start(), flow_match.end())
        end = scan_matching_bracket(flow_text, start)
        if end != -1:
            body = flow_text[start + 1 : end - 1]
            viewport_match = re.search(r"\bviewport\s*:\s*\{", body)
            if viewport_match:
                inner_start = body.rindex(
                    "{", viewport_match.start(), viewport_match.end()
                )
                inner_end = scan_matching_bracket(body, inner_start)
                if inner_end != -1:
                    parsed = _parse_viewport_body(body[inner_start + 1 : inner_end - 1])
                    if any(value is not None for value in parsed.values()):
                        return parsed
    return None


def sanitize_meta_source(text: str) -> str:
    """Prepare meta TS source for brace-counting extraction.

    Character scan that tracks string literals ('", `, with backslash
    escapes) so it can safely drop `//` and `/* */` comments that sit
    OUTSIDE strings (a `note: "w/ badge // caveat"` value survives) and
    neutralize `{`/`}` characters INSIDE strings (they become spaces so
    brace counting never sees them). Guidance comments therefore never
    register as composition data, and string content never unbalances a
    block. Values later read by extract_string_property keep their text
    apart from any brace characters, which validation never needs.
    """
    result: list[str] = []
    quote: str | None = None
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if quote is not None:
            if char == "\\" and index + 1 < length:
                result.append(char)
                result.append(text[index + 1])
                index += 2
                continue
            if char == quote:
                quote = None
                result.append(char)
            elif char in "{}":
                result.append(" ")
            else:
                result.append(char)
            index += 1
            continue
        if char in "'\"`":
            quote = char
            result.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            close = text.find("*/", index + 2)
            result.append(" ")
            index = length if close == -1 else close + 2
            continue
        result.append(char)
        index += 1
    return "".join(result)


def extract_balanced_braces(text: str, start: int) -> str:
    """Return the balanced `{...}` block opening at `start`, or ""."""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""


def extract_brace_block(text: str, key: str) -> str:
    """Return the balanced `{...}` object for `<key>:` declared at the TOP
    level of the meta object literal, or "" if absent.

    Anchoring to the `const <name>Meta = {` object at depth 1 means a
    nested key with the same name (for example a `components` object inside
    `data.fixtures`) can never masquerade as the composition contract.
    Expects text already passed through sanitize_meta_source.
    """
    key_pattern = re.compile(rf"\b{re.escape(key)}\s*:\s*\{{")
    meta_open = re.search(r"\bconst\s+\w+Meta\b[^=]*=\s*\{", text)
    if not meta_open:
        opener = key_pattern.search(text)
        return extract_balanced_braces(text, opener.end() - 1) if opener else ""
    depth = 0
    index = meta_open.end() - 1
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1:
            match = key_pattern.match(text, index)
            if match:
                return extract_balanced_braces(text, match.end() - 1)
        index += 1
    return ""


def extract_component_entries(components_block: str) -> list[str]:
    """Split a components block into individual component entry objects.

    Walks the block with a brace stack and keeps each innermost balanced
    object that declares a `name:` or `origin:` key, so route wrapper objects
    are skipped without regex truncation.
    """
    entries: list[str] = []
    stack: list[int] = []
    for index, char in enumerate(components_block):
        if char == "{":
            stack.append(index)
        elif char == "}" and stack:
            start = stack.pop()
            candidate = components_block[start:index + 1]
            if "{" not in candidate[1:-1] and COMPONENT_ENTRY_KEY_PATTERN.search(
                candidate
            ):
                entries.append(candidate)
    return entries


def load_storybook_index_ids(index_path: Path) -> set[str] | None:
    """Return every story id in a Storybook index.json, or None if unreadable."""
    if not index_path.is_file():
        return None
    try:
        data = json.loads(read(index_path))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    entries = data.get("entries") or data.get("stories") or {}
    if not isinstance(entries, dict):
        return None
    ids: set[str] = set()
    for entry_key, entry in entries.items():
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        ids.add(str(entry_id or entry_key))
    return ids


def validate_docs(
    folder: Path,
    errors: list[str],
    warnings: list[str],
    handoff_ready: bool = False,
) -> None:
    docs_dir = folder / "docs"
    check(docs_dir.is_dir(), "missing docs/ directory", errors)
    if not docs_dir.is_dir():
        return

    for doc_name in REQUIRED_DOCS:
        doc_path = docs_dir / doc_name
        check(doc_path.is_file(), f"missing docs/{doc_name}", errors)
        if not doc_path.is_file():
            continue
        text = read(doc_path)
        for heading in REQUIRED_DOC_HEADINGS.get(doc_name, []):
            check(
                re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
                is not None,
                f"docs/{doc_name} missing heading '{heading}'",
                errors,
            )
        for heading in NEW_DOC_HEADINGS.get(doc_name, []):
            check(
                re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
                is not None,
                f"docs/{doc_name} missing heading '{heading}'",
                warnings,
            )
        if handoff_ready:
            prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            prose = re.sub(r"`[^`\n]*`", "", prose)
            placeholders = PLACEHOLDER_PATTERN.findall(prose)
            check(
                not placeholders,
                f"docs/{doc_name} still has unresolved bracket placeholder text",
                errors,
            )
            if doc_name == "PRODUCTION_HANDOFF.md":
                validate_review_status(text, errors, warnings)
                validate_integration_ownership(text, warnings)
        if doc_name == "PRODUCTION_HANDOFF.md":
            validate_handoff_scope(text, warnings)
        if doc_name == "ACCEPTANCE.md":
            validate_acceptance_ids(text, errors, warnings, handoff_ready)


SCOPE_VALUES = {"A", "B", "C", "U"}


def markdown_table_rows(section: str) -> list[list[str]]:
    """Cell lists for each pipe-table row, separator rows dropped."""
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell):
            continue
        rows.append(cells)
    return rows


def normalize_scope_cell(cell: str) -> str:
    """Leading scope letter of a cell, tolerating emphasis and trailing notes."""
    value = cell.replace("*", "").replace("`", "").strip()
    if not value:
        return ""
    head = value[0].upper()
    if head in SCOPE_VALUES and (len(value) == 1 or not value[1].isalpha()):
        return head
    return ""


def validate_handoff_scope(handoff_text: str, warnings: list[str]) -> None:
    """Every mapped part must declare whether production already has it.

    Without this column the map reads as a work list, and a receiving
    implementation rebuilds screens that already ship — waste that compiles,
    lints, and satisfies every other criterion. Warning-level so handoffs
    written before the column keep validating.
    """
    section = extract_doc_section(handoff_text, "Prototype To Frontend Map")
    rows = markdown_table_rows(section)
    if not rows:
        warnings.append(
            "docs/PRODUCTION_HANDOFF.md Prototype To Frontend Map has no table rows"
        )
        return

    # Single-target maps carry one `Scope` column; multi-target maps carry
    # `Scope(web)` / `Scope(app)` columns. Both forms are legal.
    header = rows[0]
    scope_indexes = [
        index
        for index, cell in enumerate(header)
        if re.fullmatch(
            r"scope(\((?:web|app)\))?", cell.replace("*", "").strip().lower()
        )
    ]
    if not scope_indexes:
        warnings.append(
            "docs/PRODUCTION_HANDOFF.md Prototype To Frontend Map has no 'Scope' "
            "(or 'Scope(web)'/'Scope(app)') column, so the receiving "
            "implementation cannot tell which surfaces already ship (A) from "
            "which are new (B)"
        )
        return

    for row in rows[1:]:
        for scope_index in scope_indexes:
            column = header[scope_index].replace("*", "").strip() or "Scope"
            if scope_index >= len(row):
                label = row[0] if row else "(empty row)"
                warnings.append(
                    f"docs/PRODUCTION_HANDOFF.md map row {label} has no {column} cell"
                )
                continue
            if not normalize_scope_cell(row[scope_index]):
                label = row[0] or "(unnamed row)"
                warnings.append(
                    f"docs/PRODUCTION_HANDOFF.md map row {label} has an unresolved "
                    f"{column} value; use A (already ships, do not rebuild), B (new), "
                    f"C (Storybook-only), or U (unverified, also list it in Open "
                    f"Product Decisions)"
                )


def validate_review_status(
    handoff_text: str, errors: list[str], warnings: list[str]
) -> None:
    """Handoff docs must carry a team-confirmed Review Status before handoff."""
    review_section = extract_doc_section(handoff_text, "Review Status")
    if not review_section:
        errors.append(
            "docs/PRODUCTION_HANDOFF.md has no Review Status section, so team "
            "confirmation of the Storybook demo cannot be verified"
        )
        return
    status_match = re.search(
        r"^[ \t]*[-*][ \t]*Status[ \t]*:[ \t]*(.+)$", review_section, re.MULTILINE
    )
    check(
        status_match is not None,
        "docs/PRODUCTION_HANDOFF.md Review Status has no 'Status:' line",
        errors,
    )
    if status_match:
        status_value = status_match.group(1).strip().strip("`").lower()
        check(
            status_value == "confirmed",
            "docs/PRODUCTION_HANDOFF.md Review Status is not confirmed; the team "
            "must confirm the Storybook demo before handoff",
            errors,
        )
    for label in ("Confirmed by", "Confirmed on", "Reviewed demo", "Scope"):
        require_review_field(review_section, label, "Review Status", errors)
    semantic = extract_doc_section(handoff_text, "Semantic Review")
    for label in ("Reviewed by", "Reviewed on", "Scope", "Related updates"):
        require_review_field(semantic, label, "Semantic Review", errors)
    check(
        doc_field(semantic, "Result").lower() == "passed",
        "Semantic Review must record Result: passed after reviewing sources and related updates",
        errors,
    )


def doc_field(section: str, label: str) -> str:
    match = re.search(rf"^[ \t]*[-*][ \t]+{re.escape(label)}[ \t]*:[ \t]*(.*)$", section, re.MULTILINE)
    return match.group(1).strip().strip("`") if match else ""


def meaningful_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().lower() not in {"unknown", "pending", "tbd", "todo", "none", "n/a"}
        and not PLACEHOLDER_PATTERN.search(value)
    )


def require_review_field(section: str, label: str, subject: str, errors: list[str]) -> None:
    value = doc_field(section, label)
    check(meaningful_text(value), f"{subject} requires a concrete {label} record", errors)
    if label.endswith(" on") and meaningful_text(value):
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("not YYYY-MM-DD")
            date.fromisoformat(value)
        except ValueError:
            errors.append(f"{subject} {label} must use YYYY-MM-DD")


def validate_acceptance_ids(
    text: str, errors: list[str], warnings: list[str], handoff_ready: bool
) -> None:
    """Acceptance criteria carry stable AC-S/AC-H/AC-P ids.

    Format violations and duplicates are always errors. Tier coverage is
    checked only under --handoff-ready. A legacy file with no ids at all gets
    a single warning so acceptance docs written before the id scheme keep
    validating.
    """
    tokens = AC_ID_TOKEN_PATTERN.findall(text)
    if not tokens:
        if handoff_ready:
            warnings.append(
                "docs/ACCEPTANCE.md has no AC-S/AC-H/AC-P criterion ids; legacy "
                "acceptance files keep validating, but new handoffs need stable "
                "ids so the receiving implementation can report traceability "
                "row by row"
            )
        return

    tier_counts = {"S": 0, "H": 0, "P": 0}
    seen: dict[str, int] = {}
    for token in tokens:
        match = AC_ID_VALID_PATTERN.match(token)
        if not match:
            errors.append(
                f"docs/ACCEPTANCE.md criterion id '{token}' does not match the "
                "AC-S-NNN / AC-H-NNN / AC-P-NNN format"
            )
            continue
        tier_counts[match.group(1)] += 1
        seen[token] = seen.get(token, 0) + 1

    for token in sorted(token for token, count in seen.items() if count > 1):
        errors.append(f"docs/ACCEPTANCE.md criterion id '{token}' is duplicated")

    if handoff_ready:
        for tier, label in (
            ("S", "AC-S (Storybook acceptance)"),
            ("H", "AC-H (handoff acceptance)"),
            ("P", "AC-P (production acceptance)"),
        ):
            check(
                tier_counts[tier] > 0,
                f"docs/ACCEPTANCE.md has no {label} criterion",
                errors,
            )

    for line in text.splitlines():
        match = AC_P_LINE_PATTERN.match(line)
        if match and "(assembly)" not in match.group(2) and "(integration)" not in match.group(2):
            warnings.append(
                f"docs/ACCEPTANCE.md {match.group(1)} has no (assembly) or "
                "(integration) owner tag, so the assembly pass cannot tell "
                "which production criteria it must settle in mock mode"
            )


def validate_integration_ownership(handoff_text: str, warnings: list[str]) -> None:
    """New handoffs name the stage-3 receiver of real data wiring explicitly.

    Warning-level so legacy handoffs written before the three-stage ownership
    contract keep validating; new handoffs must name an owner or record the
    open decision.
    """
    section = extract_doc_section(handoff_text, "Integration Ownership")
    if not section:
        return
    if "Data Integration Ownership" not in section:
        warnings.append(
            "docs/PRODUCTION_HANDOFF.md Integration Ownership has no 'Data "
            "Integration Ownership' field naming who replaces the mock adapters "
            "with real integrations; name a team, system, or person, or record "
            "the open decision in Open Product Decisions"
        )


def mask_code_fences(text: str) -> str:
    """Blank fenced code lines (same length, newlines kept) so `#` comments
    inside fences are never mistaken for markdown headings."""
    masked: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        is_fence_marker = line.lstrip().startswith(("```", "~~~"))
        if is_fence_marker or in_fence:
            masked.append(re.sub(r"[^\n]", " ", line))
        else:
            masked.append(line)
        if is_fence_marker:
            in_fence = not in_fence
    return "".join(masked)


def extract_doc_section(text: str, heading: str) -> str:
    scan_text = mask_code_fences(text)
    opener = re.search(rf"^(#+)[ \t]+{re.escape(heading)}[ \t]*$", scan_text, re.MULTILINE)
    if not opener:
        return ""
    level = len(opener.group(1))
    closer = re.search(
        rf"^#{{1,{level}}}\s", scan_text[opener.end():], re.MULTILINE
    )
    end = opener.end() + closer.start() if closer else len(text)
    return text[opener.end():end]


def unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_data_authority(
    folder: Path,
    files: dict[str, Path | None],
    errors: list[str],
    warnings: list[str],
    handoff_ready: bool,
) -> None:
    """Check declared authority, never infer it from a demo or fixture shape."""
    path = folder / "docs" / "DATA_SPEC.md"
    text = read(path) if path.is_file() else ""
    section = extract_doc_section(text, "Data Authority")
    headings = re.findall(r"^##\s+Data Authority\s*$", mask_code_fences(text), re.MULTILINE)
    if not headings:
        (errors if handoff_ready else warnings).append(
            "DATA_SPEC.md has no Data Authority registry; fixture schema authority is unverified"
        )
        return
    check(len(headings) == 1, "DATA_SPEC.md has duplicate Data Authority sections", errors)
    blocks = re.findall(r"^```json\s*\n(.*?)^```\s*$", section, re.MULTILINE | re.DOTALL)
    if len(blocks) != 1:
        errors.append("Data Authority requires exactly one fenced json registry")
        return
    try:
        registry = json.loads(blocks[0], object_pairs_hook=unique_json_object)
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Data Authority is not valid JSON: {exc}")
        return
    if not isinstance(registry, dict) or type(registry.get("schemaVersion")) is not int or registry.get("schemaVersion") != 1:
        errors.append("Data Authority requires schemaVersion 1")
        return
    if not isinstance(registry.get("fixtures"), list) or not isinstance(registry.get("contracts"), list):
        errors.append("Data Authority requires fixtures and contracts arrays")
        return
    if handoff_ready:
        for heading in ("Fake Data", "Real Data Contract"):
            check(bool(extract_doc_section(text, heading)), f"DATA_SPEC.md requires {heading}", errors)

    indexed: dict[str, dict[str, dict]] = {"fixtures": {}, "contracts": {}}
    for collection, key in (("fixtures", "group"), ("contracts", "id")):
        for index, record in enumerate(registry[collection]):
            subject = f"Data Authority {collection}[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{subject} must be an object")
                continue
            identifier = record.get(key)
            if not meaningful_text(identifier):
                errors.append(f"{subject} needs a concrete {key}")
                continue
            subject = f"Data Authority {collection} {identifier}"
            check(identifier not in indexed[collection], f"{subject} is duplicated", errors)
            indexed[collection][identifier] = record
            check(meaningful_text(record.get("owner")), f"{subject} needs a named owner", errors)
            status = record.get("status")
            check(status in ("proposed", "open", "confirmed", "superseded"), f"{subject} has invalid status", errors)
            check("source" in record, f"{subject} must explicitly record source or null", errors)
            source = record.get("source")
            if source is not None or status == "confirmed":
                complete = isinstance(source, dict) and all(
                    meaningful_text(source.get(field))
                    for field in ("reference", "revision", "confirmedBy", "confirmedOn")
                )
                check(complete, f"{subject} requires source reference, revision, confirmedBy and confirmedOn", errors)
                if complete:
                    try:
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", source["confirmedOn"]):
                            raise ValueError("not YYYY-MM-DD")
                        date.fromisoformat(source["confirmedOn"])
                    except ValueError:
                        errors.append(f"{subject} source confirmedOn must use YYYY-MM-DD")
            if collection == "fixtures":
                check(record.get("values") == "fake", f"{subject} values must stay fake", errors)
                check(record.get("schemaScope") in ("ui-model", "transport"), f"{subject} has invalid schemaScope", errors)
                if handoff_ready:
                    check(status != "superseded", f"{subject} is an active fixture with superseded authority", errors)
            else:
                check(record.get("kind") in ("api", "analytics", "remote-config", "storage", "static"), f"{subject} has invalid kind", errors)

    for group, record in indexed["fixtures"].items():
        if "contractId" not in record:
            continue
        contract_id = record["contractId"]
        if not isinstance(contract_id, str) or contract_id not in indexed["contracts"]:
            errors.append(f"Data Authority fixture {group} references an unknown contractId")
        elif handoff_ready and indexed["contracts"][contract_id].get("status") == "superseded":
            errors.append(f"Data Authority fixture {group} references superseded contract {contract_id}")
    if handoff_ready:
        data = files.get("data")
        expected = set(EXPORT_CONST_PATTERN.findall(sanitize_meta_source(read(data)))) if data and data.is_file() else set()
        expected.update(p.stem for p in (folder / "fixtures").glob("*.json"))
        actual = set(indexed["fixtures"])
        for name in sorted(expected - actual):
            errors.append(f"Data Authority is missing fixture group {name}")
        for name in sorted(actual - expected):
            errors.append(f"Data Authority references nonexistent fixture group {name}")


def validate_doc_code_consistency(
    folder: Path,
    files: dict[str, Path | None],
    errors: list[str],
    warnings: list[str],
) -> None:
    """Cross-check doc contracts against the flow and data source files.

    Runs only with --handoff-ready: drafts may legitimately drift while the
    prototype is still being shaped, but handed-off docs may not.
    """
    docs_dir = folder / "docs"
    flow_path = files.get("flow")
    data_path = files.get("data")
    flow_spec = docs_dir / "FLOW_SPEC.md"
    handoff = docs_dir / "PRODUCTION_HANDOFF.md"
    data_spec = docs_dir / "DATA_SPEC.md"

    route_ids: list[str] = []
    flow_node_ids: list[str] = []
    if flow_path is not None and flow_path.is_file():
        flow_text = read(flow_path)
        route_ids = extract_const_string_array(flow_text, "RouteIds")
        flow_node_ids = extract_const_string_array(flow_text, "FlowNodeIds")
    all_ids = set(route_ids + flow_node_ids)

    if flow_spec.is_file() and all_ids:
        spec_text = read(flow_spec)
        route_map = extract_doc_section(spec_text, "Route Map")
        node_map = extract_doc_section(spec_text, "Flow Node Map")
        for route_id in route_ids:
            check(
                f"`{route_id}`" in route_map,
                f"FLOW_SPEC.md Route Map does not document flow route `{route_id}`",
                errors,
            )
        for node_id in flow_node_ids:
            check(
                f"`{node_id}`" in node_map,
                f"FLOW_SPEC.md Flow Node Map does not document flow node `{node_id}`",
                warnings,
            )
        for section_name, section in (
            ("Route Map", route_map),
            ("Flow Node Map", node_map),
        ):
            for doc_id in DOC_ID_BULLET_PATTERN.findall(section):
                check(
                    doc_id in all_ids,
                    f"FLOW_SPEC.md {section_name} documents `{doc_id}` but "
                    "*PrototypeFlow.ts does not define it",
                    errors,
                )

    if handoff.is_file() and route_ids:
        frontend_map = extract_doc_section(read(handoff), "Prototype To Frontend Map")
        for route_id in route_ids:
            check(
                f"`{route_id}`" in frontend_map,
                "PRODUCTION_HANDOFF.md Prototype To Frontend Map does not map "
                f"flow route `{route_id}`",
                errors,
            )
        for node_id in flow_node_ids:
            check(
                f"`{node_id}`" in frontend_map,
                "PRODUCTION_HANDOFF.md Prototype To Frontend Map does not mention "
                f"flow node `{node_id}`",
                warnings,
            )

    if data_path is not None and data_path.is_file():
        data_exports = set(EXPORT_CONST_PATTERN.findall(read(data_path)))
        if data_exports:
            references: list[tuple[str, str]] = []
            if data_spec.is_file():
                inventory = extract_doc_section(read(data_spec), "Fixture Inventory")
                references.extend(
                    ("DATA_SPEC.md Fixture Inventory", name)
                    for name in FIXTURE_BULLET_PATTERN.findall(inventory)
                )
            if handoff.is_file():
                contracts = extract_doc_section(
                    read(handoff), "API And Data Contracts"
                )
                references.extend(
                    ("PRODUCTION_HANDOFF.md API And Data Contracts", name.strip())
                    for name in TABLE_FIRST_CELL_PATTERN.findall(contracts)
                )
            for source, name in references:
                check(
                    name in data_exports,
                    f"{source} references fixture group `{name}` but "
                    "*PrototypeData.ts does not export it",
                    errors,
                )


def extract_named_array_body(text: str, name: str) -> str:
    """Body of ``export const <name> = [ ... ]`` for an exact export name."""
    match = re.search(
        rf"export\s+const\s+{re.escape(name)}\s*(?::[^=;\n]+)?=\s*\[", text
    )
    if not match:
        return ""
    start = text.rindex("[", match.start(), match.end())
    end = scan_matching_bracket(text, start)
    return text[start + 1 : end - 1] if end != -1 else ""


def validate_fixture_json_consistency(
    folder: Path,
    files: dict[str, Path | None],
    errors: list[str],
    warnings: list[str],
) -> None:
    """Cross-check the two fixture carriers (.ts exports and fixtures/*.json).

    Runs only with --handoff-ready. Structural checks only: presence in both
    carriers and JSON parseability are errors, and for route-content groups
    (names ending in ``Routes``) every JSON ``id`` must be a known flow screen
    id. Deep value equality is not checked; a route-id set difference between
    the carriers is a warning.
    """
    data_path = files.get("data")
    if data_path is None or not data_path.is_file():
        return
    # Strip comments first so example fixtures in guidance comments never
    # register as real ids or exports.
    data_text = sanitize_meta_source(read(data_path))
    exports = sorted(set(EXPORT_CONST_PATTERN.findall(data_text)))
    fixtures_dir = folder / "fixtures"
    json_groups: dict[str, Path] = {}
    if fixtures_dir.is_dir():
        json_groups = {path.stem: path for path in sorted(fixtures_dir.glob("*.json"))}
    if not exports and not json_groups:
        return

    if exports and not fixtures_dir.is_dir():
        errors.append(
            "prototype has no fixtures/ directory; every fixture group needs a "
            f"language-neutral fixtures/<group>.json counterpart ({', '.join(exports)})"
        )
        return

    for name in exports:
        check(
            name in json_groups,
            f"fixture group `{name}` has no fixtures/{name}.json counterpart",
            errors,
        )
    for name in sorted(json_groups):
        check(
            name in exports,
            f"fixtures/{name}.json has no matching fixture export in *PrototypeData.ts",
            errors,
        )

    flow_path = files.get("flow")
    valid_ids: set[str] = set()
    if flow_path is not None and flow_path.is_file():
        valid_ids = set(extract_flow_screen_ids(read(flow_path)))

    for name, path in sorted(json_groups.items()):
        try:
            payload = json.loads(read(path))
        except json.JSONDecodeError as exc:
            errors.append(f"fixtures/{path.name} is not valid JSON: {exc}")
            continue
        if not name.endswith("Routes"):
            continue
        json_ids = [
            item["id"]
            for item in (payload if isinstance(payload, list) else [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        if valid_ids:
            for value in unique(json_ids):
                check(
                    value in valid_ids,
                    f"fixtures/{path.name} references route id '{value}' that the "
                    "flow metadata does not define",
                    errors,
                )
        ts_ids = set(
            re.findall(
                r"\bid\s*:\s*['\"]([^'\"]+)['\"]",
                extract_named_array_body(data_text, name),
            )
        )
        if name in exports and ts_ids != set(json_ids):
            ts_only = sorted(ts_ids - set(json_ids))
            json_only = sorted(set(json_ids) - ts_ids)
            detail = "; ".join(
                part
                for part in (
                    f"only in .ts: {', '.join(ts_only)}" if ts_only else "",
                    f"only in .json: {', '.join(json_only)}" if json_only else "",
                )
                if part
            )
            warnings.append(
                f"fixture group `{name}` route id sets differ between the .ts and "
                f".json carriers ({detail}); keep both carriers in sync"
            )


TRANSITION_PRESENTATION_VALUES = {"push", "modal", "sheet", "fullscreen", "replace"}
TRANSITION_BACK_BEHAVIOR_VALUES = {"pop", "popToRoot", "dismiss", "none"}
TRANSITION_MOTION_VALUES = {"none", "platform-default", "custom"}


def app_target_in_scope(handoff_text: str) -> bool:
    """True when Target Surfaces declares an app surface that is in scope."""
    section = extract_doc_section(handoff_text, "Target Surfaces")
    # The surface label is routinely bolded (`- **App**: ...`). Without the
    # optional emphasis wrapper the match fails, app_target_in_scope returns
    # False, and the presentation check below is skipped in silence — the
    # handoff looks clean precisely because nothing was checked.
    match = re.search(
        r"^\s*[-*]\s+(?:\*{1,2}|_{1,2})?App(?:\*{1,2}|_{1,2})?\s*:\s*(.+)$",
        section,
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        return False
    return "not in scope" not in match.group(1).strip().lower()


def extract_meta_surface_target(meta_text: str) -> str | None:
    """The typed `surface: { target }` declaration of the meta object."""
    block = extract_brace_block(sanitize_meta_source(meta_text), "surface")
    return extract_string_property(block, "target") if block else None


def resolve_app_target_in_scope(
    folder: Path, files: dict[str, Path | None]
) -> bool:
    """Whether an app target is in scope for app-only checks.

    Prefers the typed meta `surface.target` (app/hybrid in scope, web/package
    not); metas without one fall back to the legacy PRODUCTION_HANDOFF
    Target Surfaces prose parse.
    """
    meta_path = files.get("meta")
    if meta_path is not None and meta_path.is_file():
        target = extract_meta_surface_target(read(meta_path))
        if target in ("app", "hybrid"):
            return True
        if target in ("web", "package"):
            return False
    handoff = folder / "docs" / "PRODUCTION_HANDOFF.md"
    return handoff.is_file() and app_target_in_scope(read(handoff))


VIEWPORT_FORM_FACTORS = ("phone", "tablet", "desktop")
VIEWPORT_SIDE_MIN = 240
VIEWPORT_SIDE_MAX = 3840


def validate_flow_viewport(
    files: dict[str, Path | None],
    errors: list[str],
    warnings: list[str],
    handoff_ready: bool,
) -> None:
    """Type/range checks for declared viewports; silence for legacy flows.

    A declared flow viewport must name a known formFactor and keep both sides
    within the accepted range (errors). A flow that declares a viewport while
    its Static Flow export never reads Flow.viewport is half-converted and
    would still render phone frames (warning; --strict-style promotes). Flows
    declaring nothing skip every check, except a --handoff-ready reminder that
    consumers will assume phone 375x812.
    """
    flow_path = files.get("flow")
    if flow_path is None or not flow_path.is_file():
        return
    flow_text = read(flow_path)
    viewport = extract_flow_viewport(flow_text)

    if viewport is not None:
        check(
            viewport["formFactor"] in VIEWPORT_FORM_FACTORS,
            "flow viewport formFactor must be one of phone, tablet, desktop "
            f"(got {viewport['formFactor']!r})",
            errors,
        )
        for side in ("width", "height"):
            value = viewport[side]
            check(
                value is not None
                and VIEWPORT_SIDE_MIN <= value <= VIEWPORT_SIDE_MAX,
                f"flow viewport {side} must be an integer within "
                f"{VIEWPORT_SIDE_MIN}-{VIEWPORT_SIDE_MAX} (got {value!r})",
                errors,
            )
        export_path = files.get("static flow export")
        # Code-shaped reference (`<camel>Flow.viewport`), so a template comment
        # that merely mentions Flow.viewport cannot satisfy the check.
        if (
            export_path is not None
            and export_path.is_file()
            and re.search(r"\w+Flow\.viewport", read(export_path)) is None
        ):
            warnings.append(
                "flow declares a viewport but the Static Flow export never reads "
                "Flow.viewport, so it still renders the baked-in phone frames; "
                "re-scaffold the export or port the runtime viewport read"
            )
    elif handoff_ready:
        warnings.append(
            "flow declares no viewport; downstream consumers assume phone "
            "375x812 — declare flow.viewport (or scaffold with --viewport) "
            "if this product is reviewed at another size"
        )

    for obj in split_top_level_objects(extract_array_body(flow_text, "Routes")):
        route_viewport = extract_route_viewport(obj)
        if route_viewport is None:
            continue
        route_id = extract_string_property(obj, "id") or "?"
        for side in ("width", "height"):
            value = route_viewport[side]
            check(
                value is not None
                and VIEWPORT_SIDE_MIN <= value <= VIEWPORT_SIDE_MAX,
                f"route '{route_id}' viewport {side} must be an integer within "
                f"{VIEWPORT_SIDE_MIN}-{VIEWPORT_SIDE_MAX} (got {value!r})",
                errors,
            )


def validate_surface_viewport_alignment(
    files: dict[str, Path | None], warnings: list[str]
) -> None:
    """--handoff-ready nudge: a web-only product reviewed in phone frames.

    Fires only when the meta declares surface.target web AND the resolved
    formFactor is phone (declared phone, or undeclared and therefore implicit
    phone). Warning-level: mobile-first web is a legitimate choice — the
    point is to make it a deliberate one.
    """
    meta_path = files.get("meta")
    if meta_path is None or not meta_path.is_file():
        return
    if extract_meta_surface_target(read(meta_path)) != "web":
        return
    flow_path = files.get("flow")
    viewport = (
        extract_flow_viewport(read(flow_path))
        if flow_path is not None and flow_path.is_file()
        else None
    )
    form_factor = viewport["formFactor"] if viewport else "phone"
    if form_factor == "phone":
        warnings.append(
            "Target surface is web-only but the primary review viewport "
            "resolves to phone (375x812); confirm mobile-first is intentional "
            "or re-scaffold with --viewport desktop or tablet"
        )


def validate_transition_presentation(
    folder: Path, files: dict[str, Path | None], errors: list[str]
) -> None:
    """Require explicit navigation and motion at handoff, on every platform."""
    flow_path = files.get("flow")
    if flow_path is None or not flow_path.is_file():
        return
    flow_text = read(flow_path)
    route_ids = set(
        extract_const_string_array(flow_text, "RouteIds")
        + extract_object_array_ids(flow_text, "Routes")
    )
    app_target = resolve_app_target_in_scope(folder, files)
    flow_doc = folder / "docs" / "FLOW_SPEC.md"
    flow_prose = mask_code_fences(read(flow_doc)) if flow_doc.is_file() else ""
    flow_prose = re.sub(r"(`+).*?\1", "", flow_prose, flags=re.DOTALL)
    for index, transition in enumerate(extract_transition_objects(flow_text), start=1):
        label = extract_string_property(transition, "trigger") or f"#{index}"
        is_return = extract_string_property(transition, "kind") == "return"
        visible_target = extract_string_property(transition, "to") in route_ids
        if not is_return and (app_target or visible_target):
            check(
                extract_string_property(transition, "presentation") in TRANSITION_PRESENTATION_VALUES,
                f"transition {label} needs an explicit presentation; do not infer push",
                errors,
            )
        if not visible_target:
            continue
        if is_return:
            check(
                extract_string_property(transition, "backBehavior") in TRANSITION_BACK_BEHAVIOR_VALUES,
                f"return transition {label} needs explicit backBehavior; do not infer pop",
                errors,
            )
        motion = extract_string_property(transition, "motion")
        check(motion in TRANSITION_MOTION_VALUES, f"transition {label} needs explicit motion (none/platform-default/custom)", errors)
        if motion == "custom":
            reference = extract_string_property(transition, "motionRef") or ""
            match = re.fullmatch(r"FLOW_SPEC\.md#([A-Za-z0-9_-]+)", reference)
            anchor = match.group(1) if match else None
            exists = bool(anchor and (
                re.search(rf'<a\s+(?:id|name)=["\']{re.escape(anchor)}["\'][^>]*>', flow_prose)
            ))
            check(exists, f"transition {label} custom motionRef must resolve to an explicit FLOW_SPEC.md#anchor", errors)


def validate_component_usage(
    folder: Path,
    files: dict[str, Path | None],
    warnings: list[str],
    framework: str = "react",
) -> None:
    component_label = FRAMEWORK_FILE_PATTERNS[framework]["component"]
    ui_spec = folder / "docs" / "UI_SPEC.md"
    component_path = files.get("component")
    if not ui_spec.is_file() or component_path is None or not component_path.is_file():
        return

    spec_text = read(ui_spec)
    map_section = extract_doc_section(spec_text, "Component Map")
    gaps_section = extract_doc_section(spec_text, "Component Gaps")
    if not map_section and not gaps_section:
        return

    # Bracketed spans are unresolved scaffold guidance, not real mappings.
    resolved_map = re.sub(r"\[[^\]\n]*\]", "", map_section)
    mapped_names = unique(COMPONENT_NAME_PATTERN.findall(resolved_map))

    component_text = read(component_path)
    # Type-only imports carry no value binding, so they never satisfy a
    # Component Map entry.
    value_import_text = re.sub(r"import\s+type\b[^;]*;", "", component_text)
    imported_clauses = " ".join(IMPORT_CLAUSE_PATTERN.findall(value_import_text))
    import_specifiers = IMPORT_PATTERN.findall(value_import_text)
    for name in mapped_names:
        name_pattern = rf"\b{re.escape(name)}\b"
        imported = re.search(name_pattern, imported_clauses) is not None or any(
            re.search(name_pattern, specifier.rsplit("/", 1)[-1])
            for specifier in import_specifiers
        )
        check(
            imported,
            f"UI_SPEC Component Map names `{name}` but {component_label} never imports it",
            warnings,
        )
        check(
            re.search(rf"<(?:\w+\.)?{re.escape(name)}[\s/>]", component_text)
            is not None,
            f"UI_SPEC Component Map names `{name}` but {component_label} never renders it",
            warnings,
        )

    has_no_reusable_marker = NO_REUSABLE_PATTERN.search(gaps_section) is not None

    def is_design_system_import(specifier: str) -> bool:
        if specifier.endswith(".css"):
            return False
        if not specifier.startswith("."):
            if framework == "vue":
                if specifier in {"vue", "clsx", "classnames"}:
                    return False
                return not specifier.startswith(("@storybook", "@vue/", "vue/"))
            if specifier in {"react", "react-dom", "clsx", "classnames"}:
                return False
            return not specifier.startswith(("@storybook", "react/", "react-dom/"))
        if "prototypeFlowLayout" in specifier:
            return False
        return "/components/" in specifier or "/ui/" in specifier or specifier.startswith("../..")

    has_design_system_import = any(
        is_design_system_import(specifier)
        for specifier in IMPORT_PATTERN.findall(component_text)
    )

    check(
        bool(mapped_names) or has_no_reusable_marker,
        "UI_SPEC Component Map has no resolved component mappings and Component Gaps "
        "lacks a '- No reusable components: <evidence>' line",
        warnings,
    )
    check(
        has_design_system_import or has_no_reusable_marker,
        f"{component_label} has no design-system import and Component Gaps lacks a "
        "'- No reusable components: <evidence>' line",
        warnings,
    )


def validate_css(files: dict[str, Path | None], warnings: list[str]) -> None:
    css_path = files.get("css")
    if css_path is None or not css_path.is_file():
        return

    text = read(css_path)

    # Collapse var() fallbacks (innermost first) so raw values are legal only
    # in fallback position; anything left is a hardcoded style. Comments are
    # replaced newline-for-newline so warning line numbers stay accurate.
    collapsed = re.sub(
        r"/\*.*?\*/",
        lambda match: "\n" * match.group(0).count("\n"),
        text,
        flags=re.DOTALL,
    )
    while True:
        reduced = VAR_FALLBACK_PATTERN.sub(r"var(\1)", collapsed)
        if reduced == collapsed:
            break
        collapsed = reduced

    for line_number, line in enumerate(collapsed.splitlines(), start=1):
        if COLOR_LITERAL_PATTERN.search(line):
            warnings.append(
                f"{css_path.name}:{line_number} hardcoded color outside a var() "
                "token fallback"
            )

    selectors: list[str] = []
    selector_buffer = ""
    keyframes_depth = 0
    pending_keyframes = False
    for raw_line in collapsed.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if pending_keyframes:
            if "{" in line:
                pending_keyframes = False
                keyframes_depth = max(line.count("{") - line.count("}"), 0)
            continue
        if keyframes_depth > 0:
            keyframes_depth = max(
                keyframes_depth + line.count("{") - line.count("}"), 0
            )
            continue
        if line.startswith("@keyframes"):
            if "{" in line:
                keyframes_depth = max(line.count("{") - line.count("}"), 0)
            else:
                pending_keyframes = True
            continue
        if line.startswith("@"):
            continue
        if "{" in line:
            selector_list = (selector_buffer + " " + line.split("{", 1)[0]).strip()
            selector_buffer = ""
            selectors.extend(
                selector.strip()
                for selector in selector_list.split(",")
                if selector.strip()
            )
        elif ";" in line or "}" in line:
            selector_buffer = ""
        elif line.endswith(",") or line.startswith((".", "[", ":", "&")):
            selector_buffer += " " + line
        else:
            selector_buffer = ""

    # Every selector must be scoped under one of the file's feature root blocks
    # (a leading class stripped of its BEM __element / --modifier suffixes).
    root_blocks: list[str] = []
    for selector in selectors:
        leading_class = re.match(r"\.([A-Za-z][A-Za-z0-9_-]*)", selector)
        if leading_class:
            block = re.split(r"__|--", leading_class.group(1))[0]
            if block and f".{block}" not in root_blocks:
                root_blocks.append(f".{block}")
    root_hint = root_blocks[0] if root_blocks else f".{css_path.stem}"

    for selector in selectors:
        if not selector.startswith(tuple(root_blocks) or (root_hint,)):
            warnings.append(
                f"{css_path.name} selector '{selector}' is not scoped under a "
                f"feature root class such as '{root_hint}'"
            )


def find_with_convention_fallback(
    folder: Path,
    label: str,
    preferred: str,
    fallback: str,
    warnings: list[str],
) -> Path | None:
    """Locate a file, tolerating a non-conforming name instead of going quiet.

    Every doc/code cross-check keys off these paths and returns early when one
    is ``None``. Without a fallback a prototype that named its flow file
    ``featureFlow.ts`` instead of ``featurePrototypeFlow.ts`` loses the whole
    cross-check suite and reports *fewer* problems than a conforming one — the
    output ends up anti-correlated with quality. Take the file, and say so.
    """
    path = find_one(folder, preferred)
    if path is not None:
        return path
    path = find_one(folder, fallback)
    if path is not None:
        warnings.append(
            f"{path.name} does not follow the {preferred} naming convention; "
            f"cross-checks ran against it, but rename it so tooling keyed on "
            f"the convention keeps finding it"
        )
    return path


def validate_files(
    folder: Path,
    errors: list[str],
    framework: str = "react",
    warnings: list[str] | None = None,
) -> dict[str, Path | None]:
    warnings = warnings if warnings is not None else []
    patterns = FRAMEWORK_FILE_PATTERNS[framework]
    files = {
        "component": find_one(folder, patterns["component"]),
        "story": find_one(folder, patterns["story"]),
        "static flow export": find_one(folder, patterns["static flow export"]),
        "static flow story": find_one(folder, patterns["static flow story"]),
        "flow": find_with_convention_fallback(
            folder, "flow", "*PrototypeFlow.ts", "*Flow.ts", warnings
        ),
        "data": find_with_convention_fallback(
            folder, "data", "*PrototypeData.ts", "*Data.ts", warnings
        ),
        "meta": find_with_convention_fallback(
            folder, "meta", "*PrototypeMeta.ts", "*Meta.ts", warnings
        ),
        "css": find_one(folder, "*-prototype.css"),
        "flow layout helper": folder.parent / "prototypeFlowLayout.ts",
        "index": folder / "index.ts",
    }

    for label, path in files.items():
        check(path is not None and path.is_file(), f"missing {label} file", errors)

    return files


def validate_story(path: Path | None, errors: list[str]) -> None:
    if path is None or not path.is_file():
        return
    text = read(path)
    check("parameters" in text, "story missing parameters", errors)
    check("prototype:" in text, "story missing parameters.prototype", errors)
    check('layout: "fullscreen"' in text or "layout: 'fullscreen'" in text, "story should use fullscreen layout", errors)


def validate_static_flow_story(path: Path | None, errors: list[str]) -> None:
    if path is None or not path.is_file():
        return
    text = read(path)
    check("StaticFlow" in text, "static flow story should export StaticFlow", errors)
    check("parameters" in text, "static flow story missing parameters", errors)
    check("prototype:" in text, "static flow story missing parameters.prototype", errors)
    check(
        'layout: "fullscreen"' in text or "layout: 'fullscreen'" in text,
        "static flow story should use fullscreen layout",
        errors,
    )


def validate_static_flow_export(path: Path | None, errors: list[str]) -> None:
    if path is None or not path.is_file():
        return
    text = read(path)
    check("../prototypeFlowLayout" in text, "static flow export should import shared prototypeFlowLayout helper", errors)
    check("readPrototypeFlowLayoutPositions" in text, "static flow export should read saved inspector layout positions", errors)
    check("getPrototypeFlowLayoutStorageKey" in text, "static flow export should use the shared layout storage key", errors)
    check("isFlowPreview" in text, "static flow export should render route previews in flow preview mode", errors)
    check("data-layout-source" in text, "static flow export should expose data-layout-source", errors)
    check("data-figma-text-auto-width" in text, "static flow export should mark edge labels for Figma text auto-width", errors)


def validate_viewer_compatibility(files: dict[str, Path | None], errors: list[str]) -> None:
    component_path = files.get("component")
    story_path = files.get("story")
    component_text = ""
    if component_path is not None and component_path.is_file():
        component_text = read(component_path)
    text = component_text
    if story_path is not None and story_path.is_file():
        text += "\n" + read(story_path)
    if component_text:
        check(
            "!isEmbeddedFlowPreview" in component_text,
            "prototype must hide its own chrome (header/route nav) in flow preview mode via !isEmbeddedFlowPreview",
            errors,
        )

    check(
        "prototypeFlowPreview" in text,
        "prototype should support prototypeFlowPreview query mode for iframe previews",
        errors,
    )
    check(
        "prototypeRoute" in text,
        "prototype should support prototypeRoute query mode for route-specific iframe previews",
        errors,
    )
    check(
        "data-prototype-root" in text,
        "prototype root should keep data-prototype-root for backward-compatible UI Flow preview measurement",
        errors,
    )
    check(
        "data-prototype-route-preview" in text,
        "prototype route shell should expose data-prototype-route-preview for template-compatible preview measurement",
        errors,
    )


def validate_meta(path: Path | None, errors: list[str]) -> None:
    if path is None or not path.is_file():
        return
    text = read(path)
    for doc_name in [
        "ACCEPTANCE",
        "DATA_SPEC",
        "FLOW_SPEC",
        "IMPLEMENTATION_GUIDE",
        "PRD",
        "PRODUCTION_HANDOFF",
        "UI_SPEC",
    ]:
        check(doc_name in text, f"meta missing raw import for docs/{doc_name}.md", errors)
    check("flow:" in text, "meta missing flow field", errors)
    check("data:" in text, "meta missing data field", errors)
    check("docs:" in text, "meta missing docs field", errors)
    check("figmaExport" in text, "meta missing figmaExport field", errors)
    check("flowStoryId" in text, "meta missing figmaExport.flowStoryId", errors)


def validate_components_meta(
    folder: Path,
    files: dict[str, Path | None],
    errors: list[str],
    warnings: list[str],
    handoff_ready: bool = False,
    storybook_index: Path | None = None,
) -> None:
    """Check the optional meta.components per-route composition block.

    Every check here is a warning by default (--strict-style promotes them);
    only the Storybook index storyId existence check becomes an error under
    --handoff-ready.
    """
    meta_path = files.get("meta")
    if meta_path is None or not meta_path.is_file():
        return
    meta_text = sanitize_meta_source(read(meta_path))
    components_block = extract_brace_block(meta_text, "components")
    if not components_block:
        warnings.append("meta has no components section")
        return

    flow_path = files.get("flow")
    route_ids: list[str] = []
    if flow_path is not None and flow_path.is_file():
        route_ids = extract_flow_screen_ids(read(flow_path))
    if route_ids:
        for route_id in COMPONENT_ROUTE_PATTERN.findall(components_block):
            check(
                route_id in route_ids,
                f"meta components route '{route_id}' is not a known flow route id",
                warnings,
            )

    for origin in COMPONENT_ORIGIN_PATTERN.findall(components_block):
        check(
            origin in COMPONENT_ORIGIN_VALUES,
            f"meta components origin '{origin}' is not one of shared|local|promoted",
            warnings,
        )

    component_names: list[str] = []
    for index, entry in enumerate(extract_component_entries(components_block), start=1):
        name = extract_string_property(entry, "name")
        origin = extract_string_property(entry, "origin")
        if name:
            component_names.append(name)
        if origin in {"promoted", "shared"}:
            check(
                extract_string_property(entry, "importPath") is not None
                or extract_string_property(entry, "storyId") is not None,
                f"meta components entry `{name or f'#{index}'}` has origin "
                f"'{origin}' but neither importPath nor storyId",
                warnings,
            )

    ui_spec = folder / "docs" / "UI_SPEC.md"
    if component_names and ui_spec.is_file():
        spec_text = read(ui_spec)
        doc_sections = extract_doc_section(
            spec_text, "Component Map"
        ) + extract_doc_section(spec_text, "Component Gaps")
        if doc_sections.strip():
            for name in unique(component_names):
                check(
                    name in doc_sections,
                    f"meta components names `{name}` but UI_SPEC.md Component Map/"
                    "Component Gaps sections never mention it",
                    warnings,
                )

    if storybook_index is not None:
        index_ids = load_storybook_index_ids(storybook_index)
        if index_ids is None:
            warnings.append(
                f"cannot read Storybook index at {storybook_index}, so meta "
                "components storyId values were not verified"
            )
        else:
            for story_id in unique(
                COMPONENT_STORY_ID_PATTERN.findall(components_block)
            ):
                check(
                    story_id in index_ids,
                    f"meta components storyId '{story_id}' does not exist in the "
                    "Storybook index",
                    errors if handoff_ready else warnings,
                )


def validate_flow(path: Path | None, errors: list[str]) -> None:
    if path is None or not path.is_file():
        return
    text = read(path)
    check("RouteIds" in text, "flow file missing route id array", errors)
    check("Routes" in text, "flow file missing routes metadata", errors)
    check("Transitions" in text, "flow file missing transitions metadata", errors)
    check("sourceAnchor" in text, "flow transition type should include optional sourceAnchor for export layout tuning", errors)
    route_ids = extract_const_string_array(text, "RouteIds")
    flow_node_ids = extract_const_string_array(text, "FlowNodeIds")
    all_ids = route_ids + flow_node_ids
    duplicate_ids = sorted({value for value in all_ids if all_ids.count(value) > 1})

    check(bool(route_ids), "flow file should include at least one stable route id string", errors)
    check(not duplicate_ids, f"flow ids must be unique: {', '.join(duplicate_ids)}", errors)

    for route_id in route_ids:
        check(
            re.fullmatch(r"[a-z0-9][a-z0-9-]*", route_id) is not None,
            f"route id '{route_id}' should be lowercase kebab-case",
            errors,
        )

    for node_id in flow_node_ids:
        check(
            re.fullmatch(r"[a-z0-9][a-z0-9-]*", node_id) is not None,
            f"flow node id '{node_id}' should be lowercase kebab-case",
            errors,
        )

    transitions = extract_transition_objects(text)
    # A transition may target any screen the flow metadata actually declares.
    # Some prototypes keep two id layers on purpose — navigation route ids for
    # the component's own routing, and finer board-screen ids for the UI Flow
    # cards the Inspector renders from `flow.routes[].id`. Only reading the
    # `*RouteIds` / `*FlowNodeIds` string arrays would reject every edge drawn
    # between board screens.
    valid_targets = set(extract_flow_screen_ids(text))

    check(
        len(all_ids) <= 1 or bool(transitions),
        "flow with multiple routes or nodes should include transition metadata",
        errors,
    )

    has_key_flow_line = False
    for index, transition in enumerate(transitions, start=1):
        from_id = extract_string_property(transition, "from")
        to_id = extract_string_property(transition, "to")
        trigger = extract_string_property(transition, "trigger")
        label = extract_string_property(transition, "label")
        flow_line = extract_string_property(transition, "flowLine")
        transition_label = trigger or label or f"#{index}"

        check(bool(from_id), f"transition {transition_label} missing from", errors)
        check(bool(to_id), f"transition {transition_label} missing to", errors)
        check(bool(trigger), f"transition {transition_label} missing trigger", errors)
        check(bool(label), f"transition {transition_label} missing label", errors)

        if from_id:
            check(
                from_id in valid_targets,
                f"transition {transition_label} has unknown from target '{from_id}'",
                errors,
            )
        if to_id:
            check(
                to_id in valid_targets,
                f"transition {transition_label} has unknown to target '{to_id}'",
                errors,
            )
        if flow_line:
            check(
                flow_line in {"key", "reference", "hidden"},
                f"transition {transition_label} has invalid flowLine '{flow_line}'",
                errors,
            )
            has_key_flow_line = has_key_flow_line or flow_line == "key"

        presentation = extract_string_property(transition, "presentation")
        if presentation:
            check(
                presentation in TRANSITION_PRESENTATION_VALUES,
                f"transition {transition_label} has invalid presentation "
                f"'{presentation}' (expected push|modal|sheet|fullscreen|replace)",
                errors,
            )
        back_behavior = extract_string_property(transition, "backBehavior")
        if back_behavior:
            check(
                back_behavior in TRANSITION_BACK_BEHAVIOR_VALUES,
                f"transition {transition_label} has invalid backBehavior "
                f"'{back_behavior}' (expected pop|popToRoot|dismiss|none)",
                errors,
            )

    check(
        not transitions or has_key_flow_line,
        'flow with transitions should mark at least one transition as flowLine: "key"',
        errors,
    )


MANIFEST_NAME = "HANDOFF_MANIFEST.json"
MANIFEST_SCHEMA_VERSION = 2


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_docs_hashes(folder: Path) -> dict[str, str]:
    """sha256 per handoff document, manifest itself excluded."""
    docs_dir = folder / "docs"
    hashes: dict[str, str] = {}
    for doc_name in REQUIRED_DOCS:
        doc_path = docs_dir / doc_name
        if doc_path.is_file():
            hashes[doc_name] = sha256_text(read(doc_path))
    return hashes


def compute_artifact_hashes(folder: Path) -> dict[str, str]:
    """Hash handoff bytes, including carriers whose ids or counts can stay unchanged."""
    paths = {folder / "docs" / name for name in REQUIRED_DOCS}
    paths.update(folder / "docs" / name for name in ("flow.json", "TOKENS.json"))
    for suffix in ("Flow", "Data", "Meta"):
        canonical = list(folder.glob(f"*Prototype{suffix}.ts"))
        paths.update(canonical or folder.glob(f"*{suffix}.ts"))
    paths.update((folder / "fixtures").glob("*.json"))
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths) if path.is_file()
    }


def docs_digest(docs_hashes: dict[str, str]) -> str:
    """Stable digest of the whole docs hash object; the hash the receiving
    frontend-product-implementation pass records as the consumed version."""
    return sha256_text(json.dumps(docs_hashes, sort_keys=True))


def write_handoff_manifest(
    folder: Path, files: dict[str, Path | None], changelog_summary: str | None
) -> Path:
    """Write docs/HANDOFF_MANIFEST.json after a fully passing --handoff-ready run.

    The manifest is the versioned snapshot the receiving implementation pins:
    per-doc hashes for drift detection, flow/fixture snapshots for coverage
    audits, and an incrementing changelog so a consumed version is nameable.
    """
    docs_dir = folder / "docs"
    docs_hashes = compute_docs_hashes(folder)
    artifact_hashes = compute_artifact_hashes(folder)

    route_ids: list[str] = []
    flow_node_ids: list[str] = []
    transition_count = 0
    flow_path = files.get("flow")
    if flow_path is not None and flow_path.is_file():
        flow_text = read(flow_path)
        route_ids = extract_const_string_array(flow_text, "RouteIds")
        flow_node_ids = extract_const_string_array(flow_text, "FlowNodeIds")
        transition_count = len(extract_transition_objects(flow_text))

    fixture_exports: list[str] = []
    data_path = files.get("data")
    if data_path is not None and data_path.is_file():
        fixture_exports = sorted(
            set(EXPORT_CONST_PATTERN.findall(sanitize_meta_source(read(data_path))))
        )

    handoff_path = docs_dir / "PRODUCTION_HANDOFF.md"
    handoff_text = read(handoff_path) if handoff_path.is_file() else ""
    review_section = extract_doc_section(handoff_text, "Review Status")
    review_status: dict[str, str | None] = {"status": "unknown", "confirmedOn": None}
    status_match = re.search(
        r"^\s*[-*]\s*Status\s*:\s*(.+)$", review_section, re.MULTILINE
    )
    if status_match:
        review_status["status"] = status_match.group(1).strip().strip("`")
    confirmed_match = re.search(
        r"^\s*[-*]\s*Confirmed on\s*:\s*(.+)$", review_section, re.MULTILINE
    )
    if confirmed_match:
        review_status["confirmedOn"] = confirmed_match.group(1).strip()

    review_status["confirmedBy"] = doc_field(review_section, "Confirmed by") or None
    review_status["scope"] = doc_field(review_section, "Scope") or None

    manifest_path = docs_dir / MANIFEST_NAME
    previous_changelog: list[dict] = []
    if manifest_path.is_file():
        try:
            previous = json.loads(read(manifest_path))
        except json.JSONDecodeError:
            previous = None
        if isinstance(previous, dict) and isinstance(previous.get("changelog"), list):
            previous_changelog = [
                entry for entry in previous["changelog"] if isinstance(entry, dict)
            ]

    version = 1
    if previous_changelog:
        version = (
            max(int(entry.get("version", 0)) for entry in previous_changelog) + 1
        )
    summary = changelog_summary or "regenerated"
    changelog = previous_changelog + [
        {"version": version, "date": date.today().isoformat(), "summary": summary}
    ]

    manifest = {
        "manifestSchemaVersion": MANIFEST_SCHEMA_VERSION,
        "feature": folder.name,
        "generatedAt": date.today().isoformat(),
        "reviewStatus": review_status,
        "docs": docs_hashes,
        "docsDigest": docs_digest(docs_hashes),
        "artifacts": artifact_hashes,
        "artifactsDigest": docs_digest(artifact_hashes),
        "flow": {
            "routeIds": route_ids,
            "flowNodeIds": flow_node_ids,
            "transitionCount": transition_count,
        },
        "fixtures": {"exports": fixture_exports},
        "scopeDigest": sha256_text(
            extract_doc_section(handoff_text, "Prototype To Frontend Map")
        ),
        "changelog": changelog,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    return manifest_path


def run_verify_manifest(folder: Path) -> int:
    """Verify the full published artifact set; a hash match is not semantic review."""
    path = folder / "docs" / MANIFEST_NAME
    if not path.is_file():
        print(f"No {MANIFEST_NAME} found in {folder / 'docs'}; run --handoff-ready first.")
        return 1
    try:
        manifest = json.loads(read(path), object_pairs_hook=unique_json_object)
    except ValueError as exc:
        print(f"{MANIFEST_NAME} is not valid JSON: {exc}")
        return 1
    if not isinstance(manifest, dict) or type(manifest.get("manifestSchemaVersion")) is not int or manifest.get("manifestSchemaVersion") != MANIFEST_SCHEMA_VERSION:
        print(f"{MANIFEST_NAME} lacks supported v2 carrier integrity coverage; review and republish with --handoff-ready.")
        return 1
    for key, digest_key in (("docs", "docsDigest"), ("artifacts", "artifactsDigest")):
        recorded = manifest.get(key)
        if not isinstance(recorded, dict) or not recorded or not all(
            isinstance(name, str) and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for name, value in recorded.items()
        ) or manifest.get(digest_key) != docs_digest(recorded):
            print(f"{MANIFEST_NAME} has an invalid {key} hash object or {digest_key}; review and republish.")
            return 1
    recorded = manifest["artifacts"]
    current = compute_artifact_hashes(folder)
    changes = [f"missing: {name}" for name in sorted(recorded.keys() - current.keys())]
    changes += [f"added: {name}" for name in sorted(current.keys() - recorded.keys())]
    changes += [f"drifted: {name}" for name in sorted(current.keys() & recorded.keys()) if current[name] != recorded[name]]
    current_docs = compute_docs_hashes(folder)
    if current_docs != manifest["docs"]:
        changes.append("document hash snapshot differs")
    if not changes:
        print(f"Handoff artifacts match {MANIFEST_NAME}; no drift. Source truth and semantic review are separate checks.")
        return 0
    print(f"Handoff drift detected against {MANIFEST_NAME}:")
    for change in changes:
        print(f"- {change}")
    print("Review affected decisions and related artifacts before republishing with --handoff-ready --changelog.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prototype_folder", help="Path to a generated prototype folder.")
    parser.add_argument(
        "--handoff-ready",
        dest="handoff_ready",
        action="store_true",
        help=(
            "Also fail docs that still contain scaffold placeholder guidance, "
            "cross-check doc route/fixture references against the flow and data "
            "files, and require a confirmed Review Status."
        ),
    )
    parser.add_argument(
        "--production-ready",
        dest="handoff_ready",
        action="store_true",
        help="Deprecated alias for --handoff-ready.",
    )
    parser.add_argument(
        "--strict-style",
        dest="strict_style",
        action="store_true",
        help=(
            "Treat validation warnings (component map, token discipline, CSS "
            "scope, doc coverage, meta.components composition) as errors."
        ),
    )
    parser.add_argument(
        "--storybook-index",
        type=Path,
        default=None,
        help=(
            "Path to a Storybook index.json used to verify meta components "
            "storyId values (warnings by default, errors with --handoff-ready)."
        ),
    )
    parser.add_argument(
        "--framework",
        choices=("auto", "react", "vue"),
        default="auto",
        help=(
            "Prototype framework. auto classifies the folder from its component "
            "file (*Prototype.vue vs *Prototype.tsx)."
        ),
    )
    parser.add_argument(
        "--verify-manifest",
        dest="verify_manifest",
        action="store_true",
        help=(
            "Compare current handoff docs against docs/HANDOFF_MANIFEST.json and "
            "exit non-zero listing drifted or missing documents. Runs instead of "
            "the normal validation."
        ),
    )
    parser.add_argument(
        "--changelog",
        default=None,
        help=(
            "Changelog summary recorded in docs/HANDOFF_MANIFEST.json when a "
            "passing --handoff-ready run writes or regenerates the manifest."
        ),
    )
    args = parser.parse_args()

    folder = Path(args.prototype_folder).resolve()
    if args.verify_manifest:
        return run_verify_manifest(folder)

    errors: list[str] = []
    warnings: list[str] = []
    files: dict[str, Path | None] = {}

    check(folder.is_dir(), f"{folder} is not a directory", errors)
    if folder.is_dir():
        framework = args.framework
        if framework == "auto":
            framework, detection_error = detect_prototype_framework(folder)
            if framework == "mixed":
                errors.append(detection_error or "folder mixes prototype frameworks")

        if framework == "mixed":
            validate_docs(folder, errors, warnings, args.handoff_ready)
        else:
            validate_docs(folder, errors, warnings, args.handoff_ready)
            files = validate_files(folder, errors, framework, warnings)
            validate_data_authority(folder, files, errors, warnings, args.handoff_ready)
            validate_story(files["story"], errors)
            validate_static_flow_story(files["static flow story"], errors)
            validate_static_flow_export(files["static flow export"], errors)
            validate_viewer_compatibility(files, errors)
            validate_meta(files["meta"], errors)
            validate_flow(files["flow"], errors)
            validate_flow_viewport(files, errors, warnings, args.handoff_ready)
            validate_component_usage(folder, files, warnings, framework)
            validate_components_meta(
                folder,
                files,
                errors,
                warnings,
                args.handoff_ready,
                args.storybook_index,
            )
            validate_css(files, warnings)
            if args.handoff_ready:
                validate_doc_code_consistency(folder, files, errors, warnings)
                validate_fixture_json_consistency(folder, files, errors, warnings)
                validate_transition_presentation(folder, files, errors)
                validate_surface_viewport_alignment(files, warnings)

    if args.strict_style:
        errors.extend(warnings)
        warnings = []

    if warnings:
        print("Prototype validation warnings (errors with --strict-style):")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("Prototype validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.handoff_ready and folder.is_dir():
        manifest_path = write_handoff_manifest(folder, files, args.changelog)
        print(f"Wrote docs/{manifest_path.name} (handoff snapshot for drift detection).")

    print("Prototype validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
