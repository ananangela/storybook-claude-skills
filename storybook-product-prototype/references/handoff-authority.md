# Handoff Authority

Use this contract when producing or receiving prototype data, decisions, and review evidence. `DATA_SPEC.md` remains the entry point. The Inspector reads its raw markdown; do not maintain a second authority registry in `meta.data`.

## Data Authority Registry

Write exactly one fenced `json` block under the level-two `Data Authority` heading. Keep JSON Schema blocks under the separate `Data Schemas (JSON Schema)` heading.

```json
{
  "schemaVersion": 1,
  "fixtures": [
    {
      "group": "examplePrototypeRows",
      "values": "fake",
      "schemaScope": "ui-model",
      "status": "proposed",
      "source": null,
      "owner": "Product team"
    }
  ],
  "contracts": []
}
```

Every fixture record declares `group`, `values`, `schemaScope`, `status`, `source`, and `owner`. `group` matches the TypeScript export, `fixtures/<group>.json`, and the fixture's schema heading. An optional `contractId` references a unique contract record's `id`.

Every contract record declares `id`, `kind`, `status`, `source`, and `owner`. `kind` is `api`, `analytics`, `remote-config`, `storage`, or `static`. A confirmed API contract may reference the separate formal transport schema used for DTOs. It does not turn a linked UI fixture schema into that transport schema; other contract kinds authorize only their own decision scope.

| Field | Allowed values and effect |
| --- | --- |
| `values` | Always `fake` for prototype fixtures, including fixtures that follow a confirmed transport schema. |
| `schemaScope` | `ui-model` generates UI and mock types; `transport` describes a request, response, or error shape. |
| `status` | `proposed`, `open`, `confirmed`, or `superseded`. Only a confirmed transport schema provides transport authority. |
| `source` | `null`, or the source object below. Every confirmed fixture or contract requires a complete source object. |
| `owner` | Named provider of the fixture requirement, or named decision owner for a contract. Empty owners are invalid. |

```json
{
  "reference": "docs/api/alerts.openapi.yaml#/components/schemas/AlertPage",
  "revision": "commit-or-document-revision",
  "confirmedBy": "Named RD reviewer",
  "confirmedOn": "2026-09-14"
}
```

Use the actual source revision and review evidence; examples above are not confirmation. `confirmedOn` is an ISO date. A confirmed UI model is still only a UI contract. Fake sample values never become real values through confirmation, and a confirmed API record never implicitly confirms a fixture's shape.

An empty `contracts` array is valid. A Fake-only handoff with proposed/open UI models and named owners can proceed to UI and mock assembly without an invented endpoint. Unclassified legacy data has no transport authority. Active fixture groups must be covered once each and cannot be superseded or depend on superseded contracts.

## Fake Data And Real Data Contract

`Fake Data` describes display examples, UI field meanings, deterministic branch states, and allowed mock use. `Real Data Contract` lists confirmed source references and unresolved integration decisions; when none exist, say that no real contract has been provided and retain an empty contracts array.

Receiving web/native implementations may generate TypeScript, Codable, or kotlinx.serialization UI model types from a UI schema and use fixture JSON for mock adapters. Transport evidence can come from a fixture explicitly classified `transport`/`confirmed`, or an independent `api` contract that is confirmed and whose source identifies the formal transport schema. In the latter case the linked fixture may remain `ui-model`/`proposed`; generate DTOs from the contract source and map them into the UI model. Never relabel a UI fixture as transport just to allow API work, and do not require the backend to match a prototype-shaped object.

For example, a confirmed response shaped as `data.items` with `nextCursor` can map into a UI model's `rows`. Test the real payload against its confirmed transport contract and the mapper against intended UI states. Raw equality to the Fake fixture is not a production contract test.

## Decisions And Unknowns

- `confirmed`: applies only to the decision's recorded source and scope.
- `proposed`: an author or Builder suggestion requiring a decision; never a normative production requirement or acceptance criterion.
- `open`: an unresolved choice with a named owner and the specific affected behavior.
- `superseded`: retained for history with its replacement identified; remove it from active instructions, fixtures, and acceptance paths.

Record scope, source, owner, affected behavior, and replacement where applicable in `Open Product Decisions`. Continue independent confirmed work. Unknown API details block the dependent integration, not unrelated UI/mock work; unknown navigation blocks completion of that flow.

If Builder proposes a `reason` parameter absent from the confirmed `delete_email_failed` analytics specification, retain it as a proposed analytics decision. Do not add it to the formal event payload or production acceptance criteria. A team approval of the product demo does not confirm the proposal.

## Remote Config Intent

Text is sufficient at prototype handoff. Record the controlled region, intended product behavior, demonstrated states, unresolved choices, and RD owner. Distinguish a demonstrated fixture state from a confirmed production default or fallback.

Without a confirmed source, keep key names, provider, request cadence, cache TTL, permissions, and rollout mechanics open. For example: "RD must be able to show or hide the promotion region; the prototype demonstrates both states. Production default and failure fallback are open; owner: Growth RD." This authorizes the two UI states, not a fabricated configuration key or default. Independent UI/mock assembly can proceed; dependent real integration waits for its decisions.

## Review Evidence

`PRODUCTION_HANDOFF.md` has two independent review records:

- `Review Status`: `Status: confirmed`, `Confirmed by`, `Confirmed on`, `Reviewed demo`, and `Scope`. Record the actual demo review and what was confirmed; keep status pending until that happens.
- `Semantic Review`: `Reviewed by`, `Reviewed on`, `Scope`, `Result: passed`, and `Related updates`. Record the actual document review; do not prefill passed merely because a script succeeded.

Semantic review checks that suggestions were not promoted into requirements, superseded decisions are absent from active paths, unknowns have owners and affected scope, and changed decisions are synchronized across Data Spec, Production Handoff, Flow Spec, Acceptance, fixtures, metadata, and affected tests. `Related updates` names the files reviewed or explains why a carrier was unaffected. Also review API/analytics/Remote Config source scope separately from the product demo.

The validator checks registry structure, source fields, review record completeness, and carrier consistency. A passing command or manifest hash does not verify external source truth or replace the semantic review.

## Updating A Consumed Handoff

Before editing, identify the changed decision and affected documents, flow/data/meta carriers, fixtures, exports, and tests. Mark replaced decisions superseded and remove their active instructions; update the related set together. Re-review the changed scope, then regenerate exports and run `--handoff-ready --changelog "<actual change>"` to publish a new local snapshot.

Manifest version 2 preserves `docsDigest` and adds `artifactsDigest`, covering docs, selected Flow/Data/Meta files, fixture JSON, and existing flow/token exports. Receivers record both digests and check source integrity at ingestion and before completion. A missing or version-1 manifest is incomplete provenance; neither it nor a new hash supplies missing data authority.

## Repo Skill Delivery

Record the skills actually used with the existing project installer and its opt-in `--record-usage` flag, an explicit skill list, and project scope. Do not use `all` or a global installation for handoff. Required/support dependencies are recorded separately from explicitly used skills; a future data-integration step is not automatically considered used.

The installer records relative installed paths, source version/dirty state, and content hashes in `docs/SKILL_USAGE.json`, and maintains relative links in managed blocks of `CLAUDE.md` and `AGENTS.md`. Preserve content outside those blocks. Verify the installed contents and record before handing the repo to another engineer; do not substitute machine-local absolute paths or external symlinks.
