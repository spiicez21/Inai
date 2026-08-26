"""Brazil → India. DATA.md §2.1.

Three separate remappings, and it matters that they are separate:

  1. **Rails.** Brazilian payment types have no Indian equivalents; they are analogues.
  2. **Method mix.** Brazil is credit-card dominant (73.9% of payments). India is UPI
     dominant. Preserving Brazil's mix would make every fee number wrong, because UPI
     carries 0% MDR and cards carry 1.5–3.5%.
  3. **Amounts.** A rank-preserving rescale onto an INR lognormal. Rank-preserving means a
     customer who paid more in Brazil still pays more in India, so the *shape* of the
     amount distribution survives while the absolute values become Indian.

Two honest caveats, stated here because the deck should state them too:

  * `payment_installments` is genuinely Brazil-specific. *Parcelamento* — splitting a
    purchase across months on one card — is a cultural norm there with no clean Indian
    equivalent; Indian EMI is issuer-side and behaves differently. We use it only as a
    source of realistic **split-payment cardinality**, not as an economic model.
  * `boleto` has no Indian analogue at all. Mapping it to netbanking is a convenience,
    not an equivalence.
"""

from __future__ import annotations

import numpy as np

from inai.money import Paise
from inai.schema import Method

#: Structural analogue only — see the caveats above.
RAIL_MAP: dict[str, tuple[Method, ...]] = {
    # A Brazilian credit card is sometimes a recurring mandate here, usually a one-off card.
    "credit_card": (Method.CARD, Method.EMANDATE),
    "debit_card": (Method.CARD,),
    "boleto": (Method.NETBANKING,),  # bank-transfer analogue
    "voucher": (Method.WALLET,),
}

#: Weights within each mapped tuple.
RAIL_WEIGHTS: dict[str, tuple[float, ...]] = {
    "credit_card": (0.82, 0.18),
    "debit_card": (1.0,),
    "boleto": (1.0,),
    "voucher": (1.0,),
}

#: Target Indian method mix. UPI-dominant, unlike the spine's 73.9% credit card.
#: Applied as a re-draw over a share of payments so the spine's per-order cardinality
#: survives while the rail mix becomes Indian. Document the re-weighting in the deck.
INDIA_METHOD_MIX: dict[Method, float] = {
    Method.UPI: 0.62,
    Method.CARD: 0.18,
    Method.NETBANKING: 0.11,
    Method.WALLET: 0.05,
    Method.EMANDATE: 0.04,
}

#: Share of payments whose rail is drawn from the Indian mix rather than mapped from the
#: spine. At 1.0 the spine's rail information is discarded entirely; at 0.0 the output is
#: Brazilian. 0.85 keeps a trace of the spine's card/non-card structure.
REWEIGHT_SHARE = 0.85


def localize_method(spine_type: str, rng: np.random.Generator) -> Method:
    """One Brazilian payment_type -> one Indian rail."""
    if rng.random() < REWEIGHT_SHARE:
        methods = list(INDIA_METHOD_MIX)
        weights = np.array([INDIA_METHOD_MIX[m] for m in methods])
        return methods[int(rng.choice(len(methods), p=weights / weights.sum()))]

    options = RAIL_MAP.get(spine_type, (Method.UPI,))
    weights = np.array(RAIL_WEIGHTS.get(spine_type, (1.0,)))
    return options[int(rng.choice(len(options), p=weights / weights.sum()))]


class AmountScaler:
    """Rank-preserving rescale of BRL payment values onto an INR lognormal.

    Fitted once over the whole batch so that ranks are global rather than per-record.
    The merchant profile (median ticket and spread) comes from the run config, so
    `demo.yaml` and `stress.yaml` can model different merchants without touching code.
    """

    def __init__(
        self,
        values: list[float],
        median_inr: float = 2400.0,
        sigma: float = 1.05,
    ) -> None:
        self._sorted = np.sort(np.asarray(values, dtype=float))
        self._n = len(self._sorted)
        self._mu = float(np.log(median_inr))
        self._sigma = float(sigma)

    def to_paise(self, brl_value: float) -> Paise:
        """Map one BRL value to integer paise, preserving its rank in the batch."""
        if self._n == 0:
            return Paise(0)
        # Percentile of this value within the batch...
        rank = float(int(np.searchsorted(self._sorted, brl_value, side="left")))
        q = min(max((rank + 0.5) / self._n, 1e-6), 1 - 1e-6)
        # ...then the same percentile of the target INR lognormal.
        z = float(np.sqrt(2.0) * _erfinv(2.0 * q - 1.0))
        rupees = float(np.exp(self._mu + self._sigma * z))
        return Paise(round(rupees * 100))


def _erfinv(x: float) -> float:
    """Inverse error function.

    Hand-rolled rather than pulled from scipy: scipy is a heavy dependency to add for one
    scalar function, and this is on the deterministic path where a version bump changing a
    numerical detail would silently change every generated amount.

    Giles' rational approximation, ~1e-9 absolute error over the range we use.
    """
    w = -np.log(max((1.0 - x) * (1.0 + x), 1e-300))
    if w < 5.0:
        w -= 2.5
        p = 2.81022636e-08
        for c in (
            3.43273939e-07,
            -3.5233877e-06,
            -4.39150654e-06,
            0.00021858087,
            -0.00125372503,
            -0.00417768164,
            0.246640727,
            1.50140941,
        ):
            p = p * w + c
    else:
        w = np.sqrt(w) - 3.0
        p = -0.000200214257
        for c in (
            0.000100950558,
            0.00134934322,
            -0.00367342844,
            0.00573950773,
            -0.0076224613,
            0.00943887047,
            1.00167406,
            2.83297682,
        ):
            p = p * w + c
    return float(p * x)
