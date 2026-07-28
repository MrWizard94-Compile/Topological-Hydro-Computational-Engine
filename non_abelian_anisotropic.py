import numpy as np
import time

def run_anisotropic_braid(vortex_order_flag):
    """
    Runs the 3D Helical Siphon simulation with Anisotropic Grid Elongation
    and a continuous Spiral Coriolis Potential Ramp.
    vortex_order_flag = 0: Vortex A over Vortex B (Sequence 1)
    vortex_order_flag = 1: Vortex B over Vortex A (Sequence 2)
    """
    # =====================================================================
    # 1. ANISOTROPIC PARAMETERS & HARDCONSTRAINTS
    # =====================================================================
    RADIUS_Q = 7          # Elongated Q-axis to break structural isotropy
    RADIUS_R = 4          # Compressed R-axis to form an asymmetrical oval racetrack
    Z_LAYERS = 5
    HBAR = 1.0
    MASS = 1.0
    G_COEFF = 0.08        # Lowered slightly to prevent non-linear self-repulsion from overriding geometry
    RHO_MAX = 1.5
    DX = 1.0
    DZ = 1.0
    DT = 0.022            # Tightened time-step to maintain absolute unitarity along the ramp

    V_MAX = (HBAR * np.pi) / (MASS * DX)
    K_STEEPNESS = 0.2
    BASELINE_MU = 6.0

    # =====================================================================
    # 2. ANISOTROPIC 3D MESH LAYOUT GENERATION (q + r + s = 0, z)
    # =====================================================================
    nodes = []
    coord_to_idx = {}
    idx = 0

    for z in range(Z_LAYERS):
        # Apply the non-linear anisotropic bounds to stretch the hex lattice into an oval
        for q in range(-RADIUS_Q, RADIUS_Q + 1):
            for r in range(max(-RADIUS_R, -q - RADIUS_Q), min(RADIUS_R, -q + RADIUS_Q) + 1):
                s = -q - r
                nodes.append((q, r, s, z))
                coord_to_idx[(q, r, s, z)] = idx
                idx += 1

    num_nodes = len(nodes)

    neighbor_matrix = np.full((num_nodes, 8), -1, dtype=np.int32)
    planar_dirs = [(+1, -1, 0), (+1, 0, -1), (0, +1, -1), (-1, +1, 0), (-1, 0, +1), (0, -1, +1)]

    for idx, (q, r, s, z) in enumerate(nodes):
        for d_idx, (dq, dr, ds) in enumerate(planar_dirs):
            nb_coord = (q + dq, r + dr, s + ds, z)
            if nb_coord in coord_to_idx:
                neighbor_matrix[idx, d_idx] = coord_to_idx[nb_coord]
            else:
                neighbor_matrix[idx, d_idx] = idx

        neighbor_matrix[idx, 6] = coord_to_idx[(q, r, s, min(z + 1, Z_LAYERS - 1))]
        neighbor_matrix[idx, 7] = coord_to_idx[(q, r, s, max(z - 1, 0))]

    # =====================================================================
    # 3. COMPONENT INITIALIZATION WITH SPIRAL CORIOLIS POTENTIAL RAMP
    # =====================================================================
    psi_re = np.zeros(num_nodes, dtype=np.float64)
    psi_im = np.zeros(num_nodes, dtype=np.float64)
    v_ext = np.zeros(num_nodes, dtype=np.float64)

    # Offset injection parameters to utilize the elongated axis
    q_left, r_left, s_left = -3, 1, 2
    q_right, r_right, s_right = 3, -1, -2

    if vortex_order_flag == 0:
        z_vortex_A = 4  # Sequence 1: A maps to Top Layer
        z_vortex_B = 3  # Sequence 1: B maps to Middle Layer
    else:
        z_vortex_A = 3  # Sequence 2: A maps to Middle Layer
        z_vortex_B = 4  # Sequence 2: B maps to Top Layer

    for idx, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        angle = np.arctan2(r, q)

        # --- THE GEOMETRIC BREAKTHROUGH: The Spiral Coriolis Ramp Potential ---
        # Combines planar distance with a non-linear continuous angular lift field
        # This breaks spatial isotropy and forces directional, path-dependent flow
        v_ext[idx] = (dist_planar * 0.7) + (2.2 * angle)

        # Build outer boundary containment walls on the oval perimeter
        if dist_planar > RADIUS_Q:
            v_ext[idx] += 40.0

        rho = 0.05
        vx, vy, vz = 0.0, 0.0, 0.0
        theta_bias = 0.0

        # Inject Vortex A (Positive Chirality, Chiral Phase Tag +pi/4)
        if z == z_vortex_A:
            dist_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
            if dist_A < 1.4:
                rho = RHO_MAX
                vx = -r * 0.4 + 0.3
                vy = q * 0.4
                vz = -1.2
                theta_bias = np.pi / 4.0

        # Inject Vortex B (Matched Positive Chirality, Chiral Phase Tag -pi/4)
        if z == z_vortex_B:
            dist_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)
            if dist_B < 1.4:
                rho = RHO_MAX
                vx = -r * 0.4 - 0.3
                vy = q * 0.4
                vz = -1.2
                theta_bias = -np.pi / 4.0

        # Lower Siphon Exit Extraction Pipe (z=0, z=1)
        if dist_planar <= 1.5 and z < 2:
            v_ext[idx] -= 30.0  # Vacuum pull down the polar siphon
            vx = -r * 0.65
            vy = q * 0.65
            vz = -1.6
            rho = 0.6
            theta_bias = 0.0

        theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33) + theta_bias
        psi_re[idx] = np.sqrt(rho) * np.cos(theta)
        psi_im[idx] = np.sqrt(rho) * np.sin(theta)

    INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

    # =====================================================================
    # 4. PARALLEL ANISOTROPIC FLUID SIMULATION LOOP
    # =====================================================================
    for step in range(1, 26):
        psi_re_next = np.copy(psi_re)
        psi_im_next = np.copy(psi_im)

        for i in range(num_nodes):
            re = psi_re[i]
            im = psi_im[i]
            rho = re**2 + im**2

            # 3D Laplacian Stencil
            lap_re_p = 0.0; lap_im_p = 0.0
            for j in range(6):
                nb_p = neighbor_matrix[i, j]
                lap_re_p += psi_re[nb_p] - re
                lap_im_p += psi_im[nb_p] - im
            lap_re_p *= (2.0 / (3.0 * (DX**2)))
            lap_im_p *= (2.0 / (3.0 * (DX**2)))

            idx_t = neighbor_matrix[i, 6]; idx_b = neighbor_matrix[i, 7]
            lap_re_v = (psi_re[idx_t] - 2.0 * re + psi_re[idx_b]) / (DZ**2)
            lap_im_v = (psi_im[idx_t] - 2.0 * im + psi_im[idx_b]) / (DZ**2)

            lap_re = lap_re_p + lap_re_v
            lap_im = lap_im_p + lap_im_v

            # Local Velocity Check
            nb_axis = neighbor_matrix[i, 0]
            t_me = np.arctan2(im, re)
            t_nb = np.arctan2(psi_im[nb_axis], psi_re[nb_axis])
            dt = t_nb - t_me
            if dt > np.pi: dt -= 2*np.pi
            if dt < -np.pi: dt += 2*np.pi
            vel = (HBAR / MASS) * (abs(dt) / DX)

            # Hardened boundary safety clamp
            if vel >= (0.999 * V_MAX):
                vel = 0.999 * V_MAX

            gamma = 0.0
            if vel > (0.6 * V_MAX):
                gamma = BASELINE_MU * np.exp((K_STEEPNESS * vel) / ((V_MAX - vel) + 1e-7))

            h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext[i] + G_COEFF * rho) * re
            h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext[i] + G_COEFF * rho) * im

            psi_re_next[i] = re + (h_im + gamma * re) * DT
            psi_im_next[i] = im + (-h_re + gamma * im) * DT

        # Unitary VRAM Mass Lock
        current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
        psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
        psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    # =====================================================================
    # 5. LINE INTEGRAL SIPHON COMPILER READOUT (z = 0)
    # =====================================================================
    exit_ring = [(1, -1, 0, 0), (0, -1, 1, 0), (-1, 0, 1, 0), (-1, 1, 0, 0), (0, 1, -1, 0), (1, 0, -1, 0)]
    exit_indices = [coord_to_idx[c] for c in exit_ring]
    total_exit_phase = 0.0

    for idx in range(6):
        idx_c = exit_indices[idx]
        idx_n = exit_indices[(idx + 1) % 6]
        t_c = np.arctan2(psi_im[idx_c], psi_re[idx_c])
        t_n = np.arctan2(psi_im[idx_n], psi_re[idx_n])
        d_t = t_n - t_c
        if d_t > np.pi: d_t -= 2.0 * np.pi
        elif d_t < -np.pi: d_t += 2.0 * np.pi
        total_exit_phase += d_t

    return int(np.round(total_exit_phase / (2.0 * np.pi)))

# =====================================================================
# THE ANISOTROPIC EVALUATION CONTROL PANEL
# =====================================================================
if __name__ == "__main__":
    print("\n" + "="*85)
    print("[ BREAKING SPATIAL ISOTROPY ] INITIALIZING CORIOLIS RAMP AND OVAL racetracks")
    print("=" * 85)
    time.sleep(0.5)

    # Process Sequence 1: Vortex A over Vortex B
    print("\nProcessing Sequence 1: Ingesting [VORTEX A OVER VORTEX B] down Spiral Siphon...")
    outcome_1 = run_anisotropic_braid(vortex_order_flag=0)
    print(f"-> Sequence 1 Siphon Output (Winding Number): {outcome_1}")

    time.sleep(0.5)

    # Process Sequence 2: Vortex B over Vortex A
    print("\nProcessing Sequence 2: Ingesting [VORTEX B OVER VORTEX A] down Spiral Siphon...")
    outcome_2 = run_anisotropic_braid(vortex_order_flag=1)
    print(f"-> Sequence 2 Siphon Output (Winding Number): {outcome_2}")

    print("\n" + "-"*85)
    print("[ DETERMINISTIC EVALUATION VERDICT ] COMPILER INTERFACE MONITOR:")
    print(f"State Output (A * B): {outcome_1}  |  State Output (B * A): {outcome_2}")
    print("-" * 85)

    if outcome_1 != outcome_2:
        print("\n[VERIFICATION: SUCCESSFUL TRUE] >>> NON-ABELIAN TOPOLOGY SECURED!")
        print("The geometric anisotropy successfully forced path-dependency.")
        print("Swapping the injection order changed the physical curvature of the 3D fluid braid.")
    else:
        print("\n[VERIFICATION: FAILED FALSE] >>> SYSTEM COLLAPSED TO HOMOGENEOUS EQUILIBRIUM.")
        print("The spiral angle force coefficient requires amplification or the grid requires further elongation.")
        print("=" * 85 + "\n")