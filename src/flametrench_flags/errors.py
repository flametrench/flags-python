# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""FlagStore error taxonomy (cross-cutting, ADR 0019 / ADR 0021 §Constraints).

Uniform taxonomy shared with audit, identity, and tenancy:
- ``InvalidFormatError`` — shape/value violation; carries a ``field``
  discriminator naming the offending input.
- ``NotFoundError`` — flag does not exist or is outside the caller's scope.
- ``PreconditionError`` — state/constraint violation (duplicate ``key`` within
  ``scope``); uses the house-uniform ADR 0019 error class, matching PHP/Java/Node.
"""

from __future__ import annotations


class FlagError(Exception):
    """Base class for all flametrench-flags errors."""


class InvalidFormatError(FlagError):
    """An input value violates the Flag shape contract (ADR 0021 §Constraints).

    ``field`` names the offending input:
    - ``"key"``           — outside ``^[a-z0-9._-]{1,128}$``
    - ``"scope"``         — not a valid ``org_<32hex>``
    - ``"basis_points"``  — outside [0, 10000]
    - ``"relation"``      — outside ``^[a-z_]{2,32}$``
    - ``"rules"``         — rule list malformed (unknown kind, missing fields)
    """

    def __init__(self, field: str, message: str = "") -> None:
        self.field = field
        super().__init__(message or f"Invalid value for field: {field!r}")


class NotFoundError(FlagError):
    """Raised when a flag does not exist or is outside the caller's scope."""


class PreconditionError(FlagError):
    """Raised when a state or constraint precondition is violated.

    Used for duplicate ``(scope, key)`` on create (ADR 0019 taxonomy).
    """
