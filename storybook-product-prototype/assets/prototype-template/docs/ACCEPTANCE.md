# Acceptance Criteria

> Except for `Production Integration Acceptance`, these criteria accept the
> **Storybook prototype**, not the production delivery.
> Where a criterion names a surface that `PRODUCTION_HANDOFF.md` marks scope `A`, it
> checks that the prototype re-creates that existing surface faithfully enough to judge
> the new behavior against — it is not a request to build that surface in production.
> The build-or-not decision lives only in the Prototype To Frontend Map's `Scope` column.
>
> Every criterion carries a stable id: `AC-S-*` for Storybook prototype acceptance,
> `AC-H-*` for handoff acceptance, `AC-P-*` for production acceptance. The receiving
> implementation reports against these ids row by row; keep them stable once handed off.

## Storybook

- AC-S-001: The default story renders the interactive `__FEATURE_TITLE__` prototype.
- AC-S-002: `parameters.prototype.docs` exposes PRD, UI Spec, Flow Spec, Data Spec, Frontend Handoff, Implementation Guide, and Acceptance.
- AC-S-003: `parameters.prototype.flow.routes` contains every interactive route.
- AC-S-004: `parameters.prototype.flow.nodes` contains every flow-only branch node.
- AC-S-005: `parameters.prototype.flow.transitions` contains every user-triggered transition.
- AC-S-006: `parameters.prototype.components.routes` records each route's composing components with `origin` (`shared`, `local`, or `promoted`) and `storyId` links where resolvable.
- AC-S-007: UI Flow iframe previews can render a specific route through `prototypeRoute`.
- AC-S-008: The prototype route shell exposes `data-prototype-route-preview` for template-compatible preview measurement.
- AC-S-009: The prototype root keeps `data-prototype-root` for backward-compatible preview measurement.
- AC-S-010: `parameters.prototype.figmaExport.flowStoryId` points to the `StaticFlow` story.
- AC-S-011: The `StaticFlow` story renders route cards, flow-only nodes, and key transitions from the same metadata as UI Flow.

## Interaction

- AC-S-012: Initial route is `__ENTRY_ROUTE_ID__`.
- AC-S-013: [Every documented trigger changes route, updates local state, or is explicitly out of scope.]

## Data

- AC-S-014: Fixtures are local and deterministic, and every fixture group is mirrored in `fixtures/<group>.json`.
- AC-S-015: Every fixture group has a JSON Schema block and a Data Authority record in `DATA_SPEC.md`; values are Fake and UI-model confirmation is distinct from transport authority.

## Frontend Handoff

- AC-H-001: `PRODUCTION_HANDOFF.md` maps prototype routes to web routes, app screens, shared components, or open decisions.
- AC-H-002: Storybook-only boundaries are listed and are not described as production runtime requirements.
- AC-H-003: Each fixture's UI/mock use and schema authority are documented; confirmed transport records carry source evidence, while proposed/open real contracts have named owners and do not block independent assembly.
- AC-H-004: Integration ownership is three-stage and explicit, and `Data Integration Ownership` names the stage-3 receiver or records the open decision.
- AC-H-005: Frontend handoff acceptance criteria are separate from Storybook acceptance criteria and production integration acceptance.
- AC-H-006: Web and app implementation notes are either filled in or explicitly marked `Not in scope`.
- AC-H-007: Demo confirmation and Semantic Review are named, dated, and scoped; the review checks suggestions, superseded decisions, and updates to related documents, carriers, and tests.
- AC-H-008: Every transition entering a visible route declares motion and its navigation/return semantics; custom motion resolves to an explicit Flow Spec anchor.
- AC-H-009: Remote Config in scope describes the controlled region, intent, demonstration states, open decisions, and RD owner without inventing technical keys or production defaults.

## Engineering

- AC-S-016: Prototype-only CSS is scoped to `.__FEATURE_CSS_CLASS__`.
- AC-S-017: Existing reusable components are used before local markup.
- AC-S-018: Every route's composition is recorded in `meta.components` and origin-marked against the UI Spec Component Map and Component Gaps.
- AC-S-019: Static Flow export reads saved layout from `../prototypeFlowLayout`.
- AC-S-020: TypeScript passes in the target project.

## Production Integration Acceptance

> These criteria accept the **production delivery**. `(assembly)` criteria are
> verified by the frontend assembly pass in mock mode; `(integration)` criteria
> are verified only after the data-integration owner replaces the mock adapters.

- AC-P-001 (assembly): The primary journey from `__ENTRY_ROUTE_ID__` completes end to end in the production shell on mock adapters.
- AC-P-002 (assembly): Every in-scope branch state (loading, empty, error, disabled, permission) is reachable through interactions in mock mode.
- AC-P-003 (assembly): Every fixture group has a typed `__FEATURE_BASE_PASCAL__DataSource` interface, a `Mock__FEATURE_BASE_PASCAL__DataSource` implementation, and a recorded replacement point.
- AC-P-004 (integration): Real payloads conform to their confirmed transport source contract; a mapper translates them into the UI model and maps real failures to the documented UI states. Raw fixture-shape equality is not required.
- AC-P-005 (integration): [Auth, permission, persistence, offline, or analytics criteria that only real integration can verify — or delete this line when none apply.]
