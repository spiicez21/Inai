"""Bank narration grammar. DATA.md §4.1.

**This is the largest synthetic-data risk in the build, and it is named as such.**

There is no public corpus of Indian bank statement narrations, so this is a grammar derived
from published NEFT/UPI/IMPS/RTGS transfer formats rather than a sample of real strings.
Read T2 fuzzy-match results as directional.

The UTR format follows the documented 16-character convention
(`<4-char bank code><YYDDD Julian date><7-digit sequence>`). Once a real Razorpay test-mode
settlement report lands in `data/reference/`, `utr_grammar_from_sample()` should replace the
synthetic generator so the format is observed rather than assumed — that is step 2 of the
DATA.md §9 day-one checklist and it is not done yet.
"""

from __future__ import annotations

from datetime import date

import numpy as np

#: Sponsor-bank prefixes seen on Indian NEFT UTRs. Razorpay settles through a small set.
BANK_PREFIXES = ("ICIC", "HDFC", "UTIB", "KKBK", "YESB", "SBIN")

#: Razorpay settles as "RAZORPAY SOFTWARE PVT LTD", but banks truncate and abbreviate it
#: differently. These are the variants a reconciler actually has to cope with.
REMITTER_FORMS = (
    "RAZORPAY SOFTWARE PVT LTD",
    "RAZORPAY SOFTWARE PRIVATE LIMITED",
    "RAZORPAY SOFTWARE P LTD",
    "RAZORPAY SOFT PVT LTD",
    "RAZORPAYSOFTWAREPVTLTD",
    "RAZORPAY",
)

_UPI_HANDLES = ("okhdfcbank", "okicici", "oksbi", "okaxis", "ybl", "paytm", "apl")


def make_utr(rng: np.random.Generator, value_date: date) -> str:
    """A 16-character NEFT-style UTR: bank code + Julian date + sequence."""
    bank = BANK_PREFIXES[int(rng.integers(0, len(BANK_PREFIXES)))]
    julian = f"{value_date.year % 100:02d}{value_date.timetuple().tm_yday:03d}"
    seq = int(rng.integers(0, 10_000_000))
    return f"{bank}{julian}{seq:07d}"


def make_rrn(rng: np.random.Generator) -> str:
    """12-digit Retrieval Reference Number, used by IMPS and UPI."""
    return f"{int(rng.integers(0, 10**12)):012d}"


def make_vpa(rng: np.random.Generator, customer_id: str) -> str:
    handle = _UPI_HANDLES[int(rng.integers(0, len(_UPI_HANDLES)))]
    return f"{customer_id[:10].lower()}@{handle}"


def neft(utr: str, remitter: str, ref: str = "") -> str:
    return f"NEFT-{utr}-{remitter}" + (f"-{ref}" if ref else "")


def rtgs(utr: str, remitter: str) -> str:
    return f"RTGS-{utr}-{remitter}"


def imps(rrn: str, remitter: str, remark: str = "") -> str:
    return f"IMPS/{rrn}/{remitter}" + (f"/{remark}" if remark else "")


def upi(rrn: str, vpa: str, note: str = "") -> str:
    return f"UPI/{rrn}/{vpa}" + (f"/{note}" if note else "")


def settlement_narration(
    rng: np.random.Generator,
    utr: str,
    value_date: date,
    amount_paise: int,
) -> str:
    """The narration on a Razorpay settlement credit.

    A settlement lands as a single lumped NEFT (or RTGS above ₹2 lakh) credit covering
    hundreds of orders, net of MDR, GST on MDR and refund adjustments. The narration
    carries the UTR and the remitter, and nothing that identifies any individual order —
    which is precisely why unpacking it order by order is the hard problem.
    """
    remitter = REMITTER_FORMS[int(rng.integers(0, len(REMITTER_FORMS)))]
    # RTGS is the rail above ₹2,00,000 in practice.
    if amount_paise >= 200_000_00:
        return rtgs(utr, remitter)
    ref = f"SETTL{value_date.strftime('%d%m%y')}" if rng.random() < 0.45 else ""
    return neft(utr, remitter, ref)


def utr_grammar_from_sample() -> None:
    """Placeholder for DATA.md §9 step 2.

    Derive the real UTR grammar from `data/reference/razorpay_settlement_sample.json`
    instead of the synthetic generator above. Not implemented — the sample requires a
    Razorpay test-mode account and has not been pulled.
    """
    raise NotImplementedError(
        "Pull data/reference/razorpay_settlement_sample.json first — DATA.md §1.2."
    )
