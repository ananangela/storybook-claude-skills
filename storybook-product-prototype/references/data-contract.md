# Data Contract

Read [handoff-authority.md](handoff-authority.md) for the shared authority registry, decision status, source evidence, and review contract. Fixture values are always Fake; their schema may describe a UI model or a separately confirmed transport shape.

Use this reference when creating `DATA_SPEC.md` and `<featurePrototypeData>.ts`.

## Fixture Rules

- Keep fixtures local and deterministic.
- Author every fixture group in two carriers with the same values: typed data in the `.ts` file, and language-neutral JSON at `fixtures/<group>.json` inside the prototype folder. The JSON carrier is what native platforms and the receiving mock adapters load; `validate_prototype.py --handoff-ready` cross-checks the two.
- Use existing component prop types when possible.
- Name fixture groups by route or domain.
- Include branch fixtures when the UI Flow contains branch nodes.
- Include empty, loading, disabled, and error fixtures when those states are in scope.
- Do not call live product APIs from a prototype.
- For frontend handoff, classify every fixture group in Data Authority. Identify its UI need and confirmed source or open/proposed receiving decision; an invented API, storage, flag, or static contract is not required to complete UI/mock assembly.
- Do not wire real data sources, auth/session, backend clients, cache, storage, or persistence inside the prototype unless the user explicitly scopes that work.

## Data Spec Sections

Use these sections:

```markdown
# Data Spec

## Source Of Truth

## Data Authority

## Fake Data

## Real Data Contract

## Fixture Inventory

## Route Data Requirements

## Data Schemas (JSON Schema)

## API Replacement Points

## Remote Config Intent

## State And Branch Fixtures

## AI Update Rules
```

## JSON Schema Blocks

The `Data Schemas (JSON Schema)` section holds one fenced `json` block per fixture group, under its group heading, describing the classified UI entity/state shape or source-backed transport shape. Write or update a block whenever a fixture group is created or changed. Web, iOS, and Android may generate TypeScript, Codable, or kotlinx.serialization UI/mock types from a `ui-model` schema. Generating DTOs from that block requires `schemaScope: transport`, `status: confirmed`, and complete source evidence. Alternatively, a separate confirmed API contract may reference the formal transport schema; generate DTOs from that source while the fixture remains a UI model, then map between them. Fake values never define backend truth. Do not parse the separate Data Authority registry as a JSON Schema.

## API Replacement Points

For each identified future API or service, record the contract id, status, source, owner, and affected UI behavior. Document the following only when confirmed; otherwise record the missing decision and owner without inventing a value:

- endpoint or service name
- method if known
- request shape
- response shape
- owning team or source
- routes that consume it
- fixture group that currently mocks it
- auth, permission, cache, persistence, or offline constraints when known
- receiving implementation owner for real data wiring
- the five semantics the data-integration pass must know before it can wire anything:
  - `pagination`: `cursor`, `offset`, or `none` — and the parameter and response fields that carry it
  - `sort` / `filter`: which fields the caller may pass
  - `freshness`: `static`, `poll` (with interval), or `push` (with transport)
  - `mutation`: create/update/delete, whether it is idempotent, whether optimistic updates are allowed
  - `errors`: which classes are retryable, which are terminal, which require reauthentication

Record an unresolved semantic as `unknown` with the owner who answers it. Never guess one — a missing entry costs one question, a wrong one ships as a silent product decision (an invented poll interval, a pagination scheme the backend does not implement).

Keep a Fake-only `contracts: []` handoff valid. A proposed/open contract is a question for the receiving owner, not an executable transport specification. If the confirmed real DTO differs, the receiver maps it to the UI model and tests against the real source contract.

## Remote Config Intent

Text describing the controlled region, intended product behavior, demonstrated states, unresolved defaults/fallbacks, and RD owner is sufficient for prototype handoff. Key, provider, polling, cache, permission, and rollout details remain open without confirmed evidence. A demonstrated fixture state is not a production default. Continue independent UI/mock work; defer only the dependent real integration.

## Data Invariants

Document invariants that UI and tests rely on, such as:

- stable ids for route keys
- required fields for each card or row
- direction or status values controlling visual state
- branch fixture values that trigger success and error flows
- fixture fields that must remain stable across web and app frontend implementations
