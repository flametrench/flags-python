# Changelog

## 0.4.0 — 2026-06-07

Initial release — Flametrench v0.4 feature-flag primitive (ADR 0021).

- `Flag` entity: `flag_<32hex>` id, scope, key, enabled, default_variant, rules, timestamps
- `AuthzRule` + `PercentageRule` types (ordered, first-match-wins)
- `bucket(key, subject_id)` — SHA-256 deterministic bucketing, pinned for cross-SDK identity (ADR 0021 §Deterministic bucketing)
- `InMemoryFlagStore`: CRUD (create/get/update/delete), by-key lookup, `evaluate()` with injected `check_fn` for authz rules
- `ConflictError`, `InvalidFormatError(field)`, `NotFoundError`
- Unit tests: bucket vectors, CRUD, evaluate logic, validation error paths
