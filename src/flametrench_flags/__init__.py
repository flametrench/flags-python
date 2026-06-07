# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""flametrench-flags — feature-flag primitive for Flametrench v0.4 (ADR 0021).

See the upstream specification at
https://github.com/flametrench/spec/blob/main/decisions/0021-flags-primitive.md.

Targeting reuses authz (ADR 0001) via an injected check_fn, plus deterministic
SHA-256-based percentage bucketing pinned for cross-SDK identity.
"""

from .bucket import bucket
from .errors import FlagError, InvalidFormatError, NotFoundError, PreconditionError
from .in_memory import InMemoryFlagStore
from .types import AuthzRule, Flag, PercentageRule, Rule

__all__ = [
    "AuthzRule",
    "Flag",
    "FlagError",
    "InMemoryFlagStore",
    "InvalidFormatError",
    "NotFoundError",
    "PercentageRule",
    "PreconditionError",
    "Rule",
    "bucket",
]

__version__ = "0.4.0"
