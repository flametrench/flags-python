# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""Feature-flag shape and supporting types (ADR 0021)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class AuthzRule:
    """Target subjects that pass an authz check (ADR 0021).

    Matches iff check(subject, relation, (object_type, object_id)) is true.
    """
    kind: Literal["authz"]
    relation: str
    object_type: str
    object_id: str
    variant: bool


@dataclass(frozen=True)
class PercentageRule:
    """Target a percentage of subjects by deterministic bucket (ADR 0021).

    basis_points is in [0, 10000]. Matches iff bucket(key, subject_id) < basis_points.
    """
    kind: Literal["percentage"]
    basis_points: int
    variant: bool


Rule = AuthzRule | PercentageRule


@dataclass(frozen=True)
class Flag:
    """A feature flag as stored and returned by FlagStore.

    ``id``, ``created_at``, and ``updated_at`` are set by the store.
    ``rules`` is an ordered list; first-match wins on evaluation.
    ``key`` is unique within ``scope`` and immutable after creation.
    """
    id: str
    scope: str
    key: str
    enabled: bool
    default_variant: bool
    rules: tuple[Rule, ...]
    created_at: datetime
    updated_at: datetime
