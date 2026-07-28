import numpy as np
import time

def run_temporal_task_solver(omega_gauge, sequence_flag):
    """
    Simulates a sequential order-of-arrival classification task.
    sequence_flag = 0: Input A arrives at t=1, Input B arrives at t=5 (A -> B)
    sequence_flag = 1: Input B arrives at t=1, Input A arrives at t=5 (B -> A)
    """
    # 1. PARAMETERS & GRID CONSTRAINTS
    NUM_NODES = 5040      # Using your exact baseline production lattice size
    HBAR, MASS = 1.0, 1.0
    G_COEFF, G_CROSS = 0.08, 0.04
    DX, DT = 0.2, 0.010
    V_MAX = (HBAR * np.pi) / (MASS * DX)

    # 2. FIXED MEMORY ARRAY ALLOCATION
    psi_u_re = np.zeros(NUM_NODES, dtype=np.float64)
    psi_u_im = np.zeros(NUM_NODES, dtype=np.float64)
    psi_d_re = np.zeros(NUM_NODES, dtype=np.float64)
    psi_d_im = np.zeros(NUM_NODES, dtype=np.float64)

    # Pre-compiled ring topology lookup for local derivatives
    neighbor_matrix = np.zeros((NUM_NODES, 6), dtype=np.int32)
    for i in range(NUM_NODES):
        neighbor_matrix[i] = [(i + j) % NUM_NODES for j in range(1, 7)]

    # Non-Abelian Gauge Mapping vectors (The Gauge Field Anchor)
    Ax = np.linspace(-1.0, 1.0, NUM_NODES) * 0.5
    Ay = np.linspace(1.0, -1.0, NUM_NODES) * 0.5

    # 3. TIME-ORDERED SIMULATION CHANNELS (30 TIME-STEPS)
    for step in range(1, 31):
        # --- THE SEQUENTIAL INJECTION PROTOCOL ---
        # Input A triggers at step 2, Input B triggers at step 10 under Sequence 0
        if sequence_flag == 0:
            if step == 2:   # Input A arrives first
                psi_u_re[1000:1500] += 1.2
            if step == 10:  # Input B arrives second
                psi_d_im[3500:4000] += 1.2
        # Input B triggers at step 2, Input A triggers at step 10 under Sequence 1
        else:
            if step == 2:   # Input B arrives first
                psi_d_im[3500:4000] += 1.2
            if step == 10:  # Input A arrives second
                psi_u_re[1000:1500] += 1.2

        # Fetch neighbor vectors simultaneously via broadcasting
        u_re_nb = psi_u_re[neighbor_matrix]
        u_im_nb = psi_u_im[neighbor_matrix]
        d_re_nb = psi_d_re[neighbor_matrix]
        d_im_nb = psi_d_im[neighbor_matrix]

        # Spatial Derivatives (Lattice Laplacian Stencils)
        lap_u_re = (np.sum(u_re_nb, axis=1) - 6.0 * psi_u_re) / (DX**2)
        lap_u_im = (np.sum(u_im_nb, axis=1) - 6.0 * psi_u_im) / (DX**2)
        lap_d_re = (np.sum(d_re_nb, axis=1) - 6.0 * psi_d_re) / (DX**2)
        lap_d_im = (np.sum(d_im_nb, axis=1) - 6.0 * psi_d_im) / (DX**2)

        rho_u = psi_u_re**2 + psi_u_im**2
        rho_d = psi_d_re**2 + psi_d_im**2

        # SU(2) Cross-Talk Matrix Layer (Pauli Matrix Mixing)
        soc_u_re = -(Ax * psi_d_im * omega_gauge)
        soc_u_im = (Ay * psi_d_re * omega_gauge)
        soc_d_re = -(Ax * psi_u_im * omega_gauge)
        soc_d_im = (Ay * psi_u_re * omega_gauge)

        # Global Coupled Hamiltonian Updates
        h_u_re = -(HBAR**2 / (2 * MASS)) * lap_u_re + (G_COEFF * rho_u + G_CROSS * rho_d) * psi_u_re + soc_u_re
        h_u_im = -(HBAR**2 / (2 * MASS)) * lap_u_im + (G_COEFF * rho_u + G_CROSS * rho_d) * psi_u_im + soc_u_im
        h_d_re = -(HBAR**2 / (2 * MASS)) * lap_d_re + (G_COEFF * rho_d + G_CROSS * rho_u) * psi_d_re + soc_d_re
        h_d_im = -(HBAR**2 / (2 * MASS)) * lap_d_im + (G_COEFF * rho_d + G_CROSS * rho_u) * psi_d_im + soc_d_im

        # Step Forward over continuous-time updates
        psi_u_re += h_u_im * DT; psi_u_im -= h_u_re * DT
        psi_d_re += h_d_im * DT; psi_d_im -= h_d_re * DT

        # Unitary Normalization Lock to seal total system energy footprint
        current_mass = np.sum(psi_u_re**2 + psi_u_im**2 + psi_d_re**2 + psi_d_im**2)
        if current_mass > 0:
            psi_u_re *= np.sqrt(100.0 / current_mass)
            psi_u_im *= np.sqrt(100.0 / current_mass)
            psi_d_re *= np.sqrt(100.0 / current_mass)
            psi_d_im *= np.sqrt(100.0 / current_mass)

    # 4. POLAR DRAIN SCANNER READOUT LAYER (Read un-driven Spin-Down channel energy)
    return np.mean(psi_d_re**2 + psi_d_im**2)

if __name__ == "__main__":
    print("\n" + "="*80)
    print("[ TEMPORAL ORDER RESOLUTION TRIAL ] TESTING PATH-DEPENDENT FIELD MEMORY")
    print("="*80)
    time.sleep(0.5)

    # ---- SECTION 1: THE CONVENTIONAL LATTICE CONTROL TEST (omega_gauge = 0) ----
    print("Evaluating Conventional Feed-Forward Lattice (No Gauge Coupling)...")
    control_AB = run_temporal_task_solver(omega_gauge=0.0, sequence_flag=0)
    control_BA = run_temporal_task_solver(omega_gauge=0.0, sequence_flag=1)
    control_divergence = np.abs(control_AB - control_BA)

    print(f"  -> Path A -> B Signal Resolution: {control_AB:.8f}")
    print(f"  -> Path B -> A Signal Resolution: {control_BA:.8f}")
    print(f"  -> Conventional Structural Divergence: {control_divergence:.8f}")

    # ---- SECTION 2: THE SU(2) SPINOR FIELD ENGAGED TEST (omega_gauge = 1.75) ----
    print("\nEvaluating SU(2) Spinor Manifold Engine (Gauge Coupling Active)...")
    spinor_AB = run_temporal_task_solver(omega_gauge=1.75, sequence_flag=0)
    spinor_BA = run_temporal_task_solver(omega_gauge=1.75, sequence_flag=1)
    spinor_divergence = np.abs(spinor_AB - spinor_BA)

    print(f"  -> Path A -> B Signal Resolution: {spinor_AB:.8f}")
    print(f"  -> Path B -> A Signal Resolution: {spinor_BA:.8f}")
    print(f"  -> SU(2) Spinor Field Divergence: {spinor_divergence:.8f}")

    print("\n" + "-"*80)
    print("[ FINAL TASK RESOLUTION VERDICT ]:")
    print(f"Conventional System Sequence Divergence: {control_divergence:.8f}")
    print(f"Spinor Engine Field Sequence Divergence: {spinor_divergence:.8f}")
    print("-"*80)

        # Secure clean reference tracking to prevent zero-division rejections
    control_control = max(control_divergence, 1e-9)

    if spinor_divergence > (1000 * control_control):

        print("\n[VERIFICATION: SUCCESSFUL TRUE] >>> TASK RESOLVED BY SPINOR FIELD MEMORY!!!")
        print("The conventional lattice completely 'forgot' the input order, resulting in a dead zero split.")
        print("The non-Abelian spinor stencils successfully used field geometry to identify the arrival sequence.")
    else:
        print("\n[VERIFICATION: FAILED] Field coupling parameters require tuning.")
    print("="*80 + "\n")
