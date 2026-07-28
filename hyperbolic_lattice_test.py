import numpy as np
import time

def simulate_isotropic_lattice(omega_gauge, path_chirality):
    """
    Simulates an isotropic 2D spatial ring grid with symmetric stencils.
    Updates the fields cumulatively from step n-1 to step n.
    """
    GRID_RES = 64
    NUM_NODES = GRID_RES * GRID_RES # 4,096 Node Controlled Isotropic Cluster
    HBAR, MASS = 1.0, 1.0
    DX, DT = 0.2, 0.001
    G_BASE = 0.1
    RHO_CEILING = 10.0

    # Allocate complex spinor fields
    u_field = np.zeros((GRID_RES, GRID_RES), dtype=np.complex128)
    d_field = np.zeros((GRID_RES, GRID_RES), dtype=np.complex128)

    # Initialize a localized, symmetric Gaussian packet in the center of the Up channel
    y, x = np.ogrid[:GRID_RES, :GRID_RES]
    center = GRID_RES / 2.0
    u_field.real = np.exp(-((x - center)**2 + (y - center)**2) / 8.0)

    # Background topological phase field in the Down channel
    d_field.real = np.cos(2.0 * np.pi * x / GRID_RES)
    d_field.imag = np.sin(2.0 * np.pi * y / GRID_RES)

    # Spatially varying non-linear vector potential operators (A_x, A_y)
    Ax = np.sin(2.0 * np.pi * x / GRID_RES)
    Ay = np.cos(2.0 * np.pi * y / GRID_RES)

    # --- CUMULATIONAL TIME INTEGRATION LOOP ---
    for step in range(50):
        # Translate the driver vortex symmetrically along a true circular 2D orbit
        angle = path_chirality * step * (2.0 * np.pi / 50)
        orbit_x = int(center + 12 * np.cos(angle)) % GRID_RES
        orbit_y = int(center + 12 * np.sin(angle)) % GRID_RES

        # Inject symmetric kinetic energy at the coordinate intercept
        u_field[orbit_y, orbit_x] += 0.4 * DT

        # Compute 2D central finite-difference Laplacians
        # lap(psi) = (psi_{x+1} + psi_{x-1} + psi_{y+1} + psi_{y-1} - 4*psi) / DX^2
        lap_u = (np.roll(u_field, 1, axis=1) + np.roll(u_field, -1, axis=1) +
                 np.roll(u_field, 1, axis=0) + np.roll(u_field, -1, axis=0) - 4.0 * u_field) / (DX**2)

        lap_d = (np.roll(d_field, 1, axis=1) + np.roll(d_field, -1, axis=1) +
                 np.roll(d_field, 1, axis=0) + np.roll(d_field, -1, axis=0) - 4.0 * d_field) / (DX**2)

        rho_u = np.clip(np.abs(u_field)**2, 0.0, RHO_CEILING)
        rho_d = np.clip(np.abs(d_field)**2, 0.0, RHO_CEILING)

        # Proactive Quantum-Pressure Limiter Governor
        dynamic_g = G_BASE * (1.0 / (1.0 + (rho_u + rho_d) / RHO_CEILING))

        # True SU(2) Cross-Talk Gauge Stencils
        soc_u = -1j * omega_gauge * (Ax * d_field + Ay * d_field)
        soc_d = -1j * omega_gauge * (Ax * u_field + Ay * u_field)

        # Evaluate coupled continuous differential Hamiltonians
        h_u = -(HBAR**2 / (2 * MASS)) * lap_u + (dynamic_g * rho_u) * u_field + soc_u
        h_d = -(HBAR**2 / (2 * MASS)) * lap_d + (dynamic_g * rho_d) * d_field + soc_d

        # Evolve fields forward cumulatively without overwriting state variables
        u_field += -1j * h_u * DT
        d_field += -1j * h_d * DT

        # Unitary Mass lock
        total_mass = np.sum(np.abs(u_field)**2 + np.abs(d_field)**2)
        if total_mass > 0:
            norm = np.sqrt(100.0 / total_mass)
            u_field *= norm; d_field *= norm

    return u_field, d_field
if __name__ == "__main__":
    print("\n" + "="*90)
    print("[ ISOTROPIC LATTICE GEOMETRY TRIAL ] EVALUATING TRUE PATH-DEPENDENCE")
    print("="*90)

    omega_sweeps = [0.0, 3.5, 12.0]

    for omega in omega_sweeps:
        print(f"\nEvaluating Isotropic Matrix at Omega Gauge = {omega:.1f}...")

        # Execute identical spatial trajectories in opposite orbit directions
        u_cw, d_cw = simulate_isotropic_lattice(omega_gauge=omega, path_chirality=+1)
        u_ccw, d_ccw = simulate_isotropic_lattice(omega_gauge=omega, path_chirality=-1)

        # Calculate raw phase angle field variance cleanly
        phase_diff_u = np.mean(np.abs(np.angle(u_cw) - np.angle(u_ccw)))
        phase_diff_d = np.mean(np.abs(np.angle(d_cw) - np.angle(d_ccw)))

        print(f"  [PHASE CHANNEL ANGLE DIVERGENCE]")
        print(f"    -> Up Spin Phase Delta       : {phase_diff_u:.6f} Radians")
        print(f"    -> Down Spin Phase Delta     : {phase_diff_d:.6f} Radians")
        print("-" * 90)

    print("="*90 + "\n")
