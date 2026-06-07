# Copyright 2026 NDC Digital, LLC
# SPDX-License-Identifier: Apache-2.0

"""Deterministic percentage-rollout bucketing (ADR 0021 §Deterministic bucketing).

Cross-SDK identity is normative: every SDK MUST produce identical buckets for
identical (key, subject_id) pairs.

Algorithm (pinned by spec):
  h  = SHA-256( utf8(key) || 0x00 || utf8(subject_id) )
  n  = uint32_big_endian(h[0:4])
  return n % 10000

Inputs MUST be passed exactly as they appear on the wire:
  key        — the flag's ``key`` string, UTF-8, no normalization
  subject_id — the full wire-format id: ``{type}_{32hex}`` (e.g. ``usr_abc...``)
"""

from __future__ import annotations

import hashlib
import struct


def bucket(key: str, subject_id: str) -> int:
    """Return the rollout bucket for (key, subject_id) in [0, 9999].

    A ``percentage`` rule with ``basis_points = B`` matches iff
    ``bucket(key, subject_id) < B``.
    """
    digest = hashlib.sha256(
        key.encode() + b"\x00" + subject_id.encode()
    ).digest()
    n = struct.unpack(">I", digest[:4])[0]
    return n % 10000
