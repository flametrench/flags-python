# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""InMemoryFlagStore — spec-conformant in-memory FlagStore."""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from typing import Any, Callable

from flametrench_ids import generate

from .bucket import bucket
from .errors import InvalidFormatError, NotFoundError, PreconditionError
from .types import AuthzRule, Flag, PercentageRule, Rule

_KEY_RE = re.compile(r"^[a-z0-9._-]{1,128}$")
_ORG_ID_RE = re.compile(r"^org_[0-9a-f]{32}$")
_RELATION_RE = re.compile(r"^[a-z_]{2,32}$")
_VALID_RULE_KINDS = {"authz", "percentage"}

CheckFn = Callable[[str, str, str, str], bool]
"""check(subject_id, relation, object_type, object_id) -> bool"""


def _parse_rule(raw: dict[str, Any]) -> Rule:
    kind = raw.get("kind")
    if kind not in _VALID_RULE_KINDS:
        raise InvalidFormatError("rules")
    variant = raw.get("variant")
    if not isinstance(variant, bool):
        raise InvalidFormatError("rules")

    if kind == "authz":
        relation = raw.get("relation", "")
        if not _RELATION_RE.match(relation):
            raise InvalidFormatError("relation")
        obj = raw.get("object", {})
        if not isinstance(obj.get("type"), str) or not isinstance(obj.get("id"), str):
            raise InvalidFormatError("rules")
        return AuthzRule(
            kind="authz",
            relation=relation,
            object_type=obj["type"],
            object_id=obj["id"],
            variant=variant,
        )

    # kind == "percentage"
    bp = raw.get("basis_points")
    if not isinstance(bp, int) or not (0 <= bp <= 10000):
        raise InvalidFormatError("basis_points")
    return PercentageRule(kind="percentage", basis_points=bp, variant=variant)


def _validate_and_parse(
    scope: str,
    key: str,
    rules: list[dict[str, Any]],
) -> tuple[list[Rule], None]:
    if not _ORG_ID_RE.match(scope):
        raise InvalidFormatError("scope")
    if not _KEY_RE.match(key):
        raise InvalidFormatError("key")
    parsed = [_parse_rule(r) for r in rules]
    return parsed, None


class InMemoryFlagStore:
    """Append-on-write in-memory FlagStore.

    Flags are held in two indexes: by ``flag_<32hex>`` id and by
    ``(scope, key)`` for fast key-based lookup. ``create`` validates
    all inputs and enforces key uniqueness within scope.

    ``evaluate`` accepts an optional ``check_fn`` callable for authz-rule
    resolution. When not supplied, authz rules never match (safe default).
    """

    def __init__(self) -> None:
        self._flags: dict[str, Flag] = {}
        self._by_scope_key: dict[tuple[str, str], str] = {}  # (scope, key) → id

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create_flag(
        self,
        *,
        scope: str,
        key: str,
        enabled: bool = True,
        default_variant: bool = False,
        rules: list[dict[str, Any]] | None = None,
    ) -> Flag:
        parsed_rules, _ = _validate_and_parse(scope, key, rules or [])
        if (scope, key) in self._by_scope_key:
            raise PreconditionError(f"Flag key {key!r} already exists in scope {scope!r}")
        now = datetime.now(timezone.utc)
        flag_id = generate("flag")
        flag = Flag(
            id=flag_id,
            scope=scope,
            key=key,
            enabled=enabled,
            default_variant=default_variant,
            rules=tuple(parsed_rules),
            created_at=now,
            updated_at=now,
        )
        self._flags[flag_id] = flag
        self._by_scope_key[(scope, key)] = flag_id
        return flag

    def get_flag(self, flag_id: str) -> Flag:
        flag = self._flags.get(flag_id)
        if flag is None:
            raise NotFoundError(f"Flag not found: {flag_id!r}")
        return flag

    def get_flag_by_key(self, scope: str, key: str) -> Flag:
        flag_id = self._by_scope_key.get((scope, key))
        if flag_id is None:
            raise NotFoundError(f"Flag key {key!r} not found in scope {scope!r}")
        return self._flags[flag_id]

    def update_flag(
        self,
        flag_id: str,
        *,
        enabled: bool | None = None,
        default_variant: bool | None = None,
        rules: list[dict[str, Any]] | None = None,
    ) -> Flag:
        flag = self._flags.get(flag_id)
        if flag is None:
            raise NotFoundError(f"Flag not found: {flag_id!r}")

        new_enabled = flag.enabled if enabled is None else enabled
        new_default = flag.default_variant if default_variant is None else default_variant
        new_rules: tuple[Rule, ...]
        if rules is None:
            new_rules = flag.rules
        else:
            parsed, _ = _validate_and_parse(flag.scope, flag.key, rules)
            new_rules = tuple(parsed)

        updated = dataclasses.replace(
            flag,
            enabled=new_enabled,
            default_variant=new_default,
            rules=new_rules,
            updated_at=datetime.now(timezone.utc),
        )
        self._flags[flag_id] = updated
        return updated

    def delete_flag(self, flag_id: str) -> None:
        flag = self._flags.pop(flag_id, None)
        if flag is None:
            raise NotFoundError(f"Flag not found: {flag_id!r}")
        self._by_scope_key.pop((flag.scope, flag.key), None)

    # ── Evaluation ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        key: str,
        subject_id: str,
        scope: str,
        check_fn: CheckFn | None = None,
    ) -> bool:
        """Evaluate flag ``key`` for ``subject_id`` within ``scope``.

        Returns ``False`` (safe default) for undefined flags.
        ``authz`` rules are evaluated via ``check_fn``; if not supplied they
        never match.
        """
        flag_id = self._by_scope_key.get((scope, key))
        if flag_id is None:
            return False
        flag = self._flags[flag_id]

        if not flag.enabled:
            return flag.default_variant

        for rule in flag.rules:
            if isinstance(rule, AuthzRule):
                if check_fn is not None and check_fn(
                    subject_id, rule.relation, rule.object_type, rule.object_id
                ):
                    return rule.variant
            else:  # PercentageRule
                if bucket(flag.key, subject_id) < rule.basis_points:
                    return rule.variant

        return flag.default_variant
