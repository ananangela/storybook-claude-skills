#!/usr/bin/env python3
"""Scaffold a PRD-led Storybook product prototype and frontend handoff."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


TOKEN_FILES = {
    "FeaturePrototypeFlowExport.tsx.template": "__FEATURE_PASCAL__FlowExport.tsx",
    "FeaturePrototypeFlowExport.stories.tsx.template": "__FEATURE_PASCAL__FlowExport.stories.tsx",
    "FeaturePrototype.tsx.template": "__FEATURE_PASCAL__.tsx",
    "FeaturePrototype.stories.tsx.template": "__FEATURE_PASCAL__.stories.tsx",
    "featurePrototypeFlow.ts.template": "__FEATURE_CAMEL__Flow.ts",
    "featurePrototypeData.ts.template": "__FEATURE_CAMEL__Data.ts",
    "featurePrototypeMeta.ts.template": "__FEATURE_CAMEL__Meta.ts",
    "feature-prototype.css.template": "__FEATURE_KEBAB__.css",
}

VUE_TOKEN_FILES = {
    "FeaturePrototypeFlowExport.vue.template": "__FEATURE_PASCAL__FlowExport.vue",
    "FeaturePrototypeFlowExport.stories.ts.template": "__FEATURE_PASCAL__FlowExport.stories.ts",
    "FeaturePrototype.vue.template": "__FEATURE_PASCAL__.vue",
    "FeaturePrototype.stories.ts.template": "__FEATURE_PASCAL__.stories.ts",
}

# Base-template files replaced by the Vue overlay; skipped when framework is vue.
REACT_ONLY_TEMPLATE_NAMES = {
    "FeaturePrototypeFlowExport.tsx.template",
    "FeaturePrototypeFlowExport.stories.tsx.template",
    "FeaturePrototype.tsx.template",
    "FeaturePrototype.stories.tsx.template",
    "index.ts",
}

# Preset values are pinned to the storybook-template --sbt viewport token tier
# (compact/medium/wide); keep the two in sync.
VIEWPORT_PRESETS = {
    "phone": (375, 812),
    "tablet": (768, 1024),
    "desktop": (1280, 800),
}

VIEWPORT_MIN = 240
VIEWPORT_MAX = 3840


def viewport_argument(value: str) -> str:
    if value in VIEWPORT_PRESETS:
        return value
    match = re.fullmatch(r"(\d+)x(\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError(
            f"expected phone, tablet, desktop, or <W>x<H> (got {value!r})"
        )
    width, height = (int(part) for part in match.groups())
    if not all(VIEWPORT_MIN <= side <= VIEWPORT_MAX for side in (width, height)):
        raise argparse.ArgumentTypeError(
            f"viewport sides must be {VIEWPORT_MIN}-{VIEWPORT_MAX} (got {value!r})"
        )
    return value


def classify_form_factor(width: int) -> str:
    if width >= 1024:
        return "desktop"
    if width >= 600:
        return "tablet"
    return "phone"


def resolve_viewport(viewport: str, form_factor: str | None) -> tuple[str, int, int]:
    if viewport in VIEWPORT_PRESETS:
        width, height = VIEWPORT_PRESETS[viewport]
        return viewport, width, height
    width, height = (int(part) for part in viewport.split("x"))
    return form_factor or classify_form_factor(width), width, height


def detect_framework(target_root: Path) -> tuple[str, str]:
    for directory in (target_root, *target_root.parents):
        package_json = directory / "package.json"
        if not package_json.is_file():
            continue
        try:
            manifest = json.loads(package_json.read_text())
        except (OSError, json.JSONDecodeError) as error:
            return "react", f"could not parse {package_json} ({error}); falling back to react"
        dependency_names: set[str] = set()
        if isinstance(manifest, dict):
            for section in ("dependencies", "devDependencies"):
                block = manifest.get(section)
                if isinstance(block, dict):
                    dependency_names.update(block)
        vue_matches = sorted(
            name
            for name in dependency_names
            if name == "vue" or name.startswith("@storybook/vue3")
        )
        if vue_matches:
            return "vue", f"{vue_matches[0]} dependency in {package_json}"
        if "react" in dependency_names:
            return "react", f"react dependency in {package_json}"
        return "react", f"no vue or react dependency in {package_json}; falling back to react"
    return "react", f"no package.json found above {target_root}; falling back to react"


def split_words(value: str) -> list[str]:
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value.strip())
    words = re.findall(r"[A-Za-z0-9]+", cleaned)
    if not words:
        raise ValueError("feature name must contain at least one letter or digit")
    return words


def to_kebab(words: list[str]) -> str:
    return "-".join(word.lower() for word in words)


def to_pascal(words: list[str]) -> str:
    return "".join(word[:1].upper() + word[1:] for word in words)


def to_camel(words: list[str]) -> str:
    pascal = to_pascal(words)
    return pascal[:1].lower() + pascal[1:]


def to_title(words: list[str]) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in words)


def to_storybook_id(value: str) -> str:
    story_id = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return story_id or "prototype"


def copy_template_file(source: Path, target: Path, replacements: dict[str, str]) -> None:
    text = source.read_text()
    for token, value in replacements.items():
        text = text.replace(token, value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def copy_flow_layout_helper(skill_root: Path, target_root: Path, force: bool) -> None:
    source = skill_root / "assets" / "prototype-flow-layout" / "prototypeFlowLayout.ts"
    target = target_root / "prototypeFlowLayout.ts"

    if target.exists() and not force:
        return

    if not source.is_file():
        raise FileNotFoundError(f"missing prototype flow layout helper: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def copy_template_tree(
    template_root: Path,
    prototype_dir: Path,
    replacements: dict[str, str],
    token_files: dict[str, str],
    skip_names: set[str],
    force: bool,
) -> None:
    for source in template_root.rglob("*"):
        if source.is_dir() or source.name in skip_names:
            continue

        relative = source.relative_to(template_root)
        mapped_name = token_files.get(source.name, source.name)
        for token, value in replacements.items():
            mapped_name = mapped_name.replace(token, value)

        target = prototype_dir / relative.parent / mapped_name
        if target.exists() and not force:
            raise FileExistsError(f"{target} already exists. Pass --force to overwrite.")
        copy_template_file(source, target, replacements)


def scaffold(args: argparse.Namespace) -> Path:
    words = split_words(args.feature_name)
    feature_kebab = args.kebab or to_kebab(words)
    feature_pascal = args.pascal or f"{to_pascal(words)}Prototype"
    # Feature name without the Prototype suffix, for production-facing names
    # such as the `<Feature>DataSource` adapter contract in ACCEPTANCE.md.
    feature_base_pascal = to_pascal(words)
    if args.pascal:
        stripped = args.pascal[: -len("Prototype")] if args.pascal.endswith("Prototype") else args.pascal
        feature_base_pascal = stripped or args.pascal
    feature_camel = args.camel or f"{to_camel(words)}Prototype"
    feature_title = args.title or f"{to_title(words)} Prototype"
    entry_route = args.entry_route or to_kebab(words)
    css_class = args.css_class or f"{args.css_prefix}-{feature_kebab}-prototype"

    skill_root = Path(__file__).resolve().parents[1]
    template_root = skill_root / "assets" / "prototype-template"
    vue_template_root = skill_root / "assets" / "prototype-template-vue"
    target_root = Path(args.target_root).resolve()
    prototype_dir = target_root / f"{feature_kebab}-prototype"
    story_id_base = to_storybook_id(f"Pages/Prototypes/{feature_title}")

    if args.framework == "auto":
        framework, framework_reason = detect_framework(target_root)
    else:
        framework, framework_reason = args.framework, "explicit --framework value"
    print(f"framework: {framework} ({framework_reason})")

    form_factor, viewport_width, viewport_height = resolve_viewport(
        args.viewport, args.form_factor
    )
    print(f"viewport: {form_factor} {viewport_width}x{viewport_height}")
    print(f"target surface: {args.target_surface}")
    print(
        "note: --force re-scaffolds regenerate the flow file; repeat "
        "--viewport/--target-surface or the prototype reverts to the phone/web defaults."
    )

    if prototype_dir.exists():
        if not args.force:
            raise FileExistsError(
                f"{prototype_dir} already exists. Pass --force to overwrite template files."
            )
    else:
        prototype_dir.mkdir(parents=True)

    replacements = {
        "__ENTRY_ROUTE_ID__": entry_route,
        "__FEATURE_BASE_PASCAL__": feature_base_pascal,
        "__FEATURE_CAMEL__": feature_camel,
        "__FEATURE_CSS_CLASS__": css_class,
        "__FEATURE_KEBAB__": f"{feature_kebab}-prototype",
        "__FEATURE_PASCAL__": feature_pascal,
        "__FEATURE_STORY_ID__": f"{story_id_base}--static-flow",
        "__FEATURE_TITLE__": feature_title,
        "__FORM_FACTOR__": form_factor,
        "__OWNER__": args.owner,
        "__OWNER_JSON__": json.dumps(args.owner, ensure_ascii=False),
        "__SHELL_WIDE_CAP__": "720px" if form_factor == "phone" else "100%",
        "__TARGET_SURFACE__": args.target_surface,
        "__VIEWPORT_HEIGHT__": str(viewport_height),
        "__VIEWPORT_WIDTH__": str(viewport_width),
    }

    copy_flow_layout_helper(skill_root, target_root, args.force)

    copy_template_tree(
        template_root,
        prototype_dir,
        replacements,
        TOKEN_FILES,
        REACT_ONLY_TEMPLATE_NAMES if framework == "vue" else set(),
        args.force,
    )
    if framework == "vue":
        if not vue_template_root.is_dir():
            raise FileNotFoundError(f"missing Vue overlay template set: {vue_template_root}")
        copy_template_tree(
            vue_template_root,
            prototype_dir,
            replacements,
            VUE_TOKEN_FILES,
            set(),
            args.force,
        )

    return prototype_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_name", help="Human feature name, e.g. 'Portfolio Alerts'")
    parser.add_argument(
        "--target-root",
        default="src/pages/prototypes",
        help="Prototype root directory in the target repo.",
    )
    parser.add_argument("--title", help="Human story title. Defaults to '<Feature> Prototype'.")
    parser.add_argument("--owner", default="Product Team", help="Prototype owner label.")
    parser.add_argument("--entry-route", help="Initial route id. Defaults to feature kebab name.")
    parser.add_argument("--kebab", help="Override feature kebab base name.")
    parser.add_argument("--pascal", help="Override component PascalCase name.")
    parser.add_argument("--camel", help="Override module camelCase base name.")
    parser.add_argument("--css-class", help="Override prototype root CSS class.")
    parser.add_argument("--css-prefix", default="cm", help="CSS class prefix.")
    parser.add_argument(
        "--framework",
        choices=("auto", "react", "vue"),
        default="auto",
        help=(
            "Target Storybook framework. auto detects from the nearest package.json "
            "above the target root and falls back to react."
        ),
    )
    parser.add_argument(
        "--viewport",
        type=viewport_argument,
        default="phone",
        help=(
            "Primary review viewport: phone (375x812), tablet (768x1024), "
            "desktop (1280x800), or a custom <W>x<H> within "
            f"{VIEWPORT_MIN}-{VIEWPORT_MAX}. Custom sizes classify their form "
            "factor by width (>=1024 desktop, >=600 tablet, else phone)."
        ),
    )
    parser.add_argument(
        "--form-factor",
        choices=tuple(VIEWPORT_PRESETS),
        help="Form-factor label for a custom <W>x<H> --viewport value.",
    )
    parser.add_argument(
        "--target-surface",
        choices=("web", "app", "hybrid", "package"),
        default="web",
        help="Target production surface recorded in the prototype meta.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files.")
    args = parser.parse_args()

    if args.form_factor and args.viewport in VIEWPORT_PRESETS:
        parser.error("--form-factor only applies to a custom <W>x<H> --viewport value")

    prototype_dir = scaffold(args)
    print(prototype_dir)


if __name__ == "__main__":
    main()
