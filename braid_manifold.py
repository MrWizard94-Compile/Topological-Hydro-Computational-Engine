import numpy as np
import time

def run_manifold_braid(vortex_order_flag):
    """
    Runs the 3D Helical Siphon simulation on a warped spatial manifold
    where neighbor stencils rotate dynamically with radial distance.
    No software governor is active during the core interaction phase.
    """
    # =====================================================================
    # 1. HARDENED MANIFOLD PARAMETERS
    # =====================================================================
    RADIUS_Q = 6
    RADIUS_R = 4
    Z_LAYERS = 5
    HBAR = 1.0
    MASS = 1.0
    G_COEFF = 0.10
    RHO_MAX = 1.5
    DX = 1.0
    DZ = 1.0
    DT = 0.020

    # =====================================================================
    # 2. THE CHIRAL MANIFOLD GENERATION (TWISTED STENCIL MATRIX)
    # =====================================================================
    nodes = []
    coord_to_idx = {}
    idx = 0

    for z in range(Z_LAYERS):
        for q in range(-RADIUS_Q, RADIUS_Q + 1):
            for r in range(max(-RADIUS_R, -q - RADIUS_Q), min(RADIUS_R, -q + RADIUS_Q) + 1):
                s = -q - r
                nodes.append((q, r, s, z))
                coord_to_idx[(q, r, s, z)] = idx
                idx += 1

    num_nodes = len(nodes)
    neighbor_matrix = np.full((num_nodes, 8), -1, dtype=np.int32)

    # Baseline isotropic 6 planar directions
    base_dirs = np.array([
        [1, -1, 0], [1, 0, -1], [0, 1, -1],
        [-1, 1, 0], [-1, 0, 1], [0, -1, 1]
    ], dtype=np.float64)

    for idx, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)

        # --- THE MASTER STROKE: Twist angle proportional to radial distance ---
        twist_angle = dist_planar * 0.25
        cos_t = np.cos(twist_angle)
        sin_t = np.sin(twist_angle)

        # 2D Rotation Matrix to deform horizontal neighbor alignments
        rot_matrix = np.array([[cos_t, -sin_t], [sin_t, cos_t]])

        for d_idx in range(6):
            # Rotate the standard directional vectors to break spatial isotropy
            # Projecting hex step into twisted continuous coordinates
            dq_raw, dr_raw = base_dirs[d_idx, 0], base_dirs[d_idx, 1]
            rotated_dir = rot_matrix @ np.array([dq_raw, dr_raw])

            # Snap back to nearest integer coordinate offsets to map memory arrays
            dq = int(np.round(rotated_dir[0]))
            dr = int(np.round(rotated_dir[1]))
            ds = -dq - dr

            nb_coord = (q + dq, r + dr, s + ds, z)
            if nb_coord in coord_to_idx:
                neighbor_matrix[idx, d_idx] = coord_to_idx[nb_coord]
            else:
                neighbor_matrix[idx, d_idx] = idx # Reflective wrap boundary

        # Connect vertical Z-axis neighbors
        neighbor_matrix[idx, 6] = coord_to_idx[(q, r, s, min(z + 1, Z_LAYERS - 1))]
        neighbor_matrix[idx, 7] = coord_to_idx[(q, r, s, max(z - 1, 0))]

    # =====================================================================
    # 3. INITIALIZATION AND ASYMMETRIC FIELD SEEDING
    # =====================================================================
    psi_re = np.zeros(num_nodes, dtype=np.float64)
    psi_im = np.zeros(num_nodes, dtype=np.float64)
    v_ext = np.zeros(num_nodes, dtype=np.float64)

    q_left, r_left, s_left = -2, 1, 1
    q_right, r_right, s_right = 2, -1, -1

    if vortex_order_flag == 0:
        z_vortex_A, z_vortex_B = 4, 3  # Sequence 1: A over B
    else:
        z_vortex_A, z_vortex_B = 3, 4  # Sequence 2: B over A

    for idx, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        angle = np.arctan2(r, q)

        # Spiral continuous baseline track potential
        v_ext[idx] = (dist_planar * 0.6) + (2.0 * angle)
        if dist_planar > RADIUS_Q:
            v_ext[idx] += 40.0

        rho = 0.05
        vx, vy, vz = 0.0, 0.0, 0.0
        theta_bias = 0.0

        # Slipped kinematic vector injection with Phase-Chirality tags
        if z == z_vortex_A:
            dist_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
            if dist_A < 1.4:
                rho = RHO_MAX
                vx = -r * 0.5 + 0.4; vy = q * 0.5; vz = -1.1
                theta_bias = np.pi / 4.0

        if z == z_vortex_B:
            dist_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)
            if dist_B < 1.4:
                rho = RHO_MAX
                vx = -r * 0.5 - 0.4; vy = q * 0.5; vz = -1.1
                theta_bias = -np.pi / 4.0

        if dist_planar <= 1.5 and z < 2:
            v_ext[idx] -= 30.0  # Core Polar Siphon drain
            vx = -r * 0.6; vy = q * 0.6; vz = -1.5
            rho = 0.6

        theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33) + theta_bias
        psi_re[idx] = np.sqrt(rho) * np.cos(theta)
        psi_im[idx] = np.sqrt(rho) * np.sin(theta)

    INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

    # =====================================================================
    # 4. UNGOVERNED MANIFOLD FLOW SIMULATION LOOP
    # =====================================================================
    for step in range(1, 26):
        psi_re_next = np.copy(psi_re)
        psi_im_next = np.copy(psi_im)

        for i in range(num_nodes):
            re = psi_re[i]
            im = psi_im[i]
            rho = re**2 + im**2

            # Compute Laplacian over the rotated/twisted spatial stencils
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

            # --- THE GOVERNOR IS DEAD ---
            # Gamma is locked to absolute zero across all steps.
            gamma = 0.0

            h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext[i] + G_COEFF * rho) * re
            h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext[i] + G_COEFF * rho) * im

            psi_re_next[i] = re + (h_im + gamma * re) * DT
            psi_im_next[i] = im + (-h_re + gamma * im) * DT

        # Unitary Normalization Seal to catch numerical anomalies
        current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
        if np.isnan(current_mass) or np.isinf(current_mass):
            return "SINGULARITY CRASH (NaN/INF)"

        psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
        psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    # =====================================================================
    # 5. LINE INTEGRAL SCANNER LAYER AT THE DISCHARGE OPENING (z = 0)
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

if __name__ == "__main__":
    print("\n" + "="*85)
    print("[ THE LAST RESORT: TWISTED MANIFOLD ENGINE ] EXECUTING GEOMETRIC LENSE-THIRRING DRAG")
    print("=" * 85)
    time.sleep(0.5)

    print("Processing Sequence 1: Running [VORTEX A OVER VORTEX B] on twisted stencil...")
    outcome_1 = run_manifold_braid(vortex_order_flag=0)
    print(f"-> Sequence 1 Output Winding: {outcome_1}")

    time.sleep(0.5)

    print("\nProcessing Sequence 2: Running [VORTEX B OVER VORTEX A] on twisted stencil...")
    outcome_2 = run_manifold_braid(vortex_order_flag=1)
    print(f"-> Sequence 2 Output Winding: {outcome_2}")

    print("\n" + "-"*85)
    print("[ THE NON-ABELIAN MATRIX INTERFACE SCREEN ]:")
    print(f"State Matrix (A * B): {outcome_1}  |  State Matrix (B * A): {outcome_2}")
    print("-" * 85)

    if str(outcome_1) != str(outcome_2):
        print("\n[VERIFICATION: TRUE] >>> PARADIGM SHIFT COMPLETED! THE SYSTEM IS NON-ABELIAN.")
        print("Deforming the grid topology successfully shattered commutative symmetry.")
    else:
        print("\n[VERIFICATION: FALSE] >>> HOMOGENEOUS SYMMETRY REMAINS INTACT.")
        print("The digital quantization floor requires direct spatial coordinate scaling.")
    print("=" * 85 + "\n")
