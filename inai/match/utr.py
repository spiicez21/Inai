"""UTR extraction from bank narrations. INAI_SPEC.md §5.3, §8.7.

Regex first. The LLM is allowed to parse a narration **only when the regex fails**, and it
is never allowed to decide whether two records match — it returns a candidate reference and
the deterministic cascade does the rest.

The grammar this has to survive is in `DATA.md` §4.1, and the damage in §5.1:

    C07  truncation at a bank field limit, separators collapsed, vowels dropped
    C14  lower-cased, randomly-cased, Hindi suffix appended

So extraction cannot assume the `NEFT-<UTR>-<REMITTER>` shape survived. It looks for the
*token*, anywhere, in any case.
"""

from __future__ import annotations

import re

#: A NEFT/RTGS UTR: 4 alpha (sponsor bank) + 12 digits. 16 characters.
UTR_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{4}\d{12})(?![A-Za-z0-9])")

#: A 12-digit RRN, used by IMPS and UPI. Matched only after a rail marker, because a bare
#: 12-digit run is far too common to treat as a reference on its own.
RRN_RE = re.compile(r"(?:IMPS|UPI)[/\-\s]+(\d{12})(?!\d)", re.IGNORECASE)

#: Merchant order receipts as this system issues them.
RECEIPT_RE = re.compile(r"(?<![A-Za-z0-9])(inv_\d{7})(?![A-Za-z0-9])", re.IGNORECASE)


def extract_utr(narration: str) -> str | None:
    """The UTR from a narration, or None.

    Returns None rather than a guess. A wrong UTR is worse than no UTR: it produces a
    confident match against the wrong settlement, which silently closes an invoice that was
    never paid. INAI_SPEC.md §6.2 — an honest exception beats a confident wrong allocation.
    """
    if not narration:
        return None
    m = UTR_RE.search(narration)
    if m:
        return m.group(1).upper()
    m = RRN_RE.search(narration)
    if m:
        return m.group(1)
    return None


def extract_receipt(narration: str) -> str | None:
    """A merchant order receipt embedded in the narration, if one survived."""
    if not narration:
        return None
    m = RECEIPT_RE.search(narration)
    return m.group(1).lower() if m else None


def needs_llm(narration: str) -> bool:
    """True when the regex found nothing and §8.7 permits an LLM attempt.

    Phase 4 wires the actual call. Until then this only reports the size of the residue,
    which is itself worth knowing: if it is large, the narration grammar is the problem,
    not the matcher.
    """
    return extract_utr(narration) is None


def normalise(text: str) -> str:
    """Upper-case, collapse separators and whitespace.

    Used for fuzzy comparison in T2 (phase 3). Kept here so both tiers agree on what
    "the same string" means.
    """
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", text).split()).upper()
