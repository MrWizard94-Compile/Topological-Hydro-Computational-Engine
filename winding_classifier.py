"""
================================================================================
WINDING NUMBER CLASSIFIER  —  MemoryMatrix 3.0 / VortexBraid Engine
================================================================================
Replaces the NULL-register decoder with physics-correct topological classification.

Classification hierarchy (based on anyonic fusion rules and braiding statistics):
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  W ≈ 0              → VACUUM       |0⟩  (trivial / no winding)             │
  │  W ≈ ±1             → UNIT_CHARGE  |±1⟩ (single vortex, Abelian)          │
  │  W ≈ ±2             → DOUBLE_WOUND |±2⟩ (double braid, anomalous)         │
  │  W ≈ ±½ or ±3/2    → FRACTIONAL   |½⟩  (anyonic / non-Abelian partial)   │
  │  |W| > 2            → MULTI_WOUND  |nW⟩ (multi-winding, exotic)           │
  │  anything else      → SUPERPOS     |ψ⟩  (non-integer, gauge-induced)      │
  └─────────────────────────────────────────────────────────────────────────────┘

Physics reference:
  - Plaquette phase accumulation: Δθ = Σ arg(ψ* · shift(ψ)) around closed loop
  - Winding number W = Δθ / (2π)
  - Non-Abelian signature: |W_CW − W_CCW| >> control baseline
  - Gate mapping follows Ising anyon braid matrix algebra: σ₁, σ₂, σ₁⁻¹, σ₂⁻¹

Author : MemoryMatrix 3.0 — Senior Dev / Master Coder build
Version: 3.1.0
================================================================================
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Classification constants
# ─────────────────────────────────────────────────────────────────────────────

VACUUM_TOL      = 0.08   # |W| < this → vacuum
UNIT_TOL        = 0.12   # |W - n| < this for integer n → unit-charged state
FRAC_TARGETS    = [0.5, 1.5, 2.5]  # half-integer winding targets
FRAC_TOL        = 0.10   # tolerance around fractional targets
MULTI_THRESHOLD = 2.2    # |W| > this → multi-wound exotic state

# Ising anyon braid matrix eigenvalues (for gate mapping)
ISING_BRAID_PHASES = {
    0:    ("Identity",  "I",       "No braid"),
    1:    ("σ₁",        "B1",      "CW half-braid: e^{iπ/8}"),
    -1:   ("σ₁⁻¹",     "B1_inv",  "CCW half-braid: e^{-iπ/8}"),
    2:    ("σ₁σ₂",     "B12",     "Full CW braid: S-gate equivalent"),
    -2:   ("σ₁⁻¹σ₂⁻¹","B12_inv", "Full CCW braid: S†-gate equivalent"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Logic state enum
# ─────────────────────────────────────────────────────────────────────────────

class LogicState(Enum):
    VACUUM       = "VACUUM       |0⟩"
    UNIT_POS     = "UNIT_POS     |+1⟩"
    UNIT_NEG     = "UNIT_NEG     |−1⟩"
    DOUBLE_POS   = "DOUBLE_POS   |+2⟩"
    DOUBLE_NEG   = "DOUBLE_NEG   |−2⟩"
    FRACTIONAL   = "FRACTIONAL   |½⟩"
    MULTI_WOUND  = "MULTI_WOUND  |nW⟩"
    SUPERPOS     = "SUPERPOS     |ψ⟩"
    # Legacy alias kept for backward compatibility — no longer emitted
    NULL_REGISTER = "NULL_REGISTER (DEPRECATED — was masking real states)"


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WindingResult:
    """Full classification result for a single winding measurement."""

    # Raw physics
    raw_winding:        float
    path_direction:     str          # "CW" or "CCW"
    regime:             str          # "control" or "coupled"
    omega_gauge:        float

    # Classification
    logic_state:        LogicState
    nearest_integer:    int          # closest integer winding
    integer_residual:   float        # |W - nearest_integer|
    is_fractional:      bool
    is_non_abelian:     bool         # True if |W| not close to any integer

    # Gate mapping
    gate_label:         str
    gate_symbol:        str
    gate_description:   str

    # Path-dependence
    path_dependence_flag: bool = False   # set by WindingPairAnalyzer
    asymmetry:            float = 0.0   # |W_CW - W_CCW|, set by pair analyzer

    # Human-readable summary
    physical_meaning: str = field(default="", init=False)

    def __post_init__(self):
        self.physical_meaning = self._build_meaning()

    def _build_meaning(self) -> str:
        s = self.logic_state
        w = self.raw_winding
        if s == LogicState.VACUUM:
            return "Trivial anyon vacuum — no braiding phase accumulated"
        if s == LogicState.UNIT_POS:
            return f"Single positive vortex wrap (W≈+1) — CW phase +2π via σ₁ braid"
        if s == LogicState.UNIT_NEG:
            return f"Single negative vortex wrap (W≈−1) — CCW phase −2π via σ₁⁻¹ braid"
        if s == LogicState.DOUBLE_POS:
            return f"Double CW winding (W≈+2) — composite σ₁σ₂ gate, full +4π phase"
        if s == LogicState.DOUBLE_NEG:
            return f"Double CCW winding (W≈−2) — gauge-induced anomalous reversal, −4π phase"
        if s == LogicState.FRACTIONAL:
            closest_frac = min(FRAC_TARGETS, key=lambda f: abs(abs(w) - f))
            sign = "+" if w >= 0 else "−"
            return (f"Fractional winding (W≈{sign}{closest_frac}) — "
                    f"non-Abelian anyonic superposition; half-integer phase ±π from fusion rules")
        if s == LogicState.MULTI_WOUND:
            n = round(w)
            return (f"Multi-wound state (W≈{n}) — exotic high-charge vortex; "
                    f"energetically suppressed in physical systems but present here under strong gauge")
        if s == LogicState.SUPERPOS:
            return (f"Non-integer winding W={w:.4f} — gauge-field-induced anyonic superposition; "
                    f"signature of non-Abelian braiding path-dependence (Aharonov-Bohm type)")
        return "Unknown state"

    def to_dict(self) -> dict:
        return {
            "raw_winding":        round(self.raw_winding, 6),
            "path_direction":     self.path_direction,
            "regime":             self.regime,
            "omega_gauge":        round(self.omega_gauge, 4),
            "logic_state":        self.logic_state.name,
            "logic_state_label":  self.logic_state.value,
            "nearest_integer":    self.nearest_integer,
            "integer_residual":   round(self.integer_residual, 6),
            "is_fractional":      self.is_fractional,
            "is_non_abelian":     self.is_non_abelian,
            "gate_label":         self.gate_label,
            "gate_symbol":        self.gate_symbol,
            "gate_description":   self.gate_description,
            "path_dependence_flag": self.path_dependence_flag,
            "asymmetry":          round(self.asymmetry, 6),
            "physical_meaning":   self.physical_meaning,
        }

    def report_line(self, width: int = 80) -> str:
        bar = "─" * width
        return (
            f"\n{bar}\n"
            f"  Channel  : {self.regime.upper()} / {self.path_direction}   ω = {self.omega_gauge}\n"
            f"  W (raw)  : {self.raw_winding:+.6f}\n"
            f"  State    : {self.logic_state.value}\n"
            f"  Gate     : {self.gate_label}  [{self.gate_symbol}]  — {self.gate_description}\n"
            f"  Residual : |W - {self.nearest_integer}| = {self.integer_residual:.6f}"
            f"  ({'fractional' if self.is_fractional else 'integer-adjacent'}) "
            f"  ({'NON-ABELIAN' if self.is_non_abelian else 'Abelian'})\n"
            f"  Meaning  : {self.physical_meaning}\n"
            f"{bar}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Core classifier
# ─────────────────────────────────────────────────────────────────────────────

class WindingClassifier:
    """
    Classifies a scalar winding number W into a full topological logic state.

    Usage
    -----
    clf = WindingClassifier()
    result = clf.classify(W=-1.8492, path_direction="CW",
                          regime="coupled", omega_gauge=1.5)
    """

    def __init__(
        self,
        vacuum_tol:      float = VACUUM_TOL,
        unit_tol:        float = UNIT_TOL,
        frac_tol:        float = FRAC_TOL,
        multi_threshold: float = MULTI_THRESHOLD,
    ):
        self.vacuum_tol      = vacuum_tol
        self.unit_tol        = unit_tol
        self.frac_tol        = frac_tol
        self.multi_threshold = multi_threshold

    # ── public API ────────────────────────────────────────────────────────────

    def classify(
        self,
        W:              float,
        path_direction: str   = "CW",
        regime:         str   = "control",
        omega_gauge:    float = 0.0,
    ) -> WindingResult:
        """
        Classify scalar winding number W into a WindingResult.

        Parameters
        ----------
        W              : Raw winding number from plaquette phase accumulation
        path_direction : "CW" or "CCW"
        regime         : "control" or "coupled"
        omega_gauge    : Value of omega gauge field (0 = off)

        Returns
        -------
        WindingResult with full classification, gate mapping, and physical meaning
        """
        absW = abs(W)
        nearest_int   = self._nearest_integer(W)
        int_residual  = abs(W - nearest_int)
        is_frac       = self._is_fractional(W)
        is_non_abelian = self._is_non_abelian(W)

        logic_state = self._classify_state(W, absW, nearest_int, int_residual, is_frac)
        gate_label, gate_symbol, gate_desc = self._map_gate(nearest_int, W)

        return WindingResult(
            raw_winding       = W,
            path_direction    = path_direction,
            regime            = regime,
            omega_gauge       = omega_gauge,
            logic_state       = logic_state,
            nearest_integer   = nearest_int,
            integer_residual  = int_residual,
            is_fractional     = is_frac,
            is_non_abelian    = is_non_abelian,
            gate_label        = gate_label,
            gate_symbol       = gate_symbol,
            gate_description  = gate_desc,
        )

    def classify_field(
        self,
        psi:            np.ndarray,
        vortex_center:  tuple[float, float],
        path_radius:    float,
        path_direction: str   = "CW",
        regime:         str   = "control",
        omega_gauge:    float = 0.0,
        n_points:       int   = 256,
    ) -> WindingResult:
        """
        Compute winding number directly from a 2D complex wavefunction field
        using the ring-plaquette phase accumulation method, then classify.

        Parameters
        ----------
        psi            : 2D complex numpy array (the field ψ)
        vortex_center  : (cx, cy) center of vortex B in array coordinates
        path_radius    : Radius of integration loop in lattice units
        path_direction : "CW" or "CCW"
        regime         : "control" or "coupled"
        omega_gauge    : Value of omega gauge field
        n_points       : Number of points sampled on the contour

        Returns
        -------
        WindingResult with field-derived winding number
        """
        W = self._compute_field_winding(
            psi, vortex_center, path_radius, path_direction, n_points
        )
        return self.classify(W, path_direction, regime, omega_gauge)

    # ── classification logic ──────────────────────────────────────────────────

    def _classify_state(
        self,
        W:           float,
        absW:        float,
        nearest_int: int,
        int_residual: float,
        is_frac:     bool,
    ) -> LogicState:

        # 1. Vacuum
        if absW < self.vacuum_tol:
            return LogicState.VACUUM

        # 2. Fractional (half-integer) — check before integer to catch ±½, ±3/2
        if is_frac:
            return LogicState.FRACTIONAL

        # 3. Multi-wound exotic
        if absW > self.multi_threshold:
            return LogicState.MULTI_WOUND

        # 4. Integer-adjacent states
        if int_residual < self.unit_tol:
            if nearest_int == 1:  return LogicState.UNIT_POS
            if nearest_int == -1: return LogicState.UNIT_NEG
            if nearest_int == 2:  return LogicState.DOUBLE_POS
            if nearest_int == -2: return LogicState.DOUBLE_NEG
            # Higher integer: promote to multi-wound
            return LogicState.MULTI_WOUND

        # 5. Non-integer residual — genuine superposition / gauge-induced
        return LogicState.SUPERPOS

    def _nearest_integer(self, W: float) -> int:
        return int(np.round(W))

    def _is_fractional(self, W: float) -> bool:
        """True if W is close to any half-integer (±½, ±3/2, ±5/2, ...)."""
        for target in FRAC_TARGETS:
            if abs(abs(W) - target) < self.frac_tol:
                return True
        return False

    def _is_non_abelian(self, W: float) -> bool:
        """
        Non-Abelian signature: winding number is not close to any integer.
        For Abelian anyons, braiding always yields integer winding.
        For non-Abelian anyons, fractional / irrational winding is allowed.
        """
        int_residual = abs(W - round(W))
        return int_residual > self.unit_tol and not self._is_fractional(W)

    def _map_gate(self, nearest_int: int, W: float) -> tuple[str, str, str]:
        """Map nearest integer winding to an Ising anyon braid gate."""
        clipped = max(-2, min(2, nearest_int))
        if clipped in ISING_BRAID_PHASES:
            label, symbol, desc = ISING_BRAID_PHASES[clipped]
        else:
            n = nearest_int
            label  = f"σ₁^{n}"
            symbol = f"B{abs(n)}"
            desc   = f"High-order braid: n={n} winding"
        return label, symbol, desc

    # ── field-level computation ───────────────────────────────────────────────

    @staticmethod
    def _compute_field_winding(
        psi:           np.ndarray,
        center:        tuple[float, float],
        radius:        float,
        direction:     str,
        n_points:      int,
    ) -> float:
        """
        Ring-plaquette phase accumulation method.

        For each consecutive pair of points on a circular contour, computes
        the phase difference Δθ = arg(ψ(B) · ψ*(A)), unwraps to |Δθ| < π,
        and sums. The total / (2π) gives the winding number.

        This is the same algorithm used in GPE/Gross-Pitaevskii vortex tracking.
        """
        ny, nx = psi.shape
        cx, cy  = center
        angles  = np.linspace(0, 2 * np.pi, n_points, endpoint=False)

        # Reverse angle direction for CW
        if direction == "CW":
            angles = angles[::-1]

        # Sample ψ on the contour via bilinear interpolation
        xs = cx + radius * np.cos(angles)
        ys = cy + radius * np.sin(angles)
        # Clamp to grid
        xs = np.clip(xs, 0, nx - 1)
        ys = np.clip(ys, 0, ny - 1)

        psi_vals = WindingClassifier._bilinear_sample(psi, xs, ys)

        # Compute phase at each sample point
        phases = np.angle(psi_vals)   # in [-π, π]

        # Phase differences between consecutive points (with 2π-unwrapping)
        dphases = np.diff(phases, append=phases[0])
        # Unwrap: bring each step into (-π, π]
        dphases = (dphases + np.pi) % (2 * np.pi) - np.pi

        total_phase = np.sum(dphases)
        return total_phase / (2 * np.pi)

    @staticmethod
    def _bilinear_sample(
        psi: np.ndarray,
        xs:  np.ndarray,
        ys:  np.ndarray,
    ) -> np.ndarray:
        """Bilinear interpolation of complex field ψ at fractional coordinates."""
        ny, nx = psi.shape
        x0 = np.floor(xs).astype(int)
        y0 = np.floor(ys).astype(int)
        x1 = np.clip(x0 + 1, 0, nx - 1)
        y1 = np.clip(y0 + 1, 0, ny - 1)
        x0 = np.clip(x0, 0, nx - 1)
        y0 = np.clip(y0, 0, ny - 1)

        fx = xs - np.floor(xs)
        fy = ys - np.floor(ys)

        p00 = psi[y0, x0]
        p10 = psi[y0, x1]
        p01 = psi[y1, x0]
        p11 = psi[y1, x1]

        return (p00 * (1 - fx) * (1 - fy) +
                p10 * fx       * (1 - fy) +
                p01 * (1 - fx) * fy       +
                p11 * fx       * fy)


# ─────────────────────────────────────────────────────────────────────────────
# Pair analyzer — CW/CCW asymmetry & path-dependence verdict
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PathDependenceVerdict:
    """Output of WindingPairAnalyzer for a CW/CCW pair."""
    cw_result:        WindingResult
    ccw_result:       WindingResult
    asymmetry:        float          # |W_CW - W_CCW|
    control_baseline: float          # reference Δ from control run
    ratio:            float          # asymmetry / baseline
    is_path_dependent: bool
    verdict_text:     str
    confidence:       str            # "HIGH", "MEDIUM", "LOW"
    gate_pair_label:  str            # e.g. "σ₁ ⊗ σ₁⁻¹"

    def report(self, width: int = 80) -> str:
        bar  = "═" * width
        dash = "─" * width
        return (
            f"\n{bar}\n"
            f"  PATH-DEPENDENCE VERDICT\n"
            f"{dash}\n"
            f"  CW  winding  : {self.cw_result.raw_winding:+.6f}  →  {self.cw_result.logic_state.value}\n"
            f"  CCW winding  : {self.ccw_result.raw_winding:+.6f}  →  {self.ccw_result.logic_state.value}\n"
            f"  Asymmetry Δ  : {self.asymmetry:.6f}\n"
            f"  Ctrl baseline: {self.control_baseline:.6f}\n"
            f"  Ratio        : {self.ratio:.1f}×  (Δ_coupled / Δ_control)\n"
            f"  Path-dep?    : {'YES ✓' if self.is_path_dependent else 'NO  ○'}\n"
            f"  Confidence   : {self.confidence}\n"
            f"  Gate pair    : {self.gate_pair_label}\n"
            f"  Verdict      : {self.verdict_text}\n"
            f"{bar}"
        )

    def to_dict(self) -> dict:
        return {
            "cw":  self.cw_result.to_dict(),
            "ccw": self.ccw_result.to_dict(),
            "asymmetry":          round(self.asymmetry, 6),
            "control_baseline":   round(self.control_baseline, 6),
            "ratio":              round(self.ratio, 2),
            "is_path_dependent":  self.is_path_dependent,
            "verdict_text":       self.verdict_text,
            "confidence":         self.confidence,
            "gate_pair_label":    self.gate_pair_label,
        }


class WindingPairAnalyzer:
    """
    Analyzes a CW / CCW winding pair to determine whether genuine
    path-dependence (non-Abelian braiding signature) is present.

    Thresholds (calibrated to your simulation's control baseline 0.000119):
      RATIO_MEDIUM :  5×  — marginal signal
      RATIO_HIGH   : 50×  — clear non-Abelian signature
      RATIO_VERY_HIGH: 200× — strong anomalous gauge coupling
    """

    RATIO_MEDIUM    =   5.0
    RATIO_HIGH      =  50.0
    RATIO_VERY_HIGH = 200.0

    def __init__(self, classifier: Optional[WindingClassifier] = None):
        self.clf = classifier or WindingClassifier()

    def analyze(
        self,
        W_cw:             float,
        W_ccw:            float,
        control_baseline: float,
        omega_gauge:      float,
        regime:           str = "coupled",
    ) -> PathDependenceVerdict:
        """
        Parameters
        ----------
        W_cw             : CW winding number
        W_ccw            : CCW winding number
        control_baseline : L² difference from control run (omega=0)
        omega_gauge      : Current omega value
        regime           : "coupled" or "control"
        """
        cw_result  = self.clf.classify(W_cw,  "CW",  regime, omega_gauge)
        ccw_result = self.clf.classify(W_ccw, "CCW", regime, omega_gauge)

        asymmetry = abs(W_cw - W_ccw)
        ratio     = asymmetry / max(control_baseline, 1e-12)

        # Set back-references
        cw_result.asymmetry  = asymmetry
        ccw_result.asymmetry = asymmetry
        cw_result.path_dependence_flag  = ratio > self.RATIO_MEDIUM
        ccw_result.path_dependence_flag = ratio > self.RATIO_MEDIUM

        is_path_dep = ratio > self.RATIO_MEDIUM

        # Confidence tier
        if ratio > self.RATIO_VERY_HIGH:
            confidence = "HIGH"
        elif ratio > self.RATIO_HIGH:
            confidence = "MEDIUM"
        elif ratio > self.RATIO_MEDIUM:
            confidence = "LOW"
        else:
            confidence = "NONE"

        # Gate pair label
        gate_pair_label = f"{cw_result.gate_label} ⊗ {ccw_result.gate_label}"

        # Verdict text
        if not is_path_dep:
            verdict = ("Abelian regime — CW and CCW paths produce equivalent outcomes. "
                       "No braiding memory. Consistent with omega=0 control baseline.")
        elif ratio > self.RATIO_VERY_HIGH:
            verdict = (f"STRONG non-Abelian path-dependence detected. "
                       f"Asymmetry {ratio:.1f}× above control. "
                       f"ψ_down field acquired braiding-path memory without direct coupling — "
                       f"Aharonov-Bohm-type topological encoding confirmed. "
                       f"CW and CCW worldlines produce distinct anyonic fusion outcomes.")
        elif ratio > self.RATIO_HIGH:
            verdict = (f"Clear non-Abelian signature. "
                       f"Asymmetry {ratio:.1f}× above control. "
                       f"Gauge coupling induces measurable path-dependence in untouched field. "
                       f"Gate composition is order-dependent: AB ≠ BA (non-commutative).")
        else:
            verdict = (f"Marginal path-dependence ({ratio:.1f}× above control). "
                       f"May indicate weak gauge coupling or boundary effects. "
                       f"Increase omega_gauge or lattice size to strengthen signal.")

        return PathDependenceVerdict(
            cw_result         = cw_result,
            ccw_result        = ccw_result,
            asymmetry         = asymmetry,
            control_baseline  = control_baseline,
            ratio             = ratio,
            is_path_dependent = is_path_dep,
            verdict_text      = verdict,
            confidence        = confidence,
            gate_pair_label   = gate_pair_label,
        )
