# flametrench-flags

Feature-flag primitive for the Flametrench v0.4 platform ([ADR 0021](https://github.com/flametrench/spec/blob/main/decisions/0021-flags-primitive.md)).

## What this is

Boolean flags with two targeting rule types:
- **`authz`** — matches subjects that pass an `authz` `check()` (e.g. "editors of org O"). Targeting reuses the application's real authorization model; no separate DSL.
- **`percentage`** — deterministic SHA-256 rollout bucket, sticky and monotonic. Pinned for byte-identical behavior across all Flametrench SDKs.

## Install

```
pip install flametrench-flags
```

Requires Python ≥ 3.11 and `flametrench-ids >= 0.4.0`.

## Quick start

```python
from flametrench_flags import InMemoryFlagStore

store = InMemoryFlagStore()

store.create_flag(
    scope="org_...",
    key="new-checkout",
    enabled=True,
    default_variant=False,
    rules=[
        {"kind": "authz", "relation": "editor",
         "object": {"type": "org", "id": "org_..."}, "variant": True},
        {"kind": "percentage", "basis_points": 1000, "variant": True},
    ],
)

# Evaluate: inject your authz check_fn
result = store.evaluate(
    "new-checkout",
    subject_id="usr_...",
    scope="org_...",
    check_fn=lambda subj, rel, ot, oid: authz_store.check(subj, rel, ot, oid),
)
```

## License

Apache-2.0 © NDC Digital, LLC
