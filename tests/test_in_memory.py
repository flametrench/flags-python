# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for InMemoryFlagStore and bucket()."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from flametrench_ids import generate

from flametrench_flags import (
    ConflictError,
    Flag,
    InMemoryFlagStore,
    InvalidFormatError,
    NotFoundError,
    bucket,
)

_VALID_SCOPE = "org_" + "0" * 32


def _store() -> InMemoryFlagStore:
    return InMemoryFlagStore()


def _create_minimal(store: InMemoryFlagStore, **kwargs: object) -> Flag:
    defaults: dict[str, object] = {
        "scope": _VALID_SCOPE,
        "key": "test-flag",
        "enabled": True,
        "default_variant": False,
        "rules": [],
    }
    defaults.update(kwargs)
    return store.create_flag(**defaults)  # type: ignore[arg-type]


# ─── Deterministic bucketing (ADR 0021 §Deterministic bucketing) ─────────────


class TestBucket:
    def test_returns_int_in_range(self):
        b = bucket("new-checkout", "usr_" + "0" * 32)
        assert isinstance(b, int)
        assert 0 <= b <= 9999

    def test_known_vector_new_checkout(self):
        # Cross-SDK pinned vector: key=new-checkout, subject=usr_0190f2a81b3c7abc8123000000000002
        assert bucket("new-checkout", "usr_0190f2a81b3c7abc8123000000000002") == 9557

    def test_known_vector_new_checkout_aaa(self):
        assert bucket("new-checkout", "usr_" + "a" * 32) == 4983

    def test_known_vector_kill_switch(self):
        assert bucket("kill-switch", "usr_0190f2a81b3c7abc8123000000000002") == 9830

    def test_deterministic_same_inputs(self):
        b1 = bucket("flag-x", "usr_" + "1" * 32)
        b2 = bucket("flag-x", "usr_" + "1" * 32)
        assert b1 == b2

    def test_different_keys_different_buckets(self):
        subject = "usr_" + "2" * 32
        b1 = bucket("flag-alpha", subject)
        b2 = bucket("flag-beta", subject)
        assert b1 != b2

    def test_wire_format_matters(self):
        # The spec mandates full wire format (usr_<32hex>), NOT the raw hex
        b_wire = bucket("k", "usr_" + "a" * 32)
        b_bare = bucket("k", "a" * 32)
        assert b_wire != b_bare


# ─── Create ───────────────────────────────────────────────────────────────────


class TestCreate:
    def test_returns_flag_with_flag_id(self):
        store = _store()
        flag = _create_minimal(store)
        assert flag.id.startswith("flag_")
        assert len(flag.id) == 37  # flag_ + 32 hex

    def test_server_sets_timestamps(self):
        before = datetime.now(timezone.utc)
        store = _store()
        flag = _create_minimal(store)
        after = datetime.now(timezone.utc)
        assert before <= flag.created_at <= after
        assert before <= flag.updated_at <= after

    def test_created_at_equals_updated_at_on_create(self):
        store = _store()
        flag = _create_minimal(store)
        assert flag.created_at == flag.updated_at

    def test_fields_stored_verbatim(self):
        store = _store()
        flag = store.create_flag(
            scope=_VALID_SCOPE,
            key="my-feature",
            enabled=False,
            default_variant=True,
            rules=[],
        )
        assert flag.scope == _VALID_SCOPE
        assert flag.key == "my-feature"
        assert flag.enabled is False
        assert flag.default_variant is True

    def test_each_create_unique_id(self):
        store = _store()
        ids = {_create_minimal(store, key=f"flag-{i}").id for i in range(5)}
        assert len(ids) == 5

    def test_duplicate_key_in_scope_raises_conflict(self):
        store = _store()
        _create_minimal(store, key="dup-key")
        with pytest.raises(ConflictError):
            _create_minimal(store, key="dup-key")

    def test_same_key_different_scope_ok(self):
        store = _store()
        scope_a = "org_" + "a" * 32
        scope_b = "org_" + "b" * 32
        f1 = store.create_flag(scope=scope_a, key="shared-key")
        f2 = store.create_flag(scope=scope_b, key="shared-key")
        assert f1.id != f2.id

    def test_flag_is_immutable(self):
        store = _store()
        flag = _create_minimal(store)
        with pytest.raises((TypeError, AttributeError)):
            flag.enabled = False  # type: ignore[misc]

    def test_rules_stored_as_tuple(self):
        store = _store()
        flag = _create_minimal(store, rules=[
            {"kind": "percentage", "basis_points": 5000, "variant": True}
        ])
        assert isinstance(flag.rules, tuple)
        assert len(flag.rules) == 1


# ─── Get ──────────────────────────────────────────────────────────────────────


class TestGet:
    def test_get_by_id_returns_flag(self):
        store = _store()
        created = _create_minimal(store)
        fetched = store.get_flag(created.id)
        assert fetched.id == created.id

    def test_get_by_key_returns_flag(self):
        store = _store()
        created = _create_minimal(store, key="lookup-me")
        fetched = store.get_flag_by_key(_VALID_SCOPE, "lookup-me")
        assert fetched.id == created.id

    def test_get_unknown_id_raises_not_found(self):
        store = _store()
        with pytest.raises(NotFoundError):
            store.get_flag(generate("flag"))

    def test_get_unknown_key_raises_not_found(self):
        store = _store()
        with pytest.raises(NotFoundError):
            store.get_flag_by_key(_VALID_SCOPE, "no-such-flag")


# ─── Update ───────────────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_enabled(self):
        store = _store()
        flag = _create_minimal(store, enabled=True)
        updated = store.update_flag(flag.id, enabled=False)
        assert updated.enabled is False

    def test_update_default_variant(self):
        store = _store()
        flag = _create_minimal(store, default_variant=False)
        updated = store.update_flag(flag.id, default_variant=True)
        assert updated.default_variant is True

    def test_update_rules_replaces(self):
        store = _store()
        flag = _create_minimal(store)
        updated = store.update_flag(flag.id, rules=[
            {"kind": "percentage", "basis_points": 2000, "variant": True}
        ])
        assert len(updated.rules) == 1

    def test_update_bumps_updated_at(self):
        store = _store()
        flag = _create_minimal(store)
        before = datetime.now(timezone.utc)
        updated = store.update_flag(flag.id, enabled=False)
        after = datetime.now(timezone.utc)
        assert before <= updated.updated_at <= after

    def test_update_preserves_created_at(self):
        store = _store()
        flag = _create_minimal(store)
        updated = store.update_flag(flag.id, enabled=False)
        assert updated.created_at == flag.created_at

    def test_update_unknown_raises_not_found(self):
        store = _store()
        with pytest.raises(NotFoundError):
            store.update_flag(generate("flag"), enabled=False)

    def test_partial_update_preserves_other_fields(self):
        store = _store()
        flag = _create_minimal(store, default_variant=True)
        updated = store.update_flag(flag.id, enabled=False)
        assert updated.default_variant is True

    def test_update_get_reflects_change(self):
        store = _store()
        flag = _create_minimal(store, enabled=True)
        store.update_flag(flag.id, enabled=False)
        fetched = store.get_flag(flag.id)
        assert fetched.enabled is False


# ─── Delete ───────────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_removes_flag(self):
        store = _store()
        flag = _create_minimal(store)
        store.delete_flag(flag.id)
        with pytest.raises(NotFoundError):
            store.get_flag(flag.id)

    def test_delete_frees_key(self):
        store = _store()
        flag = _create_minimal(store, key="recyclable")
        store.delete_flag(flag.id)
        flag2 = _create_minimal(store, key="recyclable")
        assert flag2.id != flag.id

    def test_delete_unknown_raises_not_found(self):
        store = _store()
        with pytest.raises(NotFoundError):
            store.delete_flag(generate("flag"))


# ─── Evaluate ─────────────────────────────────────────────────────────────────


class TestEvaluate:
    def test_undefined_flag_returns_false(self):
        store = _store()
        assert store.evaluate("no-such-flag", "usr_" + "0" * 32, _VALID_SCOPE) is False

    def test_disabled_flag_returns_default_variant(self):
        store = _store()
        _create_minimal(store, key="kill-sw", enabled=False, default_variant=True)
        assert store.evaluate("kill-sw", "usr_" + "0" * 32, _VALID_SCOPE) is True

    def test_disabled_flag_skips_rules(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="disabled-with-rule",
            enabled=False,
            default_variant=False,
            rules=[{"kind": "percentage", "basis_points": 10000, "variant": True}],
        )
        assert store.evaluate("disabled-with-rule", "usr_" + "0" * 32, _VALID_SCOPE) is False

    def test_no_rules_returns_default_variant(self):
        store = _store()
        _create_minimal(store, key="bare-flag", default_variant=True)
        assert store.evaluate("bare-flag", "usr_" + "0" * 32, _VALID_SCOPE) is True

    def test_percentage_10000_always_matches(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="full-rollout",
            rules=[{"kind": "percentage", "basis_points": 10000, "variant": True}],
        )
        for suffix in ("0" * 32, "a" * 32, "f" * 32):
            assert store.evaluate("full-rollout", f"usr_{suffix}", _VALID_SCOPE) is True

    def test_percentage_0_never_matches(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="zero-rollout",
            rules=[{"kind": "percentage", "basis_points": 0, "variant": True}],
        )
        for suffix in ("0" * 32, "a" * 32, "f" * 32):
            assert store.evaluate("zero-rollout", f"usr_{suffix}", _VALID_SCOPE) is False

    def test_percentage_deterministic_same_user(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="stable-flag",
            rules=[{"kind": "percentage", "basis_points": 5000, "variant": True}],
        )
        subj = "usr_" + "7" * 32
        r1 = store.evaluate("stable-flag", subj, _VALID_SCOPE)
        r2 = store.evaluate("stable-flag", subj, _VALID_SCOPE)
        assert r1 == r2

    def test_first_matching_rule_wins(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="ordered-rules",
            rules=[
                {"kind": "percentage", "basis_points": 10000, "variant": False},
                {"kind": "percentage", "basis_points": 10000, "variant": True},
            ],
        )
        # First rule (basis_points=10000) always matches → variant=False
        assert store.evaluate("ordered-rules", "usr_" + "0" * 32, _VALID_SCOPE) is False

    def test_authz_rule_matches_with_check_fn(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="authz-flag",
            rules=[{
                "kind": "authz",
                "relation": "editor",
                "object": {"type": "org", "id": _VALID_SCOPE},
                "variant": True,
            }],
        )
        # check_fn always returns True
        result = store.evaluate(
            "authz-flag", "usr_" + "0" * 32, _VALID_SCOPE,
            check_fn=lambda subj, rel, ot, oid: True,
        )
        assert result is True

    def test_authz_rule_no_match_falls_through(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="authz-fallback",
            default_variant=False,
            rules=[{
                "kind": "authz",
                "relation": "editor",
                "object": {"type": "org", "id": _VALID_SCOPE},
                "variant": True,
            }],
        )
        # check_fn always returns False → rule doesn't match → default_variant
        result = store.evaluate(
            "authz-fallback", "usr_" + "0" * 32, _VALID_SCOPE,
            check_fn=lambda *a: False,
        )
        assert result is False

    def test_authz_rule_no_check_fn_never_matches(self):
        store = _store()
        store.create_flag(
            scope=_VALID_SCOPE,
            key="authz-no-fn",
            default_variant=False,
            rules=[{
                "kind": "authz",
                "relation": "editor",
                "object": {"type": "org", "id": _VALID_SCOPE},
                "variant": True,
            }],
        )
        # No check_fn → authz rule never matches → default_variant=False
        assert store.evaluate("authz-no-fn", "usr_" + "0" * 32, _VALID_SCOPE) is False

    def test_percentage_specific_bucket_vector(self):
        # new-checkout + usr_0190f2a81b3c7abc8123000000000002 → bucket=9557
        # matches iff bucket < basis_points, so:
        #   basis_points=9558 → 9557 < 9558 → True
        #   basis_points=9557 → 9557 < 9557 → False
        #   basis_points=9556 → 9557 < 9556 → False
        # Use separate stores so the same key can be created each time.
        subj = "usr_0190f2a81b3c7abc8123000000000002"

        s1 = _store()
        s1.create_flag(
            scope=_VALID_SCOPE, key="new-checkout",
            rules=[{"kind": "percentage", "basis_points": 9558, "variant": True}],
        )
        assert s1.evaluate("new-checkout", subj, _VALID_SCOPE) is True

        s2 = _store()
        s2.create_flag(
            scope=_VALID_SCOPE, key="new-checkout",
            rules=[{"kind": "percentage", "basis_points": 9557, "variant": True}],
        )
        assert s2.evaluate("new-checkout", subj, _VALID_SCOPE) is False

        s3 = _store()
        s3.create_flag(
            scope=_VALID_SCOPE, key="new-checkout",
            rules=[{"kind": "percentage", "basis_points": 9556, "variant": True}],
        )
        assert s3.evaluate("new-checkout", subj, _VALID_SCOPE) is False


# ─── Validation ───────────────────────────────────────────────────────────────


class TestValidation:
    def test_scope_wrong_prefix_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, scope="usr_" + "0" * 32)
        assert exc_info.value.field == "scope"

    def test_scope_not_32hex_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, scope="org_tooshort")
        assert exc_info.value.field == "scope"

    def test_key_empty_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, key="")
        assert exc_info.value.field == "key"

    def test_key_too_long_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, key="a" * 129)
        assert exc_info.value.field == "key"

    def test_key_uppercase_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, key="My-Flag")
        assert exc_info.value.field == "key"

    def test_key_valid_with_separators_accepted(self):
        store = _store()
        flag = _create_minimal(store, key="my.flag-name_v2")
        assert flag.key == "my.flag-name_v2"

    def test_basis_points_negative_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, rules=[
                {"kind": "percentage", "basis_points": -1, "variant": True}
            ])
        assert exc_info.value.field == "basis_points"

    def test_basis_points_over_10000_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, rules=[
                {"kind": "percentage", "basis_points": 10001, "variant": True}
            ])
        assert exc_info.value.field == "basis_points"

    def test_basis_points_0_and_10000_valid(self):
        store = _store()
        flag = store.create_flag(
            scope=_VALID_SCOPE, key="edge-bp",
            rules=[
                {"kind": "percentage", "basis_points": 0, "variant": False},
                {"kind": "percentage", "basis_points": 10000, "variant": True},
            ],
        )
        assert len(flag.rules) == 2

    def test_rule_unknown_kind_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, rules=[
                {"kind": "regex", "pattern": ".*", "variant": True}
            ])
        assert exc_info.value.field == "rules"

    def test_authz_rule_bad_relation_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, rules=[{
                "kind": "authz",
                "relation": "EDITOR",  # uppercase — invalid
                "object": {"type": "org", "id": _VALID_SCOPE},
                "variant": True,
            }])
        assert exc_info.value.field == "relation"

    def test_authz_rule_missing_object_raises(self):
        store = _store()
        with pytest.raises(InvalidFormatError) as exc_info:
            _create_minimal(store, rules=[{
                "kind": "authz",
                "relation": "editor",
                "variant": True,
            }])
        assert exc_info.value.field == "rules"
