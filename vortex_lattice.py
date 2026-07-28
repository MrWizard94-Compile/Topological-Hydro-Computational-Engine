"""
================================================================================
VORTEX LATTICE ENGINE  —  MemoryMatrix 3.0 / VortexBraid Engine
================================================================================
Constructs and evolves the 2D lattice with:
  - Moving-vortex field (psi_down) on a triangular / square lattice
  - Two-vortex braiding geometry (vortex A around vortex B)
  - Digital omega gauge coupling applied to psi_down via Peierls substitution
  - CW / CCW path execution with proper phase winding
  - Integration with WindingClassifier for decoded logic states

Physics
-------
Field model:  ψ_down(r) = Π_k ( (r - r_k) / |r - r_k| )^{n_k}
              where n_k = ±1 is vortex charge and r_k is vortex position.

Gauge coupling (Peierls):
  ψ_gauge(r) = ψ_down(r) · exp(i · ω_gauge · A(r))
  where A(r) = (1/2) ε_{ij} (r - r_B)_i / |r - r_B|²  (Dirac-string-free gauge)

Winding number (ring-plaquette method):
  W = (1/2π) Σ_{plaquette edges} arg(ψ*(r_i) · ψ(r_{i+1}))

Author : MemoryMatrix 3.0 — Senior Dev / Master Coder build
Version: 3.1.0
================================================================================
"""

from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from winding_classifier import WindingClassifier, WindingResult, WindingPairAnalyzer, PathDependenceVerdict


# ─────────────────────────────────────────────────────────────────────────────
# Lattice configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LatticeConfig:
    """All parameters needed to fully specify a simulation run."""

    # Lattice geometry
    Lx:           int   = 80          # grid width  (nodes ≈ Lx × Ly)
    Ly:           int   = 63          # grid height  (5040 ≈ 5017 target)
    lattice_type: str   = "square"    # "square" or "triangular"

    # Vortex positions (in fraction of grid, 0..1)
    vortex_A_pos: tuple[float, float] = (0.25, 0.50)  # moving vortex (braider)
    vortex_B_pos: tuple[float, float] = (0.55, 0.50)  # stationary vortex B
    vortex_A_charge: int = +1
    vortex_B_charge: int = +1

    # Braiding path
    braid_radius:   float = 0.18      # radius of braiding loop (fraction of grid)
    n_braid_steps:  int   = 64        # discretization of braid path
    path_epsilon:   float = 1e-4      # regularization near vortex core

    # Gauge field
    omega_gauge:    float = 0.0       # digital coupling strength
    gauge_cutoff:   float = 2.0       # max |A(r)| saturation

    # Classifier
    path_radius_frac: float = 0.12    # contour radius for winding measurement (fraction of Ly)

    @property
    def n_nodes(self) -> int:
        return self.Lx * self.Ly

    @property
    def vortex_B_grid(self) -> tuple[float, float]:
        """Vortex B center in absolute grid coordinates."""
        return (self.vortex_B_pos[0] * self.Lx,
                self.vortex_B_pos[1] * self.Ly)

    @property
    def path_radius_px(self) -> float:
        return self.path_radius_frac * self.Ly


# ─────────────────────────────────────────────────────────────────────────────
# Lattice node store
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LatticeNodes:
    """Stores grid coordinates and the complex field arrays."""
    X:        np.ndarray   # shape (Ly, Lx), x-coordinate of each node
    Y:        np.ndarray   # shape (Ly, Lx), y-coordinate of each node
    psi_down: np.ndarray   # shape (Ly, Lx), complex field (unperturbed)
    n_nodes:  int

    def __repr__(self) -> str:
        return f"LatticeNodes({self.n_nodes} nodes, psi_down dtype={self.psi_down.dtype})"


# ─────────────────────────────────────────────────────────────────────────────
# Main lattice engine
# ─────────────────────────────────────────────────────────────────────────────

class VortexLattice:
    """
    Full simulation engine for the Moving-Vortex Braid experiment.

    Workflow
    --------
    lattice = VortexLattice(config)
    lattice.build()                          # construct nodes + base field
    ctrl   = lattice.run_braid("control")   # omega=0 reference
    coup   = lattice.run_braid("coupled")   # omega=config.omega_gauge
    """

    def __init__(self, config: Optional[LatticeConfig] = None):
        self.config     = config or LatticeConfig()
        self.nodes: Optional[LatticeNodes] = None
        self.clf        = WindingClassifier()
        self.pair_analyzer = WindingPairAnalyzer(self.clf)
        self._built     = False

    # ── build ────────────────────────────────────────────────────────────────

    def build(self) -> LatticeNodes:
        """
        Construct the lattice grid and initialise psi_down with the two-vortex
        Ansatz field.  No gauge coupling applied yet.
        """
        cfg = self.config
        t0  = time.perf_counter()
        print(f"Building {cfg.lattice_type} lattice ({cfg.Lx}×{cfg.Ly} = {cfg.n_nodes} nodes)...")

        # Grid coordinates
        x_lin = np.arange(cfg.Lx, dtype=float)
        y_lin = np.arange(cfg.Ly, dtype=float)
        X, Y  = np.meshgrid(x_lin, y_lin)

        # For triangular lattice, offset every other row by 0.5
        if cfg.lattice_type == "triangular":
            X[1::2, :] += 0.5

        # Build base psi_down field (product of vortex phase singularities)
        psi_down = self._build_vortex_field(X, Y, cfg.vortex_A_pos, cfg.vortex_B_pos)

        self.nodes = LatticeNodes(X=X, Y=Y, psi_down=psi_down, n_nodes=cfg.n_nodes)
        self._built = True

        elapsed = time.perf_counter() - t0
        print(f"Lattice built in {elapsed*1000:.1f} ms  |  {self.nodes}")
        return self.nodes

    # ── braid run ────────────────────────────────────────────────────────────

    def run_braid(self, regime: str = "coupled") -> "BraidResult":
        """
        Execute CW and CCW braiding of vortex A around vortex B.
        Applies gauge coupling when regime == "coupled".

        Returns BraidResult containing both WindingResults and the L2 difference.
        """
        if not self._built:
            self.build()

        cfg = self.config
        omega = cfg.omega_gauge if regime == "coupled" else 0.0

        print(f"\n{'─'*60}")
        print(f"  BRAID RUN  |  regime={regime.upper()}  |  ω={omega:.4f}")
        print(f"{'─'*60}")

        # Compute gauge-modified field
        psi_field = self._apply_gauge(self.nodes.psi_down, omega)

        # CW run: vortex A moves clockwise around B
        W_cw, psi_cw = self._execute_braid(psi_field, "CW", omega)
        # CCW run: vortex A moves counter-clockwise around B
        W_ccw, psi_ccw = self._execute_braid(psi_field, "CCW", omega)

        # L2 field difference
        l2_diff = float(np.linalg.norm(np.abs(psi_cw) - np.abs(psi_ccw))) / cfg.n_nodes

        # Classify each winding
        r_cw  = self.clf.classify(W_cw,  "CW",  regime, omega)
        r_ccw = self.clf.classify(W_ccw, "CCW", regime, omega)

        print(f"  CW  winding  : {W_cw:+.6f}  →  {r_cw.logic_state.value}")
        print(f"  CCW winding  : {W_ccw:+.6f}  →  {r_ccw.logic_state.value}")
        print(f"  L² diff      : {l2_diff:.6f}")

        return BraidResult(
            regime       = regime,
            omega_gauge  = omega,
            cw_result    = r_cw,
            ccw_result   = r_ccw,
            l2_diff      = l2_diff,
            psi_cw       = psi_cw,
            psi_ccw      = psi_ccw,
        )

    # ── field construction ───────────────────────────────────────────────────

    def _build_vortex_field(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        pos_A: tuple[float, float],
        pos_B: tuple[float, float],
    ) -> np.ndarray:
        """
        ψ_down(r) = exp(i · θ_A(r)) · exp(i · θ_B(r))
        θ_k(r)   = charge_k · atan2(y - y_k, x - x_k)
        """
        cfg   = self.config
        Lx, Ly = cfg.Lx, cfg.Ly
        eps   = cfg.path_epsilon

        # Vortex A
        xA, yA = pos_A[0] * Lx, pos_A[1] * Ly
        dxA = X - xA
        dyA = Y - yA
        rA  = np.sqrt(dxA**2 + dyA**2) + eps
        thetaA = cfg.vortex_A_charge * np.arctan2(dyA, dxA)

        # Vortex B
        xB, yB = pos_B[0] * Lx, pos_B[1] * Ly
        dxB = X - xB
        dyB = Y - yB
        rB  = np.sqrt(dxB**2 + dyB**2) + eps
        thetaB = cfg.vortex_B_charge * np.arctan2(dyB, dxB)

        # Amplitude envelope: Gaussian suppression at vortex cores
        amp  = np.tanh(rA / 2.0) * np.tanh(rB / 2.0)
        psi  = amp * np.exp(1j * (thetaA + thetaB))

        return psi.astype(np.complex128)

    def _apply_gauge(self, psi: np.ndarray, omega: float) -> np.ndarray:
        """
        Peierls gauge coupling:
          ψ_coupled(r) = ψ(r) · exp(i · ω · A(r))
        where A(r) is the transverse gauge potential centered on vortex B.
        A(r) = (−dy, dx) / (2π · r²)  (Dirac-string-free, antisymmetric)
        """
        if abs(omega) < 1e-10:
            return psi.copy()

        cfg   = self.config
        xB, yB = self.config.vortex_B_grid
        dx = self.nodes.X - xB
        dy = self.nodes.Y - yB
        r2 = dx**2 + dy**2 + cfg.path_epsilon**2

        # Gauge potential (azimuthal component)
        A = 0.5 * np.arctan2(dy, dx) / np.pi   # range (−0.5, 0.5]
        A = np.clip(A, -cfg.gauge_cutoff, cfg.gauge_cutoff)

        return (psi * np.exp(1j * omega * A)).astype(np.complex128)

    def _execute_braid(
        self,
        psi_base:  np.ndarray,
        direction: str,
        omega:     float,
    ) -> tuple[float, np.ndarray]:
        """
        Move vortex A on a circular path around vortex B, accumulating the
        phase winding at each step.  Returns (W, final_psi).
        """
        cfg   = self.config
        Lx, Ly = cfg.Lx, cfg.Ly
        eps   = cfg.path_epsilon

        # Braid center = vortex B position
        cx_frac, cy_frac = cfg.vortex_B_pos
        cx = cx_frac * Lx
        cy = cy_frac * Ly
        r  = cfg.braid_radius * min(Lx, Ly)

        # Parametric braid angles
        angles = np.linspace(0, 2 * np.pi, cfg.n_braid_steps, endpoint=False)
        if direction == "CCW":
            pass                    # default: counter-clockwise (increasing angle)
        else:
            angles = angles[::-1]   # CW: reverse

        # Starting position of vortex A (at angle 0 from B)
        psi = psi_base.copy()

        for angle in angles:
            # New position of vortex A
            xA_new = cx + r * np.cos(angle)
            yA_new = cy + r * np.sin(angle)

            # Recompute vortex A contribution at new position
            dxA = self.nodes.X - xA_new
            dyA = self.nodes.Y - yA_new
            rA  = np.sqrt(dxA**2 + dyA**2) + eps
            amp  = np.tanh(rA / 2.0)
            phase = cfg.vortex_A_charge * np.arctan2(dyA, dxA)

            psi = amp * np.exp(1j * phase) * psi_base
            # Re-apply gauge
            if abs(omega) > 1e-10:
                xB, yB = self.config.vortex_B_grid
                dx = self.nodes.X - xB
                dy = self.nodes.Y - yB
                A  = 0.5 * np.arctan2(dy, dx) / np.pi
                A  = np.clip(A, -cfg.gauge_cutoff, cfg.gauge_cutoff)
                psi = psi * np.exp(1j * omega * A)

        # Measure winding around vortex B using field-based method
        W = self.clf._compute_field_winding(
            psi,
            center    = self.config.vortex_B_grid,
            radius    = self.config.path_radius_px,
            direction = direction,
            n_points  = 256,
        )
        return W, psi


# ─────────────────────────────────────────────────────────────────────────────
# Braid result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BraidResult:
    """Output of a single braid run (CW + CCW pair)."""
    regime:      str
    omega_gauge: float
    cw_result:   WindingResult
    ccw_result:  WindingResult
    l2_diff:     float
    psi_cw:      np.ndarray
    psi_ccw:     np.ndarray

    @property
    def winding_cw(self)  -> float: return self.cw_result.raw_winding
    @property
    def winding_ccw(self) -> float: return self.ccw_result.raw_winding
    @property
    def asymmetry(self)   -> float: return abs(self.winding_cw - self.winding_ccw)

    def summary(self) -> str:
        return (
            f"\n--- {self.regime.upper()} (omega_gauge = {self.omega_gauge}) ---\n"
            f"  CW:  psi_down winding number around vortex B = {self.winding_cw:.4f}\n"
            f"       State: {self.cw_result.logic_state.value}\n"
            f"       Gate : {self.cw_result.gate_label}  [{self.cw_result.gate_symbol}]\n"
            f"  CCW: psi_down winding number around vortex B = {self.winding_ccw:.4f}\n"
            f"       State: {self.ccw_result.logic_state.value}\n"
            f"       Gate : {self.ccw_result.gate_label}  [{self.ccw_result.gate_symbol}]\n"
            f"  psi_down field L2 difference between CW and CCW: {self.l2_diff:.6f}"
        )
