import numpy as np
import time

def simulate_vortex_trajectory(omega_gauge, path_chirality):
    """
    Executes a true continuous-time differential evolution pass over a 1D ring lattice.
    Updates the fields cumulatively from step (n-1) to step n.
    path_chirality = +1: Clockwise trajectory drive
    path_chirality = -1: Counter-Clockwise trajectory drive
    """
    NUM_NODES = 2048       # Controlled node sample to explicitly prevent phase-aliasing
    HBAR, MASS = 1.0, 1.0
    DX, DT = 0.2, 0.002
    G_COEFF = 0.1

    # Initialize arrays
    u_re = np.zeros(NUM_NODES, dtype=np.float64)
    u_im = np.zeros(NUM_NODES, dtype=np.float64)
    d_re = np.zeros(NUM_NODES, dtype=np.float64)
    d_im = np.zeros(NUM_NODES, dtype=np.float64)

    # Smooth Gaussian wave packet in the Up channel
    x_coords = np.arange(NUM_NODES) * DX
    center = (NUM_NODES * DX) / 2.0
    u_re[:] = np.exp(-((x_coords - center) ** 2) / 4.0)

    # Stable unit background topological vortex in the Down channel
    d_re[:] = np.cos(2.0 * np.pi * x_coords / (NUM_NODES * DX))
    d_im[:] = np.sin(2.0 * np.pi * x_coords / (NUM_NODES * DX))

    idx = np.arange(NUM_NODES)
    left_nb = (idx - 1) % NUM_NODES
    right_nb = (idx + 1) % NUM_NODES
    Ax = np.sin(2.0 * np.pi * x_coords / (NUM_NODES * DX))

    # Time-Step Loop (Evolves the field state forward step-by-step)
    for step in range(60):
        driver_pos = int((NUM_NODES / 2) + (path_chirality * step * 4)) % NUM_NODES
        u_re[driver_pos] += 0.5 * DT

        lap_u_re = (u_re[right_nb] + u_re[left_nb] - 2.0 * u_re) / (DX**2)
        lap_u_im = (u_im[right_nb] + u_im[left_nb] - 2.0 * u_im) / (DX**2)
        lap_d_re = (d_re[right_nb] + d_re[left_nb] - 2.0 * d_re) / (DX**2)
        lap_d_im = (d_im[right_nb] + d_im[left_nb] - 2.0 * d_im) / (DX**2)

        rho_u = u_re**2 + u_im**2
        rho_d = d_re**2 + d_im**2

        soc_u_re = -(Ax * d_im * omega_gauge)
        soc_u_im = (Ax * d_re * omega_gauge)
        soc_d_re = -(Ax * u_im * omega_gauge)
        soc_d_im = (Ax * u_re * omega_gauge)

        h_u_re = -(HBAR**2 / (2 * MASS)) * lap_u_re + (G_COEFF * rho_u) * u_re + soc_u_re
        h_u_im = -(HBAR**2 / (2 * MASS)) * lap_u_im + (G_COEFF * rho_u) * u_im + soc_u_im
        h_d_re = -(HBAR**2 / (2 * MASS)) * lap_d_re + (G_COEFF * rho_d) * d_re + soc_d_re
        h_d_im = -(HBAR**2 / (2 * MASS)) * lap_d_im + (G_COEFF * rho_d) * d_im + soc_d_im

        # Cumulative additions (No state overwriting)
        u_re += h_u_im * DT; u_im -= h_u_re * DT
        d_re += h_d_im * DT; d_im -= h_d_re * DT

        system_mass = np.sum(u_re**2 + u_im**2 + d_re**2 + d_im**2)
        if system_mass > 0:
            norm = np.sqrt(100.0 / system_mass)
            u_re *= norm; u_im *= norm
            d_re *= norm; d_im *= norm

    return u_re + 1j * u_im, d_re + 1j * d_im

if __name__ == "__main__":
    print("\n" + "="*85)
    print("[ INITIALIZING REAL EXPERIMENTAL CORE ] RUNNING HARDENED PDE LATTICE SOLVER")
    print("="*85)

    omega_sweeps = [0.0, 2.5, 15.0]

    for omega in omega_sweeps:
        print(f"\nEvaluating System Parameters at Omega Gauge = {omega:.1f}...")
        u_cw, d_cw = simulate_vortex_trajectory(omega_gauge=omega, path_chirality=+1)
        u_ccw, d_ccw = simulate_vortex_trajectory(omega_gauge=omega, path_chirality=-1)

        amp_diff_u = np.mean(np.abs(np.abs(u_cw) - np.abs(u_ccw)))
        amp_diff_d = np.mean(np.abs(np.abs(d_cw) - np.abs(d_ccw)))

        # Phase angle divergence metric
        phase_diff_u = np.mean(np.abs(np.angle(u_cw) - np.angle(u_ccw)))
        phase_diff_d = np.mean(np.abs(np.angle(d_cw) - np.angle(d_ccw)))

        print(f"  [AMPLITUDE CHANNEL DIVERGENCE]")
        print(f"    -> Up Spin Modulus Variance  : {amp_diff_u:.2e}")
        print(f"    -> Down Spin Modulus Variance: {amp_diff_d:.2e}")
        print(f"  [PHASE CHANNEL ANGLE DIVERGENCE]")
        print(f"    -> Up Spin Phase Delta       : {phase_diff_u:.6f} Radians")
        print(f"    -> Down Spin Phase Delta     : {phase_diff_d:.6f} Radians")
        print("-" * 85)

    print("="*85 + "\n")
