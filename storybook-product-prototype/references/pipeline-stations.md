# Pipeline Stations

Use this reference to see where a skill sits in the prototype-to-production chain, what each station consumes and produces, and which gate must pass before the next station starts. It is the shared map for `storybook-product-prototype`, `frontend-product-implementation`, `native-product-implementation`, and `production-data-integration`.

## The Six Stations

| # | Station | Owner | Input | Output | Gate |
| --- | --- | --- | --- | --- | --- |
| 1 | Prototype authoring | `storybook-product-prototype` | Product intent, design-system source, existing components | Prototype folder, seven handoff docs, fixtures (`.ts` + `fixtures/*.json`), flow metadata, Storybook stories | `validate_prototype.py`, project typecheck, Storybook build |
| 2 | Team demo confirmation | The product team (human) | The Storybook story and UI Flow | `Review Status: confirmed` with reviewer, date, and covered scope | **Human gate.** No automation passes this station |
| 3 | Handoff finalization | `storybook-product-prototype` | Demo-confirmed direction, scoped Semantic Review, classified Data Authority | Version-2 `docs/HANDOFF_MANIFEST.json`, optional `docs/TOKENS.json` and `docs/flow.json` | `--handoff-ready`: review evidence, authority structure, navigation/motion, carrier cross-checks and hashes |
| 4 | Frontend assembly, mock mode | `frontend-product-implementation` (web) / `native-product-implementation` (iOS, Android) | Manifest digests, docs, `TOKENS.json`, Fake fixtures, classified UI schemas | Production routes/screens, UI models, typed `<Feature>DataSource` + mock, authority-aware `IMPLEMENTATION_MAP.md` | design-system governance gates, mock-mode walkthrough, implementation validation, native build/test, source integrity check |
| 5 | Data integration | `production-data-integration` | Confirmed transport contracts/sources and semantics, Data Adapter Seams, UI models and Fake examples | Real clients/auth/cache/persistence, DTO-to-UI mappers, swapped injection points, contract tests | Real payload tests against confirmed source contracts, mapper tests, every `AC-P (integration)` criterion settled |
| 6 | Visual and acceptance QA | `ui-pixel-align-report`, `ui-compare-to-reference` | Running production build, prototype Storybook | Pixel-alignment evidence, applied visual fixes, completed traceability | Every Scope `B` surface compared, acceptance traceability fully resolved |

## The Platform Fork

The fork sits **after station 3**, not before it. Stations 1–3 are platform-neutral: PRD, flow state machine, acceptance criteria, scoped JSON Schemas, and DTCG tokens travel in one handoff and manifest. Demo confirmation, semantic review, and each data/analytics/config contract's confirmation remain independent; see [handoff-authority.md](handoff-authority.md).

From station 4 on, the execution skill differs by target:

- Web (React, Vue, Angular, Svelte, meta-frameworks) → `frontend-product-implementation`
- iOS SwiftUI and Android Compose → `native-product-implementation`

Both consume the same documents through the same gates and produce the same `IMPLEMENTATION_MAP.md` shape, so station 5 and station 6 do not care which branch produced the app. When a product ships on more than one platform, run station 4 once per platform against the same manifest, and read the `Scope(web)` / `Scope(app)` columns — a region that already ships on web is routinely new on app.

## Gate Rules That Cross Stations

- **Nothing skips station 2.** `--handoff-ready` fails while `Review Status` is `pending`, and every station-4 skill re-checks the status at ingestion. Docs that bypassed the validator do not bypass the receiving check.
- **The manifest pins the version.** Station 4 records the consumed `docsDigest`; `--verify-manifest` at the prototype and `validate_implementation.py` at the implementation both detect a handoff that moved underneath an in-flight implementation.
- **Scope travels verbatim.** The `A`/`B`/`C`/`U` classification is authored once at station 1–3 and copied, never re-derived, at station 4. `A` needs repo evidence; `U` is a blocking question.
- **Acceptance ids travel end to end.** `AC-S-*` is settled at station 1, `AC-H-*` at station 3, `AC-P (assembly)` at station 4's mock walkthrough, and `AC-P (integration)` at station 5. Station 6 confirms the table is fully resolved.
- **Data wiring never happens before station 5.** Station 4 delivers a replaceable seam and hands the replacement to the named owner in `Data Integration Ownership`.

## Encoding The Pipeline For Re-runs

`agent-automation-orchestrate` can encode these stations as an ordered, resumable task contract. The example below is a template: replace every placeholder command with the project's real command, and treat that skill's own config contract as authoritative for the schema.

```jsonc
// .agent-automation/config.json — template, adapt per project
{
  "project": "<project-name>",
  "tasks": [
    {
      "id": "prototype-authoring",
      "station": 1,
      "skill": "storybook-product-prototype",
      "verify": [
        "python3 <skill-root>/scripts/validate_prototype.py <prototype-folder>",
        "<typecheck command>",
        "<storybook build command>"
      ]
    },
    {
      "id": "demo-confirmation",
      "station": 2,
      "type": "designer-decision",
      "prompt": "Review the Storybook demo and UI Flow. Confirm the product direction, or list what must change.",
      "produces": "Review Status: confirmed in docs/PRODUCTION_HANDOFF.md"
    },
    {
      "id": "handoff-finalization",
      "station": 3,
      "skill": "storybook-product-prototype",
      "requires": ["demo-confirmation"],
      "verify": [
        "python3 <skill-root>/scripts/validate_prototype.py <prototype-folder> --handoff-ready --changelog \"<summary>\"",
        "python3 <skill-root>/scripts/export_prototype_contracts.py <prototype-folder>",
        "python3 <skill-root>/scripts/export_flow.py <prototype-folder>"
      ],
      "produces": "docs/HANDOFF_MANIFEST.json"
    },
    {
      "id": "frontend-assembly",
      "station": 4,
      "skill": "frontend-product-implementation",
      "requires": ["handoff-finalization"],
      "verify": [
        "<framework typecheck/test/build commands>",
        "python3 <fpi-skill-root>/scripts/validate_implementation.py --handoff <docs-dir> --map IMPLEMENTATION_MAP.md --repo <production-root>"
      ]
    },
    {
      "id": "native-assembly",
      "station": 4,
      "skill": "native-product-implementation",
      "requires": ["handoff-finalization"],
      "optional": true,
      "verify": [
        "<xcodebuild or gradlew commands>",
        "python3 <fpi-skill-root>/scripts/validate_implementation.py --handoff <docs-dir> --map IMPLEMENTATION_MAP.md --repo <native-root>"
      ]
    },
    {
      "id": "data-integration",
      "station": 5,
      "skill": "production-data-integration",
      "requires": ["frontend-assembly"],
      "verify": ["<contract test command>"]
    },
    {
      "id": "visual-acceptance-qa",
      "station": 6,
      "skill": "ui-pixel-align-report",
      "requires": ["data-integration"],
      "verify": ["<visual comparison run>", "<acceptance traceability review>"]
    }
  ]
}
```

Notes on the template:

- Station 2 stays a human stop. Automating it defeats the confirmation it exists to record.
- `native-assembly` is marked optional so a web-only project runs the same config unchanged; a native-only project marks `frontend-assembly` optional instead.
- Every station-4 branch depends on `handoff-finalization`, so a re-run after a prototype change re-derives the manifest before any implementation restarts.
- Station 5 depends on whichever station-4 branch produced the app under integration; list both when both ship.
