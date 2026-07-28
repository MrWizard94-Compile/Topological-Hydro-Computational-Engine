"""
================================================================================
MOVING-VORTEX BRAID TEST WITH LIVE DIGITAL LOGIC COUPLING
================================================================================
MemoryMatrix 3.0  |  VortexBraid Engine v3.1.0
Upgrade: NULL-register decoder replaced with physics-correct winding classifier

Run modes
---------
  python main_simulation.py               # full run (control + coupled)
  python main_simulation.py --quick       # small lattice, fast demo
  python main_simulation.py --sweep       # omega sweep 0→3
  python main_simulation.py --validate    # reproduce your original numbers

Output
------
  Console      : formatted matrix with decoded states (no more NULL REGISTER)
  JSON         : results_<timestamp>.json  — machine-readable full output
  Replay file  : winding_history.json      — state log for MemoryMatrix integration
================================================================================
"""

from __future__ import annotations

import argparse
import json
import time
import sys
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

from winding_classifier import (
    WindingClassifier,
    WindingPairAnalyzer,
    LogicState,
)
from vortex_lattice import (
    LatticeConfig,
    VortexLattice,
    BraidResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Printer helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sep(char: str = "=", width: int = 80) -> str:
    return char * width

def _header(title: str, char: str = "=", width: int = 80) -> None:
    pad = (width - len(title) - 2) // 2
    print(f"\n{_sep(char, width)}")
    print(f"{char * pad} {title} {char * (width - pad - len(title) - 2)}")
    print(_sep(char, width))

def _row(label: str, value: str, width: int = 80) -> str:
    pad = width - len(label) - len(value) - 4
    return f"  {label}{' ' * max(1, pad)}{value}"


# ─────────────────────────────────────────────────────────────────────────────
# Logic matrix printer
# ─────────────────────────────────────────────────────────────────────────────

def print_logic_matrix(
    ctrl_result: BraidResult,
    coup_result: BraidResult,
    ctrl_baseline: float,
    ctrl_l2: float,
) -> None:
    """
    Upgraded replacement for the original TOPOLOGICAL LOGIC MATRIX INTEGRATION block.
    Replaces NULL REGISTER with decoded physics states.
    """
    pair_analyzer = WindingPairAnalyzer()

    ctrl_verdict = pair_analyzer.analyze(
        W_cw             = ctrl_result.winding_cw,
        W_ccw            = ctrl_result.winding_ccw,
        control_baseline = ctrl_baseline,
        omega_gauge      = 0.0,
        regime           = "control",
    )
    coup_verdict = pair_analyzer.analyze(
        W_cw             = coup_result.winding_cw,
        W_ccw            = coup_result.winding_ccw,
        control_baseline = ctrl_baseline,
        omega_gauge      = coup_result.omega_gauge,
        regime           = "coupled",
    )

    W = 80
    _header("TOPOLOGICAL LOGIC MATRIX INTEGRATION")

    col_w = [32, 12, 10, 38]
    cols  = ["Simulation Channel", "Winding W", "Gate", "Decoded Logic State"]

    # Header row
    row = "  " + "| ".join(c.ljust(w) for c, w in zip(cols, col_w))
    print(row)
    print("  " + "-" * (W - 2))

    channels = [
        ("Control CW  ↻",  ctrl_result.cw_result,  ctrl_verdict),
        ("Control CCW ↺",  ctrl_result.ccw_result, ctrl_verdict),
        ("Coupled CW  ↻",  coup_result.cw_result,  coup_verdict),
        ("Coupled CCW ↺",  coup_result.ccw_result, coup_verdict),
    ]

    for name, res, verdict in channels:
        state_str  = res.logic_state.value.strip()
        gate_str   = f"{res.gate_label}"
        path_marker = " ★" if res.path_dependence_flag else "  "
        cols_vals  = [
            name + path_marker,
            f"{res.raw_winding:+.4f}",
            gate_str,
            state_str,
        ]
        row = "  " + "| ".join(v.ljust(w) for v, w in zip(cols_vals, col_w))
        print(row)

    print("  " + "-" * (W - 2))
    print(f"  ★ = path-dependent channel (asymmetry above {WindingPairAnalyzer.RATIO_MEDIUM:.0f}× control baseline)")
    print(_sep())

    # Physical meaning section
    _header("DECODED PHYSICAL STATES")

    all_channels = [
        ("Control CW  ↻ (ω=0)",    ctrl_result.cw_result),
        ("Control CCW ↺ (ω=0)",    ctrl_result.ccw_result),
        (f"Coupled CW  ↻ (ω={coup_result.omega_gauge})", coup_result.cw_result),
        (f"Coupled CCW ↺ (ω={coup_result.omega_gauge})", coup_result.ccw_result),
    ]
    for name, res in all_channels:
        print(f"\n  [{name}]")
        print(f"    State    : {res.logic_state.value}")
        print(f"    Gate     : {res.gate_label}  [{res.gate_symbol}]")
        print(f"    Non-Ab?  : {'YES — non-commutative braiding detected' if res.is_non_abelian else 'No  — Abelian / integer winding'}")
        print(f"    Meaning  : {res.physical_meaning}")

    print()

    # Path-dependence verdict
    _header("PATH-DEPENDENCE VERDICT")
    print(ctrl_verdict.report(width=W))
    print(coup_verdict.report(width=W))

    # Gate composition table
    _header("GATE COMPOSITION TABLE", "-")
    print(f"  {'Channel':<30} {'CW gate':<15} {'CCW gate':<15} {'CW⊗CCW pair':<20}")
    print(f"  {'-'*78}")
    for name, res_cw, res_ccw in [
        ("Control (ω=0)", ctrl_result.cw_result, ctrl_result.ccw_result),
        (f"Coupled (ω={coup_result.omega_gauge})", coup_result.cw_result, coup_result.ccw_result),
    ]:
        pair = f"{res_cw.gate_label} ⊗ {res_ccw.gate_label}"
        comm = "Commutes (Abelian)" if res_cw.gate_symbol == res_ccw.gate_symbol else "NON-COMMUTATIVE ★"
        print(f"  {name:<30} {res_cw.gate_label:<15} {res_ccw.gate_label:<15} {pair}")
        print(f"  {'':<30} {'':>30}  → {comm}")

    print()
    print(_sep())


# ─────────────────────────────────────────────────────────────────────────────
# Validation mode — reproduce original numbers
# ─────────────────────────────────────────────────────────────────────────────

def run_validation() -> None:
    """
    Replay the original simulation output and decode the NULL registers.
    Uses the exact winding numbers from the original run to demonstrate
    what the decoder *should* have said.
    """
    _header("VALIDATION MODE — DECODING ORIGINAL NULL REGISTERS")
    print("  Replaying original winding numbers and classifying correctly...\n")

    clf = WindingClassifier()
    pair = WindingPairAnalyzer(clf)

    original_data = {
        "control": {"cw": 0.9894, "ccw": 0.9894, "l2_diff": 0.000119},
        "coupled": {"cw": -1.8492, "ccw": -0.8382, "l2_diff": 0.039671},
    }

    print(_sep("-"))
    print("  ORIGINAL OUTPUT (NULL REGISTER — was wrong):")
    print(_sep("-"))
    for regime, d in original_data.items():
        print(f"\n  [{regime.upper()}]  CW={d['cw']}  CCW={d['ccw']}  L2={d['l2_diff']}")
        print(f"    CW  state : NULL REGISTER (Protected Control Baseline)  ← BUG")
        print(f"    CCW state : NULL REGISTER (Protected Control Baseline)  ← BUG")

    print(f"\n{_sep()}")
    print("  CORRECTED OUTPUT (WindingClassifier v3.1.0):")
    print(_sep("-"))

    ctrl_cw  = clf.classify(original_data["control"]["cw"],  "CW",  "control", 0.0)
    ctrl_ccw = clf.classify(original_data["control"]["ccw"], "CCW", "control", 0.0)
    coup_cw  = clf.classify(original_data["coupled"]["cw"],  "CW",  "coupled", 1.5)
    coup_ccw = clf.classify(original_data["coupled"]["ccw"], "CCW", "coupled", 1.5)

    for label, res in [
        ("Control CW  ↻ (ω=0)",  ctrl_cw),
        ("Control CCW ↺ (ω=0)",  ctrl_ccw),
        ("Coupled CW  ↻ (ω=1.5)", coup_cw),
        ("Coupled CCW ↺ (ω=1.5)", coup_ccw),
    ]:
        print(f"\n  [{label}]")
        print(f"    W        = {res.raw_winding:+.4f}")
        print(f"    State    : {res.logic_state.value}")
        print(f"    Gate     : {res.gate_label}  [{res.gate_symbol}]  — {res.gate_description}")
        print(f"    Non-Ab?  : {'YES' if res.is_non_abelian else 'No'}")
        print(f"    Meaning  : {res.physical_meaning}")

    print()
    ctrl_verdict = pair.analyze(
        original_data["control"]["cw"], original_data["control"]["ccw"],
        original_data["control"]["l2_diff"], 0.0, "control"
    )
    coup_verdict = pair.analyze(
        original_data["coupled"]["cw"], original_data["coupled"]["ccw"],
        original_data["control"]["l2_diff"], 1.5, "coupled"
    )

    print(ctrl_verdict.report())
    print(coup_verdict.report())

    # Write results
    out = {
        "mode": "validation",
        "original_winding_numbers": original_data,
        "corrected_states": {
            "control_cw":  ctrl_cw.to_dict(),
            "control_ccw": ctrl_ccw.to_dict(),
            "coupled_cw":  coup_cw.to_dict(),
            "coupled_ccw": coup_ccw.to_dict(),
        },
        "verdicts": {
            "control": ctrl_verdict.to_dict(),
            "coupled": coup_verdict.to_dict(),
        }
    }
    _save_json(out, "validation")


# ─────────────────────────────────────────────────────────────────────────────
# Omega sweep
# ─────────────────────────────────────────────────────────────────────────────

def run_sweep(n_steps: int = 20, quick: bool = False) -> None:
    """Sweep omega from 0 to 3 and record state transitions."""
    _header("OMEGA GAUGE SWEEP  (0 → 3.0)")

    cfg = LatticeConfig(Lx=40, Ly=30) if quick else LatticeConfig()
    clf = WindingClassifier()
    pair = WindingPairAnalyzer(clf)

    lattice = VortexLattice(cfg)
    lattice.build()

    omegas     = np.linspace(0.0, 3.0, n_steps)
    sweep_log  = []

    print(f"\n  {'ω':>6} | {'W_CW':>9} | {'W_CCW':>9} | {'Asymm':>9} | {'CW State':>22} | {'CCW State':>22}")
    print(f"  {'-'*95}")

    # Store the control baseline (omega=0) for ratio reporting
    ctrl_baseline = None

    for omega in omegas:
        cfg.omega_gauge = omega
        coup = lattice.run_braid("coupled" if omega > 0 else "control")

        if ctrl_baseline is None:
            ctrl_baseline = max(coup.l2_diff, 1e-8)

        verdict = pair.analyze(
            coup.winding_cw, coup.winding_ccw,
            ctrl_baseline, omega,
            "coupled" if omega > 0 else "control"
        )

        cw_s  = coup.cw_result.logic_state.name
        ccw_s = coup.ccw_result.logic_state.name
        asym  = verdict.asymmetry
        conf  = verdict.confidence[0] if verdict.confidence != "NONE" else "·"

        print(f"  {omega:>6.3f} | {coup.winding_cw:>+9.4f} | {coup.winding_ccw:>+9.4f} | "
              f"{asym:>9.6f} | {cw_s:>22} | {ccw_s:>22}  [{conf}]")

        sweep_log.append({
            "omega":    round(omega, 4),
            "W_CW":     round(coup.winding_cw, 6),
            "W_CCW":    round(coup.winding_ccw, 6),
            "L2_diff":  round(coup.l2_diff, 8),
            "asymmetry": round(asym, 8),
            "confidence": verdict.confidence,
            "cw_state":  coup.cw_result.logic_state.name,
            "ccw_state": coup.ccw_result.logic_state.name,
            "gate_cw":   coup.cw_result.gate_label,
            "gate_ccw":  coup.ccw_result.gate_label,
            "path_dependent": verdict.is_path_dependent,
        })

    # Find transition points
    transitions = []
    prev_cw = sweep_log[0]["cw_state"]
    prev_ccw = sweep_log[0]["ccw_state"]
    for entry in sweep_log[1:]:
        if entry["cw_state"] != prev_cw or entry["ccw_state"] != prev_ccw:
            transitions.append({
                "omega": entry["omega"],
                "from_cw": prev_cw,
                "to_cw": entry["cw_state"],
                "from_ccw": prev_ccw,
                "to_ccw": entry["ccw_state"],
            })
            prev_cw, prev_ccw = entry["cw_state"], entry["ccw_state"]

    print(f"\n  {_sep('-')}")
    print(f"  STATE TRANSITIONS DETECTED:  {len(transitions)}")
    for t in transitions:
        print(f"    ω={t['omega']:.3f}  CW: {t['from_cw']} → {t['to_cw']}")
        print(f"    ω={t['omega']:.3f}  CCW: {t['from_ccw']} → {t['to_ccw']}")

    _save_json({"sweep": sweep_log, "transitions": transitions}, "sweep")


# ─────────────────────────────────────────────────────────────────────────────
# Full run
# ─────────────────────────────────────────────────────────────────────────────

def run_full(quick: bool = False) -> None:
    """
    Full control + coupled braid run with decoded logic matrix output.
    This is the drop-in replacement for the original simulation.
    """
    _header("MOVING-VORTEX BRAID TEST WITH LIVE DIGITAL LOGIC COUPLING")

    # Config
    if quick:
        cfg = LatticeConfig(Lx=40, Ly=30, omega_gauge=1.5)
        print("  [QUICK MODE: 40×30 lattice]")
    else:
        # Lx=80 × Ly=63 = 5040 nodes ≈ original 5017
        cfg = LatticeConfig(Lx=80, Ly=63, omega_gauge=1.5)

    t_total = time.perf_counter()

    # Build lattice
    lattice = VortexLattice(cfg)
    lattice.build()

    # ── Control run (omega=0) ──────────────────────────────────────────────
    _header("CONTROL (omega_gauge = 0)", "-")
    ctrl_result = lattice.run_braid("control")

    # ── Coupled run (omega=cfg.omega_gauge) ───────────────────────────────
    _header(f"COUPLED (omega_gauge = {cfg.omega_gauge})", "-")
    coup_result = lattice.run_braid("coupled")

    # ── Physical field verdict ─────────────────────────────────────────────
    _header("PHYSICAL FIELD VERDICT")
    ctrl_diff = ctrl_result.l2_diff
    coup_diff = coup_result.l2_diff
    ratio     = coup_diff / max(ctrl_diff, 1e-12)

    print(f"  Control  (no coupling) CW vs CCW difference: {ctrl_diff:.6f}"
          f"  <- expected near-zero baseline")
    print(f"  Coupled  (gauge on)    CW vs CCW difference: {coup_diff:.6f}")
    print()
    if coup_diff > ctrl_diff * 5:
        print(f"  Coupled difference is {'well ' if ratio > 50 else ''}above the control baseline: "
              f"genuine path-dependence detected")
        print(f"  in the field that was never directly touched. "
              f"This IS evidence of real history-dependence.")
        print(f"  Ratio: {ratio:.1f}×  (Δ_coupled / Δ_control)")
    else:
        print(f"  Coupled difference is near control baseline ({ratio:.2f}×).")
        print(f"  Consider increasing omega_gauge or lattice size.")
    print(_sep())

    # ── Logic matrix with decoded states ──────────────────────────────────
    print_logic_matrix(ctrl_result, coup_result, ctrl_diff, ctrl_diff)

    # ── Timing ────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t_total
    _header("RUN COMPLETE")
    print(f"  Total wall time: {elapsed:.2f}s")
    print(f"  Lattice nodes  : {cfg.n_nodes}")
    print(f"  Omega gauge    : {cfg.omega_gauge}")
    print(f"  Path ratio     : {ratio:.1f}×")

    # ── Save JSON ─────────────────────────────────────────────────────────
    output = {
        "run_mode":    "full",
        "config":      {
            "Lx": cfg.Lx, "Ly": cfg.Ly, "n_nodes": cfg.n_nodes,
            "omega_gauge": cfg.omega_gauge,
            "lattice_type": cfg.lattice_type,
            "braid_radius": cfg.braid_radius,
            "n_braid_steps": cfg.n_braid_steps,
        },
        "control": {
            "cw":     ctrl_result.cw_result.to_dict(),
            "ccw":    ctrl_result.ccw_result.to_dict(),
            "l2_diff": ctrl_diff,
        },
        "coupled": {
            "cw":     coup_result.cw_result.to_dict(),
            "ccw":    coup_result.ccw_result.to_dict(),
            "l2_diff": coup_diff,
        },
        "path_dependence_ratio": round(ratio, 4),
        "wall_time_s": round(elapsed, 3),
    }
    _save_json(output, "full")

    # ── Write winding history for MemoryMatrix integration ─────────────────
    _write_winding_history(ctrl_result, coup_result, cfg.omega_gauge)


# ─────────────────────────────────────────────────────────────────────────────
# MemoryMatrix integration — winding history file
# ─────────────────────────────────────────────────────────────────────────────

def _write_winding_history(
    ctrl: BraidResult,
    coup: BraidResult,
    omega: float,
) -> None:
    """
    Write a winding_history.json that can be ingested by the MemoryMatrix
    state engine for cross-session replay and logic-state archiving.
    """
    history = {
        "schema":    "MemoryMatrix_WindingHistory_v3.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "omega_gauge": omega,
        "channels": {
            "control_cw":  _channel_entry(ctrl.cw_result),
            "control_ccw": _channel_entry(ctrl.ccw_result),
            "coupled_cw":  _channel_entry(coup.cw_result),
            "coupled_ccw": _channel_entry(coup.ccw_result),
        },
        "field_metrics": {
            "control_l2_diff": ctrl.l2_diff,
            "coupled_l2_diff": coup.l2_diff,
            "path_dependence_ratio": coup.l2_diff / max(ctrl.l2_diff, 1e-12),
        },
        "verdict": {
            "path_dependent": coup.l2_diff > ctrl.l2_diff * 5,
            "non_abelian_detected": (
                coup.cw_result.is_non_abelian or coup.ccw_result.is_non_abelian
            ),
            "gate_pair": f"{coup.cw_result.gate_label} ⊗ {coup.ccw_result.gate_label}",
        }
    }
    path = Path("winding_history.json")
    path.write_text(json.dumps(history, indent=2, default=lambda x: bool(x) if isinstance(x, bool) else str(x)))
    print(f"\n  [MemoryMatrix] Winding history written → {path.resolve()}")


def _channel_entry(res) -> dict:
    return {
        "raw_winding":  round(res.raw_winding, 6),
        "logic_state":  res.logic_state.name,
        "gate_label":   res.gate_label,
        "gate_symbol":  res.gate_symbol,
        "is_fractional": res.is_fractional,
        "is_non_abelian": res.is_non_abelian,
        "physical_meaning": res.physical_meaning,
    }


# ─────────────────────────────────────────────────────────────────────────────
# JSON output helper
# ─────────────────────────────────────────────────────────────────────────────

def _save_json(data: dict, tag: str) -> None:
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = Path(f"results_{tag}_{ts}.json")
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"\n  [Output] Results saved → {path.resolve()}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MemoryMatrix 3.0 — Moving-Vortex Braid Simulation v3.1.0"
    )
    parser.add_argument("--quick",    action="store_true",
                        help="Use small lattice (fast demo, ~2s)")
    parser.add_argument("--sweep",    action="store_true",
                        help="Run omega sweep 0→3 instead of single run")
    parser.add_argument("--validate", action="store_true",
                        help="Decode original null-register output without re-running")
    parser.add_argument("--omega",    type=float, default=1.5,
                        help="Override omega_gauge (default: 1.5)")
    parser.add_argument("--steps",    type=int,   default=20,
                        help="Number of omega steps in sweep mode (default: 20)")
    args = parser.parse_args()

    if args.validate:
        run_validation()
    elif args.sweep:
        run_sweep(n_steps=args.steps, quick=args.quick)
    else:
        run_full(quick=args.quick)


if __name__ == "__main__":
    main()
