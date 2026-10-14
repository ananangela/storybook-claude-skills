# Data Spec

## Source Of Truth

Prototype fixtures live in `__FEATURE_CAMEL__Data.ts`, mirrored one-to-one as language-neutral JSON in `fixtures/<group>.json` for non-TypeScript consumers and mock adapters. Their values are FAKE. The Data Authority registry below separately records schema scope and confirmation; product demo approval does not confirm an API, analytics parameter, or Remote Config key.

## Data Authority

This is the only authority registry; the Inspector reads it from this document. Every fixture group needs a record. `confirmed` requires a source object with `reference`, `revision`, `confirmedBy`, and `confirmedOn`; a confirmed UI model still has no transport authority.

```json
{
  "schemaVersion": 1,
  "fixtures": [
    {
      "group": "__FEATURE_CAMEL__Routes",
      "values": "fake",
      "schemaScope": "ui-model",
      "status": "proposed",
      "source": null,
      "owner": __OWNER_JSON__
    }
  ],
  "contracts": []
}
```

## Fake Data

- All fixture values are synthetic display or branch examples. They may drive UI models, mock adapters, and deterministic tests.
- Fixture field names and values do not establish backend DTOs, API endpoints, business rules, analytics parameters, or production configuration defaults.

## Real Data Contract

No real contract has been provided in this scaffold; the contracts array is empty. Keep it empty until a concrete contract or open/proposed integration decision is identified. Each contract records `id`, `kind` (`api`, `analytics`, `remote-config`, `storage`, or `static`), `status`, `source`, and its decision owner. An optional fixture `contractId` references that record.

Transport types require confirmed transport evidence: either a fixture explicitly marked `schemaScope: transport`/`status: confirmed`, or an independent confirmed API contract whose source identifies the formal transport schema. A UI fixture linked to that API may remain `ui-model`/`proposed`; generate the DTO from the separate contract source and map it to the UI model. Proposed/open contracts may support an implementation question; they cannot authorize real integration.

## Fixture Inventory

- `__FEATURE_CAMEL__Routes`: [Route fixtures or content blocks.]

## Route Data Requirements

- `__ENTRY_ROUTE_ID__`: [Required fixture groups.]

## Data Schemas (JSON Schema)

One fenced `json` block per fixture group, under its group heading. A `ui-model` schema generates only UI/mock types (TypeScript, Codable, kotlinx.serialization). Request, response, and error DTOs require a separately confirmed transport classification and source. Keep the schema and fixtures in sync without presenting Fake sample values as backend truth.

### `__FEATURE_CAMEL__Routes`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PrototypeRouteContent",
  "type": "object",
  "required": ["id", "title"],
  "properties": {
    "id": { "type": "string", "description": "Stable id used for keys and route mapping." },
    "title": { "type": "string", "description": "Display title." },
    "description": { "type": "string", "description": "Route-specific review copy or content." },
    "state": { "type": "string", "enum": ["default", "loading", "empty", "error"], "description": "Branch state this fixture drives, when present." }
  }
}
```

## API Replacement Points

- [Contract id or `none`]: [UI data need, affected route, fixture replacement, confirmed source or explicit proposed/open status, and owner. Do not invent an endpoint, request/response DTO, or production default.]

## Remote Config Intent

- Controlled region: [Named UI region or `Not in scope`.]
- Product intent and demonstrated states: [Intended behavior and Fake states shown in the prototype; distinguish them from production defaults.]
- Open decisions and RD owner: [Unresolved default/fallback or technical choices and the named owner. Key, provider, polling, cache, permissions, and rollout details remain open without confirmed sources.]

## Receiving Data Ownership

- Service owner: [Team, package, or system.]
- Auth and permission: [Requirement or unknown.]
- Cache and persistence: [Client cache, storage, offline behavior, or none.]
- Web/app parity: [Fields or states that must remain consistent across platforms.]
- Receiving implementation responsibility: real data source, API client, auth/session, storage, persistence, cache policy, and environment configuration.

## State And Branch Fixtures

- [Success, error, empty, loading, disabled, or async branch fixtures.]

## AI Update Rules

- Add fixture data before wiring a route.
- Keep fixtures deterministic.
- Mirror every fixture group as `fixtures/<group>.json` with the same values, and keep its JSON Schema block above in sync.
- Document any future API replacement in this file and in `__FEATURE_CAMEL__Meta.ts`.
- Mirror API/data contract expectations in `PRODUCTION_HANDOFF.md`.
- Do not wire real data sources in the prototype.
- Classify every fixture and contract in Data Authority. Keep fixture values `fake`, including under a confirmed transport schema; never derive confirmation from demo review or a validation pass.
- Keep suggestions `proposed`, unresolved choices `open` with owner and affected behavior, and replaced decisions `superseded` with their replacement. Remove superseded instructions from active docs, fixtures, metadata, and acceptance paths.
- Update the affected Data Spec, Production Handoff, Flow Spec, Acceptance, fixtures, metadata, and tests together; record that review before regenerating the handoff manifest.
