# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""Flametrench v0.4 conformance suite — Python harness for flags.

Tests the pinned deterministic bucketing algorithm (ADR 0021 §Deterministic
bucketing). The ``assign_bucket`` operation maps directly to the pure
``bucket(key, subject_id)`` function — no store state involved.

``runnable_today:false`` in the fixture until all 5 SDKs implement flags.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from flametrench_flags import InMemoryFlagStore, PreconditionError, bucket

_FIXTURES_DIR = Path(__file__).parent / "conformance" / "fixtures"


def _load_fixture(relative_path: str) -> dict[str, Any]:
    return json.loads((_FIXTURES_DIR / relative_path).read_text(encoding="utf-8"))


def _collect_tests(relative_path: str) -> list[Any]:
    fixture = _load_fixture(relative_path)
    return [pytest.param(t, id=t["id"]) for t in fixture["tests"]]


_ERROR_CLASSES: dict[str, type[Exception]] = {
    "PreconditionError": PreconditionError,
}


def _run_flag_steps(test: dict[str, Any]) -> None:
    store = InMemoryFlagStore()
    for step in test["steps"]:
        op = step["op"]
        inp = step["input"]
        expected = step.get("expected")
        if op == "create_flag":
            if expected and "error" in expected:
                error_class = _ERROR_CLASSES[expected["error"]]
                with pytest.raises(error_class):
                    store.create_flag(
                        scope=inp["scope"],
                        key=inp["key"],
                        enabled=inp.get("enabled", True),
                        default_variant=inp.get("default_variant", False),
                        rules=inp.get("rules") or [],
                    )
            else:
                store.create_flag(
                    scope=inp["scope"],
                    key=inp["key"],
                    enabled=inp.get("enabled", True),
                    default_variant=inp.get("default_variant", False),
                    rules=inp.get("rules") or [],
                )
        else:
            raise RuntimeError(f"Unknown fixture op: {op!r}")


# ─── flags.assign_bucket — deterministic bucketing (ADR 0021) ────────────────


@pytest.mark.parametrize("test_case", _collect_tests("flags/assign-bucket.json"))
def test_assign_bucket_conformance(test_case: dict[str, Any]) -> None:
    inp = test_case["input"]
    expected = test_case["expected"]["result"]
    actual = bucket(inp["key"], inp["subject_id"])
    assert actual == expected, (
        f"bucket({inp['key']!r}, {inp['subject_id']!r}) = {actual}, expected {expected}"
    )


# ─── flags.duplicate_key — PreconditionError on dup (scope, key) (ADR 0021) ──


@pytest.mark.parametrize("test_case", _collect_tests("flags/duplicate-key.json"))
def test_duplicate_key_conformance(test_case: dict[str, Any]) -> None:
    _run_flag_steps(test_case)
