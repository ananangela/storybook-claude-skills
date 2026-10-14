#!/usr/bin/env python3
"""Export a prototype's UI Flow as platform-neutral JSON and native navigation skeletons.

Reads a prototype folder's ``*PrototypeFlow.ts`` and writes ``docs/flow.json``:
the routes, flow-only nodes, and transitions with their navigation semantics
(``params``, ``deepLink``, ``presentation``, ``backBehavior``) and without the
canvas layout fields (``flowPosition``, ``sourceAnchor``, ``flowLine``), which
mean nothing outside the Storybook UI Flow board. When the flow declares a
viewport, the document carries it too — a top-level ``viewport`` object
(``formFactor``, ``width``, ``height``) plus per-route ``viewport`` overrides.
The viewport is product semantics (which device class the flow was designed
and reviewed at), not canvas layout, so it is exported rather than stripped;
flows without one omit the key entirely and consumers assume phone 375x812.

With ``--swift`` / ``--kotlin`` it also generates navigation skeletons — a Swift
route enum and a Kotlin sealed class — so a native implementation starts from
the flow contract instead of hand-translating TypeScript. The skeletons are
scaffolding to adapt into the app's existing router, not finished navigation.

Parsing reuses validate_prototype.py's helpers so both tools agree on what the
flow file says. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_prototype import (  # noqa: E402
    extract_array_body,
    extract_flow_viewport,
    extract_route_viewport,
    extract_string_property,
    extract_transition_objects,
    find_one,
    read,
    sanitize_meta_source,
    split_top_level_objects,
)

FLOW_SCHEMA_VERSION = 1

# Layout-only fields: meaningful on the UI Flow canvas, meaningless to a router.
LAYOUT_FIELDS = ("flowPosition", "sourceAnchor", "flowLine")

PARAM_TYPE_TO_SWIFT = {"string": "String", "number": "Double", "boolean": "Bool"}
PARAM_TYPE_TO_KOTLIN = {"string": "String", "number": "Double", "boolean": "Boolean"}

PRESENTATION_ORDER = ("push", "modal", "sheet", "fullscreen", "replace")
UNSPECIFIED_PRESENTATION = "unspecified (return edge — follow backBehavior)"


def to_pascal(route_id: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_]", route_id) if part)


def to_camel(route_id: str) -> str:
    pascal = to_pascal(route_id)
    return pascal[:1].lower() + pascal[1:] if pascal else pascal


def extract_params(object_text: str) -> list[dict[str, str]]:
    """``params: [{ name, type }]`` entries of one route object."""
    match = re.search(r"\bparams\s*:\s*\[", object_text)
    if not match:
        return []
    start = object_text.rindex("[", match.start(), match.end())
    from validate_prototype import scan_matching_bracket

    end = scan_matching_bracket(object_text, start)
    if end == -1:
        return []
    params: list[dict[str, str]] = []
    for entry in split_top_level_objects(object_text[start + 1 : end - 1]):
        name = extract_string_property(entry, "name")
        param_type = extract_string_property(entry, "type")
        if name:
            params.append({"name": name, "type": param_type or "string"})
    return params


def extract_objects(flow_text: str, suffix: str) -> list[str]:
    return split_top_level_objects(extract_array_body(flow_text, suffix))


def build_flow_document(flow_text: str, feature: str) -> dict:
    routes: list[dict] = []
    for obj in extract_objects(flow_text, "Routes"):
        route_id = extract_string_property(obj, "id")
        if not route_id:
            continue
        route: dict = {
            "id": route_id,
            "title": extract_string_property(obj, "title") or route_id,
        }
        # navigationId is optional in the source contract; fabricating it as a
        # copy of the id makes the JSON claim something the flow never said.
        for key in ("navigationId", "component", "description", "deepLink"):
            value = extract_string_property(obj, key)
            if value:
                route[key] = value
        params = extract_params(obj)
        if params:
            route["params"] = params
        route_viewport = extract_route_viewport(obj)
        if (
            route_viewport
            and route_viewport["width"] is not None
            and route_viewport["height"] is not None
        ):
            route["viewport"] = route_viewport
        routes.append(route)

    nodes: list[dict] = []
    for obj in extract_objects(flow_text, "FlowNodes"):
        node_id = extract_string_property(obj, "id")
        if not node_id:
            continue
        node: dict = {
            "id": node_id,
            "title": extract_string_property(obj, "title") or node_id,
            "shape": extract_string_property(obj, "shape") or "state",
        }
        for key in ("tone", "description"):
            value = extract_string_property(obj, key)
            if value:
                node[key] = value
        nodes.append(node)

    transitions: list[dict] = []
    for obj in extract_transition_objects(flow_text):
        from_id = extract_string_property(obj, "from")
        to_id = extract_string_property(obj, "to")
        if not from_id or not to_id:
            continue
        transition: dict = {
            "from": from_id,
            "to": to_id,
            "trigger": extract_string_property(obj, "trigger") or "",
            "label": extract_string_property(obj, "label") or "",
        }
        for key in ("kind", "presentation", "backBehavior", "motion", "motionRef", "note"):
            value = extract_string_property(obj, key)
            if value:
                transition[key] = value
        transitions.append(transition)

    document = {
        "flowSchemaVersion": FLOW_SCHEMA_VERSION,
        "feature": feature,
        "routes": routes,
        "nodes": nodes,
        "transitions": transitions,
    }
    flow_viewport = extract_flow_viewport(flow_text)
    if flow_viewport and all(value is not None for value in flow_viewport.values()):
        document["viewport"] = flow_viewport
    return document


def group_transitions_by_presentation(transitions: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group edges by presentation, keeping unspecified ones unasserted.

    A `return` edge may legitimately carry no presentation — the contract only
    requires it on non-`return` edges. Defaulting those to "push" would tell a
    native receiver to push a destination for what is actually a dismiss or a
    pop, so they get their own bucket labelled as unspecified instead.
    """
    grouped: dict[str, list[dict]] = {}
    for transition in transitions:
        grouped.setdefault(
            transition.get("presentation") or UNSPECIFIED_PRESENTATION, []
        ).append(transition)
    ordered = [(key, grouped[key]) for key in PRESENTATION_ORDER if key in grouped]
    ordered.extend(
        (key, value) for key, value in sorted(grouped.items()) if key not in PRESENTATION_ORDER
    )
    return ordered


def generated_header(feature: str, folder_name: str, comment: str = "//") -> list[str]:
    return [
        f"{comment} Generated by storybook-product-prototype/scripts/export_flow.py",
        f"{comment} Source: {feature} prototype flow metadata.",
        f"{comment} Regenerate: python3 export_flow.py {folder_name} --swift <path> --kotlin <path>",
        f"{comment} Navigation scaffolding to adapt into the app's router — not finished code.",
        "",
    ]


def render_swift(document: dict, folder_name: str) -> str:
    feature = to_pascal(document["feature"])
    lines = generated_header(document["feature"], folder_name)
    lines.append("import Foundation")
    lines.append("")

    deep_links = [route for route in document["routes"] if route.get("deepLink")]
    if deep_links:
        lines.append("// Deep links declared by the flow:")
        for route in deep_links:
            lines.append(f"//   {route['id']} -> {route['deepLink']}")
        lines.append("")

    lines.append(f"enum {feature}Route: Hashable {{")
    for route in document["routes"]:
        case_name = to_camel(route["id"])
        params = route.get("params") or []
        if params:
            arguments = ", ".join(
                f"{param['name']}: {PARAM_TYPE_TO_SWIFT.get(param['type'], 'String')}"
                for param in params
            )
            lines.append(f"    case {case_name}({arguments})")
        else:
            lines.append(f"    case {case_name}")
    lines.append("}")
    lines.append("")

    lines.append("// Navigation scaffold — transitions grouped by presentation:")
    for presentation, transitions in group_transitions_by_presentation(document["transitions"]):
        lines.append(f"//   {presentation}:")
        for transition in transitions:
            back = transition.get("backBehavior")
            suffix = f"  back: {back}" if back else ""
            for key in ("motion", "motionRef"):
                if transition.get(key):
                    suffix += f"  {key}: {transition[key]}"
            lines.append(
                f"//     {transition['from']} -> {transition['to']}"
                f"  trigger: {transition['trigger']}{suffix}"
            )
    if not document["transitions"]:
        lines.append("//   (no transitions declared)")
    lines.append("")
    return "\n".join(lines)


def render_kotlin(document: dict, folder_name: str) -> str:
    feature = to_pascal(document["feature"])
    lines = generated_header(document["feature"], folder_name)

    lines.append(f"sealed class {feature}Route(val route: String) {{")
    for route in document["routes"]:
        object_name = to_pascal(route["id"])
        params = route.get("params") or []
        if params:
            pattern = route["id"] + "".join(f"/{{{param['name']}}}" for param in params)
            arguments = ", ".join(
                f"val {param['name']}: {PARAM_TYPE_TO_KOTLIN.get(param['type'], 'String')}"
                for param in params
            )
            path = route["id"] + "".join(f"/${param['name']}" for param in params)
            lines.append(f'    data class {object_name}({arguments}) : {feature}Route("{path}") {{')
            lines.append(f'        companion object {{ const val PATTERN = "{pattern}" }}')
            lines.append("    }")
        else:
            # Plain `object`, not `data object`: the latter needs Kotlin 1.9+, and
            # generated scaffolding should compile in whatever the app is already on.
            lines.append(f'    object {object_name} : {feature}Route("{route["id"]}")')
    lines.append("}")
    lines.append("")

    deep_links = [route for route in document["routes"] if route.get("deepLink")]
    if deep_links:
        lines.append("// Deep links declared by the flow:")
        for route in deep_links:
            lines.append(f"//   {route['id']} -> {route['deepLink']}")
        lines.append("")

    lines.append("// NavHost scaffold — transitions grouped by presentation:")
    for presentation, transitions in group_transitions_by_presentation(document["transitions"]):
        lines.append(f"//   {presentation}:")
        for transition in transitions:
            back = transition.get("backBehavior")
            suffix = f"  back: {back}" if back else ""
            for key in ("motion", "motionRef"):
                if transition.get(key):
                    suffix += f"  {key}: {transition[key]}"
            lines.append(
                f"//     {transition['from']} -> {transition['to']}"
                f"  trigger: {transition['trigger']}{suffix}"
            )
    if not document["transitions"]:
        lines.append("//   (no transitions declared)")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prototype_folder", help="Path to a prototype folder.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for the flow JSON. Defaults to <folder>/docs/flow.json.",
    )
    parser.add_argument(
        "--swift",
        type=Path,
        default=None,
        help="Also write a Swift route enum and navigation scaffold to this path.",
    )
    parser.add_argument(
        "--kotlin",
        type=Path,
        default=None,
        help="Also write a Kotlin sealed route class and NavHost scaffold to this path.",
    )
    args = parser.parse_args()

    folder = Path(args.prototype_folder).resolve()
    if not folder.is_dir():
        print(f"{folder} is not a directory")
        return 1

    flow_path = find_one(folder, "*PrototypeFlow.ts") or find_one(folder, "*Flow.ts")
    if flow_path is None:
        print(
            f"No flow metadata found in {folder} (expected *PrototypeFlow.ts). "
            "Scaffold the prototype first or pass the folder that contains it."
        )
        return 1

    flow_text = sanitize_meta_source(read(flow_path))
    feature = re.sub(r"(Prototype)?Flow\.ts$", "", flow_path.name) or folder.name
    document = build_flow_document(flow_text, feature)

    if not document["routes"]:
        print(
            f"{flow_path.name} declares no routes; nothing to export. "
            "Add route metadata before exporting the flow."
        )
        return 1

    out_path = args.out or (folder / "docs" / "flow.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    print(
        f"Wrote {out_path} ({len(document['routes'])} routes, "
        f"{len(document['nodes'])} nodes, {len(document['transitions'])} transitions)."
    )

    if args.swift:
        args.swift.parent.mkdir(parents=True, exist_ok=True)
        args.swift.write_text(render_swift(document, folder.name))
        print(f"Wrote {args.swift} (Swift route enum).")

    if args.kotlin:
        args.kotlin.parent.mkdir(parents=True, exist_ok=True)
        args.kotlin.write_text(render_kotlin(document, folder.name))
        print(f"Wrote {args.kotlin} (Kotlin sealed route class).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
