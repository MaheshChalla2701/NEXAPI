"""Small, dependency-free statistics helpers.

Normal-approximation methods are used throughout; they are appropriate for
the sample sizes involved (hundreds or more per group). Each function returns
plain floats so results can be written straight to SQLite.
"""

from __future__ import annotations

import math
from statistics import fmean, variance

Z95 = 1.959963984540054


def two_sided_p_from_z(z: float) -> float:
    """Two-sided p-value for a standard-normal test statistic."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def diff_in_proportions(x_t: int, n_t: int, x_c: int, n_c: int) -> dict[str, float]:
    """Treatment-minus-control difference in proportions.

    CI: unpooled Wald interval. Test: pooled two-proportion z-test.
    """
    if min(n_t, n_c) <= 0:
        raise ValueError("Both groups need at least one unit")
    p_t, p_c = x_t / n_t, x_c / n_c
    effect = p_t - p_c
    se = math.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    pooled = (x_t + x_c) / (n_t + n_c)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / n_t + 1 / n_c))
    z = effect / se0 if se0 > 0 else 0.0
    return {
        "treatment": p_t,
        "control": p_c,
        "effect": effect,
        "ci_low": effect - Z95 * se,
        "ci_high": effect + Z95 * se,
        "p_value": two_sided_p_from_z(z),
    }


def diff_in_means(treatment: list[float], control: list[float]) -> dict[str, float]:
    """Treatment-minus-control difference in means (Welch SE, normal approx)."""
    if min(len(treatment), len(control)) < 2:
        raise ValueError("Both groups need at least two observations")
    m_t, m_c = fmean(treatment), fmean(control)
    se = math.sqrt(variance(treatment) / len(treatment) + variance(control) / len(control))
    effect = m_t - m_c
    z = effect / se if se > 0 else 0.0
    return {
        "treatment": m_t,
        "control": m_c,
        "effect": effect,
        "ci_low": effect - Z95 * se,
        "ci_high": effect + Z95 * se,
        "p_value": two_sided_p_from_z(z),
    }


def srm_two_arm(n_a: int, n_b: int, expected_share_a: float = 0.5) -> dict[str, float]:
    """Sample-ratio-mismatch chi-square test for a two-arm split (1 df)."""
    total = n_a + n_b
    if total <= 0:
        raise ValueError("No units assigned")
    exp_a = total * expected_share_a
    exp_b = total - exp_a
    chi2 = (n_a - exp_a) ** 2 / exp_a + (n_b - exp_b) ** 2 / exp_b
    # For 1 degree of freedom, P(X > chi2) = erfc(sqrt(chi2 / 2)).
    return {"chi2": chi2, "p_value": math.erfc(math.sqrt(chi2 / 2.0)), "share_a": n_a / total}
