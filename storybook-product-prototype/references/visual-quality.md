# Prototype Visual Quality

Use this reference when writing or reviewing the prototype CSS and the composed UI. The prototype must read as a believable product surface, not a gray wireframe.

## Before Writing CSS

- Do not write prototype CSS until the Token Binding section in `docs/UI_SPEC.md` exists (see `references/component-discovery.md`).
- Read the discovered token files first; bind aliases to real project tokens, not guessed names.

## Alias Block Pattern

All design values enter through one alias block on the feature root classes (the interactive root and the flow-export root share it):

- Define `--proto-*` aliases for: `bg`, `surface`, `surface-raised`, `border`, `text`, `text-muted`, `accent`, `on-accent`, `accent-container`, `success(-container)`, `warning(-container)`, `danger(-container)`, `focus-ring`, `grid-dot`, `shadow-soft`, `shadow-raised`, spacing steps, font-size/line-height scale, radii, and motion durations.
- Each alias resolves as `var(<discovered-project-token>, <neutral fallback>)`.
- Raw hex/rgb/hsl values are legal only inside this block as `var()` fallbacks. Every other rule consumes `--proto-*` aliases only.
- The Static Flow export CSS consumes the same aliases, so both renderers theme identically.

## App-Shell Minimum Bar

- Explicit `font-size` and `line-height` for every text role (h1, h2, h3, body, caption/eyebrow); nothing below 12px.
- Spacing only from the spacing scale; no ad-hoc magic numbers.
- Buttons: `cursor: pointer`, plus `:hover`, `:active`, `:focus-visible` (visible ring via `--proto-focus-ring` with offset), and `:disabled` states.
- Selected navigation = accent background with on-accent text, not a border-only tint.
- Inputs and selects: bordered, focus ring, disabled state.
- Loading, empty, and error state blocks styled and reachable through fixtures (`state` field on route content).
- Transitions animate transform/opacity/background at 120-180ms, wrapped in `@media (prefers-reduced-motion: no-preference)`.
- Layout verified at the declared viewport width (`flow.viewport`): phone prototypes keep the 720px wide-screen cap, tablet/desktop prototypes go fluid, and at least one responsive adjustment (e.g. a `min-width: 768px` block) exists for web-surface prototypes.

## Desktop Minimum Bar

Required in addition to the App-Shell Minimum Bar when the declared formFactor is `desktop` (and recommended for `tablet`):

- A maximum content width with explicit gutters — desktop screens are never a phone column stretched to 1280px, and never edge-to-edge text.
- Hover states on every interactive element (desktop is pointer-first), alongside the `:focus-visible` ring the App-Shell bar already requires.
- Wide-surface density: tables, multi-column layouts, or side-by-side panels where the product calls for them — information density is the reason the desktop viewport was declared.
- Full keyboard reachability: every action reachable by Tab order, with a visible focus path across columns and panels.
- Overflow behavior decided per region (scroll, wrap, truncate with title) instead of letting the browser pick.

## Hardcoded Value Rule

When the project has a token system, no raw colors or pixel typography may appear outside the alias block fallbacks. `scripts/validate_prototype.py` warns on raw color violations (`--strict-style` turns them into errors); pixel typography is checked in the UX self-review below.

## UX Self-Review Before Completion

With Storybook running:

1. Open every route through the UI Flow route cards and the interactive story.
2. Check hierarchy: one obvious primary action per screen; headings step down consistently.
3. Check states: hover/focus-visible on all controls, loading/empty/error where in scope.
4. Check contrast: text on accent/success/danger surfaces stays readable.
5. Check that the prototype visually belongs to the host project (same palette, same type family) — if it looks like a different product, the token binding is wrong.
6. Fix what fails, then re-run `scripts/validate_prototype.py`.
