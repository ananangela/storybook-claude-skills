# Storybook Integration

Use this reference when creating `<FeaturePrototype>.stories.tsx` (React) or `<FeaturePrototype>.stories.ts` (Vue) and `<featurePrototypeMeta>.ts`.

## Story Requirements

The default story should:

- Use `layout: "fullscreen"` when rendering a full product surface.
- Render a clickable prototype, not a static screenshot.
- Attach the meta object to `parameters.prototype`.
- Support `prototypeFlowPreview=true` for compact iframe preview styling; in this mode the prototype must hide its own chrome (prototype header and route navigation) so previews show only real page content.
- Support `prototypeRoute=<route-id>` so UI Flow route cards can render the correct route.
- Add `data-prototype-route-preview="true"` to the route preview shell for template-compatible iframe measurement. Width is declared (the shell sets the preview-size CSS variables inline from `flow.viewport`, per-route override first) while height is still measured from the rendered content — declaration and measurement split the two axes.
- Keep `data-prototype-root="true"` on the prototype root for backward-compatible viewers.

The Static Flow story should:

- Export `StaticFlow` from `<FeaturePrototypeFlowExport>.stories.tsx`.
- Use the same Storybook title and `parameters.prototype` object as the interactive story.
- Use `layout: "fullscreen"`.
- Render route cards and flow-only nodes from `flow.routes`, `flow.nodes`, and key `flow.transitions`.
- Read saved layout through `../prototypeFlowLayout` so positions edited in the Prototype Inspector match the export artifact.

## Vue Story Conventions

The Vue overlay templates follow the same story requirements with these framework-native conventions:

- Story files are `.stories.ts` (`<FeaturePrototype>.stories.ts`, `<FeaturePrototypeFlowExport>.stories.ts`), typed with `Meta` and `StoryObj` from `@storybook/vue3-vite`.
- The prototype component is a `<script setup lang="ts">` SFC imported as a default export (`import FeaturePrototype from "./FeaturePrototype.vue"`); component references inside SFC templates use PascalCase.
- The story `render` function returns a `{ components, setup, template }` object that binds args onto the component.
- `parameters.prototype`, `layout: "fullscreen"`, the `StaticFlow` export name, and the `prototypeRoute` / `prototypeFlowPreview` query modes are identical to the React contract — the meta, flow, and data modules stay plain TypeScript and are shared unchanged across frameworks.

## Metadata Shape

Expose a meta object with:

- `id`
- `title`
- `description`
- `owner`
- `status`
- `docs`
- `flow`
- `data`
- `figmaExport`
- `components` (optional; see Component Composition Metadata below)

The `docs` object should import raw markdown from:

- `docs/PRD.md`
- `docs/UI_SPEC.md`
- `docs/FLOW_SPEC.md`
- `docs/DATA_SPEC.md`
- `docs/PRODUCTION_HANDOFF.md`
- `docs/IMPLEMENTATION_GUIDE.md`
- `docs/ACCEPTANCE.md`

Use `productionHandoff` as the `docs` key for `docs/PRODUCTION_HANDOFF.md`.

The `flow` object should expose:

- `routes`
- `nodes`
- `transitions`

The `data` object should summarize:

- fixture inventory
- route data requirements
- API replacement points
- source ownership when known

Data Authority remains solely in the raw `docs.dataSpec` markdown under `## Data Authority`; do not copy the registry into `data`. The Inspector reads its single fenced JSON block, displays FAKE values separately from UI-model/transport confirmation, and shows source and owner. Missing, malformed, or unsupported authority is unverified; free-text `data.overview.status` and demo confirmation cannot override it. See [handoff-authority.md](handoff-authority.md).

The `figmaExport` object should expose:

- `flowStoryId`: the Storybook id for the `StaticFlow` export, for example `pages-prototypes-example-prototype--static-flow`.

`PRODUCTION_HANDOFF.md` should be exposed with the other docs so reviewers can inspect frontend implementation guidance without leaving Storybook.

## Component Composition Metadata

`components` is an OPTIONAL top-level meta key — a sibling of `flow`, `data`, `docs`, and `figmaExport` — that records which components compose each route. This section is the single source for the contract; other references link here instead of restating it.

```ts
components: {
  classPrefix: 'cm-',               // optional; project-wide component root-class prefix used to derive highlight selectors
  routes: [
    {
      route: 'route-id',              // MUST be an existing flow route id
      components: [
        {
          name: 'BottomSheetCell',    // local import binding / display name (PascalCase)
          origin: 'shared',           // 'shared' | 'local' | 'promoted'
          importPath: 'src/components/bottom-sheet-cell', // shared/promoted: package or repo path; local: prototype-relative file
          storyId: 'components-lists-bottom-sheet-cell--default', // optional; enables click-through
          storyTitle: 'Components/Lists/Bottom Sheet Cell',       // optional; display + derivation evidence
          note: 'variant / prop usage notes',                     // optional
          domSelector: '.cm-bottom-sheet-cell', // optional; explicit CSS selector for this component's rendered root(s) in the route preview; overrides derivation
          targets: {                  // optional; per-platform production counterparts
            web: 'src/components/bottom-sheet-cell', // production component/import path, when it exists
            ios: null,                // string = SwiftUI view name; null = must be newly built; key absent = platform out of scope
            android: 'BottomSheetCell', // string = composable name; same null/absent semantics
          },
        },
      ],
    },
  ],
}
```

Rules:

- The key is optional. Every consumer must tolerate its absence (older prototypes) and ignore unknown extra fields.
- `targets` is the OPTIONAL per-platform mapping for multi-platform deliveries: each of `web`, `ios`, and `android` holds the production counterpart's name or path (a string), an explicit `null` meaning the counterpart must be newly built, or is absent meaning that platform is out of scope for the entry. Entries without `targets` keep the single-target contract unchanged. Fill it when `PRODUCTION_HANDOFF.md` Target Surfaces declares more than one platform, so a native receiver can tell which SwiftUI view or composable corresponds to each prototype component instead of re-deriving the mapping.
- `origin` semantics: `shared` = the component existed before this prototype (a UI_SPEC Component Map entry); `local` = created for this prototype (a UI_SPEC Component Gaps entry or prototype-local file, usually with no story); `promoted` = was a gap, then promoted into the hub's shared component library in the promote workflow step (has a hub path and story id).
- The authoring source of truth stays `docs/UI_SPEC.md` Component Map / Component Gaps. `meta.components` is the machine-readable echo: author it in the compose step, and update the affected entry in the promote step in the same motion as the doc move (`origin` `local` → `promoted`, plus the new `storyId`).
- Resolve each `storyId` through the resolution chain in `references/component-discovery.md`; never guess an id silently. When no id resolves (typical for `local`), omit `storyId` — the inspector shows the source path without a link.
- Docs links are derived at runtime, never stored: strip the trailing `--<storyName>` segment from `storyId` and append `--docs` (`?path=/docs/<base>--docs`). The docs link is only a secondary link.
- `classPrefix` and `domSelector` are the OPTIONAL highlight fields. The inspector resolves each entry's highlight selector as: the entry's `domSelector` when present; otherwise, when `classPrefix` is set, `"." + classPrefix + kebab(name)` (PascalCase → kebab-case, e.g. `BottomSheetCell` → `.cm-bottom-sheet-cell`; digits stay attached to the preceding word — `Grid12` → `.cm-grid12` — so use `domSelector` when the project's class convention separates digits); otherwise the entry has no highlight affordance — its card still shows the origin badge, import path, and story links. `classPrefix` records the project's component root-class convention (see `references/component-discovery.md`); `domSelector` is the per-entry escape hatch for roots that do not follow it (page-level shells, prototype-local markup). Both fields are optional and every consumer must tolerate their absence.

Both the interactive story and the `StaticFlow` story share one meta object, so composition data surfaces in both automatically; both must tolerate the key being absent.

## UI Flow Viewer Boundary

This skill creates the metadata contract and includes a bundled Prototype Inspector runtime.

If the target project has no prototype inspector:

1. Still generate `parameters.prototype`.
2. Install the bundled runtime only when the user asks for Storybook UI Flow review:
   `node <skill-root>/scripts/install_prototype_inspector.mjs --project-root <repo-root>`.
3. Do not replace an existing `.storybook/prototype-inspector` folder or `src/pages/prototypes/prototypeFlowLayout.ts` unless the user approves `--force`. Re-running with `--force` is also how an existing install picks up bundled addon updates.
4. The inspector CSS defines a `--pi-*` token layer: each token reads the `--sbt-*` design token when the project defines it and otherwise falls back to built-in neutral values (with a `prefers-color-scheme: dark` fallback set), so the panels render correctly in any React Storybook project. When the project uses another token prefix, pass `--token-prefix <prefix>` (for example `--token-prefix md`) to bind the layer to the project's tokens, or redefine `--pi-*` tokens on `.prototype-inspector` in a stylesheet loaded after the addon CSS.

If the target project already has a prototype inspector, match its parameter name, preview-mode query conventions, route preview selector, and saved layout helper. For repos created from `design-system-to-storybook/storybook-template`, keep the existing `prototypeFlowLayout.ts` schema and Static Flow pattern.

## Bundled Prototype Inspector

The bundled addon reads `parameters.prototype` and provides a Storybook toolbar with the modes below. The toolbar tool renders only while the selected story (or its autodocs page) declares `parameters.prototype`; on every other story it is hidden entirely. Visibility is parameter-driven — sidebar category naming (`Prototypes/`, `Flows/`, ...) carries no meaning.

- `Story`: the original story.
- `Docs`: PRD, UI Spec, Flow Spec, Data Spec, Frontend Handoff, Implementation Guide, and Acceptance markdown.
- `UI Flow`: route cards, flow-only nodes, key transition lines, zoom, drag, pan, layout import, and layout export.
- `Components`: an interactive three-pane workspace over `meta.components`.
  - A route rail on the left lists the flow routes in flow order (route title plus id badge); the first route with composition data is selected by default.
  - The middle pane shows one card per component of the selected route — name, origin badge (`shared` / `new` / `promoted`), story title, import path, and notes. When a `storyId` is present, the card's `Story` button opens `?path=/story/<storyId>` in a new tab (the same URL mechanism as `Open Static Flow`), with a secondary `Docs` link to the derived `--docs` path; without a `storyId`, the card shows the source path with no link.
  - The right pane is a live same-origin iframe preview of the selected route (the same `prototypeFlowPreview=true` + `prototypeRoute=<route-id>` URL the UI Flow cards use), scaled to fit and reloaded on route switch.
  - Hovering or focusing a card whose highlight selector resolves (see Component Composition Metadata above) outlines the matching element(s) inside the preview iframe, scrolls the first match into view, and shows the match count on the card. A selector that matches nothing in the preview's current state is normal: the card shows a muted "not in current state" chip instead of a highlight.
  - The reverse direction works too (mouse only): hovering a component's rendered instance inside the live preview outlines just that instance and emphasizes its card in the middle pane, scrolling the card into view; when several entries' selectors match, the deepest (most specific) element wins. Leaving the preview hands the highlight back to a still-focused card or clears it, and the listeners never intercept clicks or navigation inside the preview.
  - Everything degrades gracefully: entries without a resolvable selector (no `domSelector` and no `classPrefix`) keep their full card — origin, links, import path — just without the hover-highlight. A prototype without `meta.components` gets a friendly empty state, not an error; a selected route without a composition entry shows a "No composition data for this route" message while the preview still renders.
- `Data`: Fake fixture values, schema scope/confirmation, contract source and owner from the raw Data Authority registry, API replacement requirements, route data map, state rules, and raw metadata. Confirmed UI models are explicitly distinct from confirmed real transport contracts; legacy or invalid registries remain unverified.
- `Open Static Flow`: when `parameters.prototype.figmaExport.flowStoryId` is present, open the Figma-ready static flow story that uses the same saved layout.

UI Flow route cards also carry a compact component strip/badge sourced from the same `meta.components` data. The `Components` mode and route-card strip ship with the bundled addon: an existing install picks them up by re-running `install_prototype_inspector.mjs --force`.

Preview-size resolution for inspector installs: each card resolves `route.viewport` → `flow.viewport` → the form-factor tier CSS tokens → the built-in 375x812 constants. The tier tokens are read on the `.prototype-inspector` element first and `:root` second, so both the documented `--sbt-sys-size-viewport-*` bridge and legacy `:root`-level overrides work. Compatibility notes: the compact pair (`--prototype-inspector-viewport-compact-width/height`) keeps its phone semantics and remains the project-global default; the medium (`768px/1024px`) and wide (`1280px/800px`) pairs serve tablet and desktop form factors; the inspector sets `--prototype-inspector-active-viewport-width/height` inline per prototype so stylesheet layout caps follow the active prototype without redefining `compact`. Cards of prototypes that declare a viewport show a formFactor badge (for example `desktop · 1280x800`); legacy prototypes show none and keep their exact pre-viewport behavior.
