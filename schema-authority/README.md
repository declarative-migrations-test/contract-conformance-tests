# Migration contract peer-authority fixture

This `*-test` repository keeps two independently authored source authorities:

- `main.tsp` — TypeSpec source authority;
- `authored.schema.json` — JSON Schema Draft 2020-12 source authority.

Neither source is generated from, ranked below, or allowed to overwrite the other. TypeSpec compilation produces a third lane—generated JSON Schema B—only under `.typespec-json-schema-validator/generated/`. Schema B is comparison evidence, never authority.

The exact-head workflow proves positive convergence and then mutates each authored lane independently. A TypeSpec-only semantic change and a JSON-Schema-only semantic change must both stop admission. The workflow also hashes both authored sources before comparison and verifies they remain unchanged afterwards.
