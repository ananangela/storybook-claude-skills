# Production Handoff

Use this reference when creating `PRODUCTION_HANDOFF.md` or preparing prototype docs for frontend web or app implementation handoff.

Read [handoff-authority.md](handoff-authority.md) with this reference. `DATA_SPEC.md` owns the Data Authority registry; this handoff references its decisions without copying or upgrading their status.

## Purpose

`PRODUCTION_HANDOFF.md` is the bridge from a Storybook prototype to frontend implementation work. It should let an engineer or AI agent understand what UI behavior to build, where it belongs in the production product, which prototype parts are reusable, which data/API contracts the UI expects, and which integration responsibilities belong to the receiving production repo.

Do not describe the prototype as production-ready. Describe the frontend contract and the decisions needed for production integration. Real data sources, auth, backend clients, storage, persistence, and environment-specific wiring are receiving-implementation responsibilities unless the user explicitly scopes them into the prototype.

## Required Sections

Use these sections:

```markdown
# Production Handoff

## Review Status

## Semantic Review

## Target Surfaces

## Prototype To Frontend Map

## Web Implementation Notes

## App Implementation Notes

## Shared Domain And UI State Model

## API And Data Contracts

## Remote Config Intent

## Frontend Handoff Acceptance

## Integration Ownership

## Storybook-Only Boundaries

## Design System Continuity

## Open Product Decisions
```

## Review Status

The handoff flow is: Storybook demo → the team confirms the product direction → the docs go to the receiving engineer or AI. This section stamps that confirmation so the receiver knows the docs describe a confirmed direction, not a draft under discussion:

- Status: `pending` or `confirmed`
- `Confirmed by`: named reviewer or team
- `Confirmed on`: actual ISO review date
- `Reviewed demo`: Storybook story or UI Flow reviewed
- `Scope`: what the product confirmation covers or explicitly excludes

`validate_prototype.py --handoff-ready` requires this complete, confirmed record. A legacy draft remains readable, but it must gain actual review evidence before handoff. Product confirmation never confirms an API, analytics parameter, Remote Config key, or UI schema automatically.

## Semantic Review

Record `Reviewed by`, `Reviewed on` (ISO date), `Scope`, `Result: passed`, and `Related updates` only after reviewing the actual document content. Check that Builder suggestions remain proposed, superseded decisions have no active paths, and every unknown names its owner and affected behavior. Review the affected Data Spec, Handoff, Flow Spec, Acceptance, fixtures, metadata, exports, and tests together; name the files updated or why each was unaffected. Validation checks completeness and integrity, not external source truth or semantic correctness.

## Target Surfaces

State whether the production target is:

- web only
- native app only
- hybrid app or embedded webview
- shared component package used by web and app
- unknown or pending decision

Add a required `Primary viewport` line mirroring `flow.viewport` — formFactor plus size, for example `Primary viewport: desktop 1280x800`. The prose here mirrors the typed declarations (`meta.surface.target` and `flow.viewport`); `validate_prototype.py` reads the typed fields first and falls back to this section's prose only for legacy prototypes that predate them.

If the target is unknown, write the safest known assumptions and list the blocking decision in `Open Product Decisions`.

Known follow-up for desktop prototypes composing storybook-template components: several `tokens-comp.css` component tokens still alias `--sbt-sys-size-viewport-compact-width`, so wide components (tables, calendars, order books) stay capped at 375px until that token pass lands — note affected regions in `Open Product Decisions` when it matters.

## Prototype To Frontend Map

Map each prototype part to frontend implementation concepts:

- **delivery scope — record this first, it decides whether the rest is work at all:**
  - `A` existing — already ships in production; the prototype re-creates it only so the
    new behavior can be judged at real information density. **Do not rebuild.**
  - `B` new — does not exist in production yet. Build it.
  - `C` storybook-only — never ships.
  - `U` unverified — you do not know. Write `U`, and add it to `Open Product Decisions`
    with an owner. Never guess `B`: a wrong `B` costs the receiver a rebuilt screen,
    while `U` costs one question.
- prototype part (a route, or a region inside a route)
- production page, screen, sheet, modal, or component — or, for `A`, the existing surface it stands in for
- what to do: build, do not rebuild, modify just this region, or strip
- reusable prototype files or components
- production navigation entry and exit points

Rows may be finer than a route. A route that is `A` overall often contains a `B` region —
an existing settings list with one new row, an existing page whose table must now honor a
new preference. Split the row; a parent's scope never carries down to its children.

For a multi-target delivery — `Target Surfaces` declares more than one platform — split
the scope per target: replace the single `Scope` column with `Scope(web)` and `Scope(app)`
columns, each holding `A`/`B`/`C`/`U` with the same semantics. The same region routinely
already ships on web (`A`) while its app counterpart is new (`B`); a single column cannot
say that, and a receiver reading "web already has it" as "the app has it too" rebuilds
nothing that should exist. Single-target handoffs keep the single `Scope` column;
`validate_prototype.py` accepts both forms.

Two signals mean a part is almost certainly `A`, not `B`:

- **It renders without a fixture.** A component the prototype passes only an
  `ariaLabel` to, whose on-screen values come from the component's own demo constants,
  is a context stand-in — not a data-driven deliverable. Say so in `DATA_SPEC.md` too,
  or the receiver will build a typed interface and a mock adapter for a screen that
  already ships, and may go ask a backend team for an endpoint nobody needs.
- **Nothing on it drives the flow.** If a route carries many components but only one
  or two handlers actually change route state, the rest is scenery.

Fill `Do Not Rebuild` with the `A` rows a receiver is most likely to build by mistake,
plus the evidence that settles each one. The table carries the verdict; that section
carries the reason, which is what survives a skeptical reader.

## Web Implementation Notes

Document web-specific needs when the surface may ship on web:

- URL route, query params, and deep-link behavior
- rendering mode when known: SPA, SSR, SSG, server components, or embedded widget
- responsive breakpoints and layout changes, using the declared formFactor (`flow.viewport`) as the baseline the prototype was reviewed at — breakpoints describe how production departs from that baseline
- keyboard behavior, focus management, and ARIA requirements
- browser storage, cache, or session behavior
- analytics events and feature flag exposure
- SEO or metadata needs when the page is public

If the product is not web, write `Not in scope`.

## App Implementation Notes

Document app-specific needs when the surface may ship on iOS, Android, or a cross-platform app:

- navigation stack, tab, sheet, modal, or push destination
- safe-area, orientation, and viewport constraints
- platform gestures, haptics, and dismissal behavior
- permission prompts and OS capability usage
- offline, reconnect, background, and retry behavior
- accessibility labels, dynamic type, reduce motion, and screen reader order
- native module, bridge, or webview dependencies

If the product is not app, write `Not in scope`.

## Shared Domain And UI State Model

Convert route fixtures into UI-facing implementation state:

- domain entities and stable ids
- route state and UI state ownership
- loading, empty, error, disabled, permission, optimistic, retry, and async branch states
- client-side validation rules
- cache invalidation or refresh triggers
- feature flags and experiment states

## API And Data Contracts

For each prototype fixture group that needs a receiving-side replacement, document:

- service or endpoint name
- method or event direction when known
- request shape
- response shape
- error shape
- auth or permission requirement
- owning team or system
- routes or screens that consume it
- fixture group being replaced
- adapter interface: `pending` at handoff time; assembly fills in the `<Feature>DataSource` method, UI model, mock path, injection site, schema authority/source, and integration owner/status so the data-integration owner has a predictable replacement point
- semantics — the five entries the data-integration pass confirms before wiring, as `key: value` shorthand separated by semicolons:
  - `pagination`: `cursor`, `offset`, or `none`
  - `sort` / `filter`: the fields the caller may pass
  - `freshness`: `static`, `poll` (with interval), or `push` (with transport)
  - `mutation`: the verb, idempotency, and whether optimistic updates are allowed
  - `errors`: the retryable / terminal / reauthentication split

  For example `pagination: cursor; freshness: poll 30s; mutation: none; errors: retryable/reauth`. An unresolved entry is `unknown (owner: <team>)`, never a guess. `validate_prototype.py` does not judge this cell's content — it is guidance for station 5, and `production-data-integration` asks the named owner for anything missing before it wires that seam.

If an API is unknown, document the UI data need and name the decision owner; keep it proposed/open in Data Authority without inventing endpoints or DTOs. A UI schema authorizes UI/mock types only. Real transport DTOs require confirmed transport evidence, and a mapper adapts them to the UI model when shapes differ. An empty contracts array is valid for a Fake-only handoff.

## Remote Config Intent

Record the controlled region, intended product behavior, demonstrated states, unresolved decisions, and RD owner. Text is enough for this stage. Do not infer production defaults/fallbacks from fixtures or invent key, provider, polling, cache, permission, or rollout details. Confirmed product behavior supports UI/mock assembly while dependent real integration awaits its decisions.

## Frontend Handoff Acceptance

Define handoff-ready checks separately from Storybook checks and from final production integration checks:

- production route or screen target is identified for the real app shell
- every fixture has Fake values and a declared schema scope/status; confirmed transport sources or explicit open decisions identify what a receiver may wire later
- route transitions match `FLOW_SPEC.md`
- accessibility and responsive behavior match `UI_SPEC.md`
- web or app platform notes are specified or explicitly marked `Not in scope`
- fixture states cover successful, empty, loading, error, and permission paths in scope
- analytics, feature flags, auth, persistence, and security requirements are noted as handoff inputs or open decisions
- demo confirmation and Semantic Review are named, dated, and scoped; suggestions have not become normative requirements and superseded clauses are absent from active paths
- visible-route transitions have explicit navigation/return and motion intent; custom motion references an existing explicit Flow Spec anchor

## Integration Ownership

Ownership is three-stage; each stage hands a contract to the next. State all three explicitly:

- Stage 1 — Prototype (this handoff, `storybook-product-prototype`): UI behavior, route flow, interaction triggers, visual states, deterministic fixtures, and API/data contract expectations.
- Stage 2 — Frontend assembly (`frontend-product-implementation`): production routes/screens, interaction states, typed adapter interfaces, and mock adapters backed by these fixtures. This stage delivers a replaceable seam; it never wires real integrations.
- Stage 3 — Data integration (the named owner below): real API clients, data sources, auth/session integration, cache policy, storage, persistence, environment configuration, and final production tests.

Include a `Data Integration Ownership` field naming the stage-3 receiver — a team, a system, a person, or the `production-data-integration` skill. When the owner is unknown, record an open decision in `Open Product Decisions` with an owner responsible for resolving it; never leave the field absent in a new handoff. `validate_prototype.py --handoff-ready` reports a missing field on a legacy handoff as a warning.

- If a later stage changes a decision, route, data shape, or branch state, identify and update all affected docs, flow/data/meta, fixtures, exports, and tests, supersede replaced decisions, and re-review before a new manifest. Receivers record both `docsDigest` and version-2 `artifactsDigest` and verify source integrity at ingestion and before completion. Hashes do not confer data authority.

## Storybook-Only Boundaries

List what must not be treated as production code:

- `parameters.prototype`
- `prototypeRoute` and `prototypeFlowPreview` query modes
- `data-prototype-root` and `data-prototype-route-preview`
- Static Flow export components
- local deterministic fixtures except as test data
- Prototype Inspector layout and Storybook toolbar behavior

Also list prototype files or components that can be extracted into frontend production code with changes.

## Design System Continuity

Record the discovery results so the receiving implementation inherits them instead of re-deriving them. This section records facts; it does not restate governance rules.

- Token namespace record: the token prefix(es) in use and the file paths that define them, from the `UI_SPEC.md` Token Binding section, or `none` when the project has no token system.
- Component Map echo: the per-route component mapping (or a link to `UI_SPEC.md`).
- Per-screen composition echo: for each route, the components that compose it, each with its origin (`shared`, `local`, or `promoted`) and its story id in backticks when one exists — mirroring `meta.components` (contract in `references/storybook-integration.md`). Format: one lead-in bullet with one indented sub-bullet per route (for example `` Route `entry-route`: ... ``); never column-0 `` - `kebab-id`: `` bullets, and leave no bracketed placeholder spans in the final handoff.
- Promotion candidates: locally created components from Component Gaps. Record each candidate's status: `promoted` — the team-confirmed component was promoted into the hub's shared component library (list its shared-component path and story id) — or `local` — it stays inside the prototype (list its prototype file path and the routes/regions that use it). Production can port `promoted` components from the hub directly and may promote remaining `local` candidates into its own design system.
- Receiving pass: the `frontend-product-implementation` pass should run `ds-governance` discovery and gates against this record; when no token system existed, follow its token-bootstrap reference.

## Open Product Decisions

Record unresolved choices that would change implementation:

For each decision record `status` (proposed/open/confirmed/superseded), source, owner, scope, affected behavior, and replacement when superseded. A Builder suggestion is proposed, not a production requirement: a suggested `reason` absent from the confirmed `delete_email_failed` event must not appear in formal event payloads or acceptance criteria. Continue independent confirmed work; do not guess blocked behavior.

- platform target or routing model
- API ownership or response shape
- auth, permission, or security policy
- persistence, caching, offline, or sync behavior
- analytics taxonomy or event names
- design-system component gaps
- release gates, feature flags, or rollout plan
