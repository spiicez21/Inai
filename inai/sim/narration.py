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


# ---------------------------------------------------------------------------
# Direct payments — the customer transfers to the merchant's bank themselves
# ---------------------------------------------------------------------------
#: Fragments for plausible Indian B2B payer names. Combined deterministically from the
#: customer id, so one customer always presents the same remitter string — which is what
#: makes payer identity a usable matching signal, and what makes C08 (paying from a parent
#: company's account) an actual anomaly rather than noise.
_NAME_HEADS = (
    "SHREE",
    "SRI",
    "NEW",
    "ROYAL",
    "PRIME",
    "GLOBAL",
    "UNITED",
    "NATIONAL",
    "ORIENT",
    "PIONEER",
    "SUNRISE",
    "GREEN",
    "METRO",
    "APEX",
    "STAR",
)
_NAME_STEMS = (
    "KRISHNA",
    "BALAJI",
    "GANESH",
    "LAXMI",
    "VENKAT",
    "RAGHAV",
    "MURUGAN",
    "SARASWATI",
    "NARAYAN",
    "ARIHANT",
    "VIJAY",
    "AMBIKA",
    "KAVERI",
    "GODAVARI",
)
_NAME_TAILS = (
    "TRADERS",
    "ENTERPRISES",
    "INDUSTRIES",
    "AGENCIES",
    "TEXTILES",
    "STEELS",
    "PHARMA",
    "LOGISTICS",
    "ENGINEERING",
    "AUTOMOBILES",
    "PLASTICS",
    "PACKAGING",
)
_NAME_SUFFIX = ("PVT LTD", "LTD", "& CO", "LLP", "")


def payer_name(customer_id: str) -> str:
    """A stable remitter name for one customer.

    Derived from the id by hashing, NOT by an RNG draw: the same customer must present the
    same name in every run and on every invoice, or payer identity carries no information.
    """
    h = 0
    for ch in customer_id:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    parts = [
        _NAME_HEADS[h % len(_NAME_HEADS)],
        _NAME_STEMS[(h >> 5) % len(_NAME_STEMS)],
        _NAME_TAILS[(h >> 11) % len(_NAME_TAILS)],
        _NAME_SUFFIX[(h >> 17) % len(_NAME_SUFFIX)],
    ]
    return " ".join(p for p in parts if p)


def direct_narration(
    rng: np.random.Generator,
    *,
    customer_name: str,
    invoice_id: str,
    amount_paise: int,
    value_date: date,
    include_reference: bool,
) -> tuple[str, str]:
    """`(narration, utr_or_rrn)` for a customer's own bank transfer.

    Unlike a settlement credit, this one names the CUSTOMER as remitter and usually carries
    the invoice reference — which is why direct payments are easy when the reference
    survives and genuinely hard when it does not.
    """
    remitter = customer_name
    ref = invoice_id if include_reference else ""

    # RTGS above ₹2 lakh, UPI for small amounts, NEFT/IMPS in between.
    roll = rng.random()
    if amount_paise >= 200_000_00:
        utr = make_utr(rng, value_date)
        return rtgs(utr, remitter) + (f"-{ref}" if ref else ""), utr
    if amount_paise < 100_000_00 and roll < 0.35:
        rrn = make_rrn(rng)
        return upi(rrn, make_vpa(rng, remitter), ref), rrn
    if roll < 0.6:
        rrn = make_rrn(rng)
        return imps(rrn, remitter, ref), rrn
    utr = make_utr(rng, value_date)
    return neft(utr, remitter, ref), utr
