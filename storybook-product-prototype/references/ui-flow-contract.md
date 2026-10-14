# UI Flow Contract

Use this reference when creating `FLOW_SPEC.md` and `<featurePrototypeFlow>.ts`.

## Route Metadata

Each route should define:

- `id`: stable route id used by React state and flow diagrams.
- `title`: review label.
- `navigationId`: shell navigation context when applicable.
- `component`: free-form display summary of the primary component or composed surface. Display text only — the structured per-route composition lives in `meta.components` (contract in `references/storybook-integration.md`); do not duplicate it here.
- `description`: behavior the route proves.
- `flowGroup`: optional grouping label.
- `flowPosition`: optional stable `{ x, y }` coordinate.
- `params`: optional array of `{ name, type }` route parameters production navigation needs (URL params on web, destination arguments on iOS/Android). Declare them here so codegen and the receiving implementation never re-derive them from fixtures.
- `deepLink`: optional direct-entry pattern for the route (for example `/alerts/:alertId` or `app://alerts/:alertId`). Declare it when the route is a deep-link target.
- `viewport`: optional `{ width, height }` preview-size override for this route only, for mixed flows (for example one desktop admin screen inside a phone flow). Falls back to the flow-level viewport.

## Viewport

The flow object carries the primary review viewport as a first-class field:

```ts
viewport: { formFactor: "phone" | "tablet" | "desktop", width: number, height: number }
```

Every renderer — Static Flow export, the prototype shell, and the Prototype Inspector — reads this value at runtime, so editing `flow.viewport` by hand resizes the prototype without re-scaffolding. A flow that declares no viewport resolves to phone 375x812 in every consumer, which keeps existing prototypes working untouched.

Presets are pinned to the storybook-template `--sbt` viewport token tier:

| Preset | formFactor | Size | Token tier |
| --- | --- | --- | --- |
| `phone` | phone | 375x812 | `--sbt-sys-size-viewport-compact-*` |
| `tablet` | tablet | 768x1024 | `--sbt-sys-size-viewport-medium-*` |
| `desktop` | desktop | 1280x800 | `--sbt-sys-size-viewport-wide-*` |

Scaffold with `--viewport {phone|tablet|desktop|<W>x<H>}` (custom sizes classify their formFactor by width: >=1024 desktop, >=600 tablet, else phone; sides must be 240-3840). The Prototype Inspector resolves each card's preview size in this order:

1. `route.viewport` (per-route override)
2. `flow.viewport`
3. the form-factor tier CSS tokens (`--prototype-inspector-viewport-compact/medium/wide-*`, read on the `.prototype-inspector` element first, then `:root`)
4. the built-in phone constants 375x812

`flowPosition` values are authored against the declared frame size. Saved drag layouts (localStorage payload version 2) carry a viewport signature (`<formFactor>:<width>x<height>`); when a prototype's declared viewport changes, saved positions with a mismatched signature are ignored with a console.info notice and the fallback layout is used — a one-time re-drag instead of phone-era coordinates rendering desktop frames as an overlapping pile. Unsigned version-1 payloads keep applying for phone 375x812 prototypes.

Static Flow export fallback placement scales with the frame: below 900px-wide frames it uses the derived grid pitch (identical to the historical 560x980 at phone); at 900px or wider each `flowGroup` becomes its own horizontal row so desktop frames never overlap. Route cards show a formFactor badge (for example `desktop · 1280x800`).

`export_flow.py` includes the resolved viewport in `docs/flow.json` (top-level `viewport` plus per-route overrides; omitted entirely for flows that declare none, `flowSchemaVersion` stays 1) while still stripping the canvas-layout fields — the viewport is product semantics, not layout.

## Flow-Only Nodes

Use flow-only nodes for branch logic that is not a full product screen:

- API success/failure decisions.
- Async loading or queued states.
- Permission decisions.
- Validation outcomes.
- Background status nodes.

Flow-only nodes should define:

- `id`
- `title`
- `description`
- `shape`: usually `decision` or `state`.
- `tone`: optional `success`, `error`, `warning`, or project-specific tone.
- `flowPosition`: optional stable coordinate.

## Transitions

Every user-triggered route change must define:

- `from`: source route or flow-node id.
- `to`: target route or flow-node id.
- `trigger`: stable event or branch condition name.
- `label`: human-readable edge label.
- `kind`: optional semantic category such as `primary`, `return`, `global`, `secondary`, `outcome`, or `condition`.
- `presentation`: target semantics — `push` (stack navigation / page change), `modal` (blocking overlay), `sheet` (partial overlay), `fullscreen` (full-screen cover), or `replace` (swap without history). Required by `--handoff-ready` for every non-return transition entering a visible route, on every platform; app targets also require it on all other non-return transitions. A missing field is an error without `--strict-style`, never an implied push.
- `backBehavior`: exit semantics — `pop` (one step back), `popToRoot` (back to the flow's root), `dismiss` (close the overlay), or `none` (no user-initiated back). Required at handoff for every return transition entering a visible route. Declare other nontrivial exits explicitly too; missing return behavior never implies pop.
- `motion`: `none`, `platform-default`, or `custom`. Required at handoff for every transition entering a visible route, including return transitions. This is animation intent, separate from navigation presentation. `platform-default` explicitly authorizes the native/browser framework default without a guessed duration; `none` explicitly disables transition animation.
- `motionRef`: required for custom motion, using `FLOW_SPEC.md#explicit-anchor` with a matching actual HTML anchor in that document. Describe entering/returning behavior, direction, duration/easing, and reduced-motion behavior at the anchor. Do not rely on an automatically generated Markdown heading slug.
- `flowLine`: optional display hint. Use `key` only for transitions drawn on the simplified canvas.
- `sourceAnchor`: optional `{ x, y }` route-card-relative ratio used only when Static Flow export needs a stable edge origin for Figma-ready layout. Use sparingly and keep values between `0` and `1`.

Draft/legacy files may omit the navigation and motion fields and remain readable. Report the unresolved choice and its owner; do not infer defaults. Missing intent blocks that flow's complete handoff, not independent work. A non-screen branch target does not need motion solely for branch evaluation. `export_flow.py` preserves motion/motionRef in flow JSON and native scaffold comments; it does not implement an animation engine.

## Trigger Naming

Use stable, implementation-facing names:

- `quoteRow.click`
- `submitButton.click`
- `orderSubmit.success`
- `orderSubmit.error`
- `bottomNavigation.watchlist`
- `topAction.search`
- `settingsSheet.dismiss`

Do not use rendered labels as route logic.

## Control Mapping

Create mapping objects before wiring handlers:

- bottom navigation id to route id
- top action id to route id
- tab or segmented control id to route id
- menu action id to route id
- sheet action id to route id

## Production Mapping

When preparing frontend handoff, map route ids and transitions to the target platform:

- web routes, nested layouts, modals, sheets, or query params
- app screens, tabs, navigation stack entries, sheets, or deep links
- shared component states when no route or screen boundary exists
- service, permission, or async branch nodes that production must implement

Keep route ids stable across prototype docs and handoff docs so engineers and AI agents can trace behavior without relying on visible labels.

## Acceptance

- Every visible route appears in route metadata.
- Every documented click appears in transition metadata.
- Every transition target exists as a route or flow-only node.
- Every transition entering a visible route has motion plus its required presentation or return behavior; every custom motion reference resolves to an explicit Flow Spec anchor.
- UI Flow canvas uses key transitions; Transition Index uses the full transition list.
- The prototype supports `prototypeRoute=<route-id>` for route-specific iframe previews.
- The prototype supports `prototypeFlowPreview=true` for compact embedded rendering.
- In flow preview mode (`isFlowPreview` prop or `prototypeFlowPreview=true`), the prototype hides its own chrome — the prototype header and the route navigation — so flow cards and iframe previews show only what the real page shows.
- The route preview shell exposes `data-prototype-route-preview="true"` for template-compatible iframe measurement.
- The prototype root keeps `data-prototype-root="true"` for backward-compatible iframe height measurement.
- Static Flow export reads saved layout from `prototypeFlowLayout.ts` using the same storage key as the Prototype Inspector, passing the resolved viewport signature so mismatched saved layouts are cleanly ignored.
- The Static Flow export derives frame sizes from `Flow.viewport` at runtime (never baked constants), and the prototype shell sets the preview-size CSS variables inline from the same source.
- Production handoff maps every route and branch node that must become a web/app surface, service decision, API/data contract expectation, or shared state.
