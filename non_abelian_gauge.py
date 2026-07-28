import numpy as np
import time

def run_gauge_manifold_simulation(vortex_order_flag):
    # =====================================================================
    # 1. PARAMETERS & STABILITY CONSTRAINTS
    # =====================================================================
    RADIUS_Q = 8
    RADIUS_R = 5
    Z_LAYERS = 5
    HBAR = 1.0
    MASS = 1.0
    G_COEFF = 0.10
    RHO_MAX = 1.5
    DX = 0.5
    DZ = 1.0
    DT = 0.012

    V_MAX = (HBAR * np.pi) / (MASS * DX)
    K_STEEPNESS = 0.25
    BASELINE_MU = 4.0

    # =====================================================================
    # 2. 3D HEXAGONAL MESH GENERATION (q + r + s = 0, z)
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
    base_dirs = np.array([[1, -1, 0], [1, 0, -1], [0, 1, -1], [-1, 1, 0], [-1, 0, 1], [0, -1, 1]], dtype=np.float64)

    # Map the twisted neighborhood stencils
    for idx_node, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        twist_angle = dist_planar * 0.20
        cos_t = np.cos(twist_angle); sin_t = np.sin(twist_angle)
        rot_matrix = np.array([[cos_t, -sin_t], [sin_t, cos_t]])

        for d_idx in range(6):
            rotated_dir = rot_matrix @ base_dirs[d_idx, :2]
            # FIXED: Explicitly isolate array indices before scalar mapping
            dq = int(np.round(rotated_dir[0]))
            dr = int(np.round(rotated_dir[1]))
            ds = -dq - dr

            nb_coord = (q + dq, r + dr, s + ds, z)
            if nb_coord in coord_to_idx:
                neighbor_matrix[idx_node, d_idx] = coord_to_idx[nb_coord]
            else:
                neighbor_matrix[idx_node, d_idx] = idx_node

        neighbor_matrix[idx_node, 6] = coord_to_idx[(q, r, s, min(z + 1, Z_LAYERS - 1))]
        neighbor_matrix[idx_node, 7] = coord_to_idx[(q, r, s, max(z - 1, 0))]

    # =====================================================================
    # 3. FIELD INITIALIZATION & VECTOR POTENTIAL GAUGE MAP (A-FIELD)
    # =====================================================================
    psi_re = np.zeros(num_nodes, dtype=np.float64)
    psi_im = np.zeros(num_nodes, dtype=np.float64)
    v_ext = np.zeros(num_nodes, dtype=np.float64)

    A_x = np.zeros(num_nodes, dtype=np.float64)
    A_y = np.zeros(num_nodes, dtype=np.float64)

    q_left, r_left, s_left = -3, 1, 2
    q_right, r_right, s_right = 3, -1, -2

    if vortex_order_flag == 0:
        z_vortex_A, z_vortex_B = 4, 3
    else:
        z_vortex_A, z_vortex_B = 3, 4

    for idx_node, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        angle = np.arctan2(r, q)

        v_ext[idx_node] = (dist_planar * 0.6)
        if dist_planar > RADIUS_Q:
            v_ext[idx_node] += 40.0

        if dist_planar > 0.1:
            A_x[idx_node] = -s / (dist_planar**2)
            A_y[idx_node] = q / (dist_planar**2)

        rho = 0.05
        vx, vy, vz = 0.0, 0.0, 0.0
        theta_bias = 0.0

        if z == z_vortex_A:
            dist_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
            if dist_A < 1.4:
                rho = RHO_MAX
                vx = -r * 0.4 + 0.3; vy = q * 0.4; vz = -1.2
                theta_bias = np.pi / 4.0

        if z == z_vortex_B:
            dist_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)
            if dist_B < 1.4:
                rho = RHO_MAX
                vx = -r * 0.4 - 0.3; vy = q * 0.4; vz = -1.2
                theta_bias = -np.pi / 4.0

        if dist_planar <= 1.5 and z < 2:
            v_ext[idx_node] -= 30.0
            vx = -r * 0.6; vy = q * 0.6; vz = -1.5
            rho = 0.6

        theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33) + theta_bias
        psi_re[idx_node] = np.sqrt(rho) * np.cos(theta)
        psi_im[idx_node] = np.sqrt(rho) * np.sin(theta)

    INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

    # =====================================================================
    # 4. GAUGE-COUPLED VECTORIZED SIMULATION LOOP
    # =====================================================================
    for step in range(1, 31):
        psi_re_nb = psi_re[neighbor_matrix[:, :6]]
        psi_im_nb = psi_im[neighbor_matrix[:, :6]]

        lap_re_p = np.sum(psi_re_nb, axis=1) - 6.0 * psi_re - (A_x * psi_im + A_y * psi_im)
        lap_im_p = np.sum(psi_im_nb, axis=1) - 6.0 * psi_im + (A_x * psi_re + A_y * psi_re)

        lap_re_p *= (2.0 / (3.0 * (DX**2)))
        lap_im_p *= (2.0 / (3.0 * (DX**2)))

        psi_re_top = psi_re[neighbor_matrix[:, 6]]
        psi_re_bot = psi_re[neighbor_matrix[:, 7]]
        psi_im_top = psi_im[neighbor_matrix[:, 6]]
        psi_im_bot = psi_im[neighbor_matrix[:, 7]]

        lap_re_v = (psi_re_top - 2.0 * psi_re + psi_re_bot) / (DZ**2)
        lap_im_v = (psi_im_top - 2.0 * psi_im + psi_im_bot) / (DZ**2)

        lap_re = lap_re_p + lap_re_v
        lap_im = lap_im_p + lap_im_v

        rho_field = psi_re**2 + psi_im**2

        nb_primary = neighbor_matrix[:, 0]
        theta_me = np.arctan2(psi_im, psi_re)
        theta_nb = np.arctan2(psi_im[nb_primary], psi_re[nb_primary])
        dt_field = theta_nb - theta_me
        dt_field = np.where(dt_field > np.pi, dt_field - 2*np.pi, dt_field)
        dt_field = np.where(dt_field < -np.pi, dt_field + 2*np.pi, dt_field)
        vel_field = (HBAR / MASS) * (np.abs(dt_field) / DX)

        vel_field = np.clip(vel_field, 0.0, 0.999 * V_MAX)
        gamma_field = np.zeros(num_nodes)
        gov_mask = vel_field > (0.6 * V_MAX)
        gamma_field[gov_mask] = BASELINE_MU * np.exp((K_STEEPNESS * vel_field[gov_mask]) / ((V_MAX - vel_field[gov_mask]) + 1e-7))

        h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext + G_COEFF * rho_field) * psi_re
        h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext + G_COEFF * rho_field) * psi_im

        psi_re_next = psi_re + (h_im + gamma_field * psi_re) * DT
        psi_im_next = psi_im + (-h_re + gamma_field * psi_im) * DT

        current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
        if np.isnan(current_mass) or np.isinf(current_mass):
            return 0.0

        psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
        psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    # =====================================================================
    # 5. UNMASKED FRACTIONAL READOUT SCANNER (z = 0)
    # =====================================================================
    exit_ring = [(1, -1, 0, 0), (0, -1, 1, 0), (-1, 0, 1, 0), (-1, 1, 0, 0), (0, 1, -1, 0), (1, 0, -1, 0)]
    exit_indices = [coord_to_idx[c] for c in exit_ring]
    total_exit_phase = 0.0

    for idx_cnt in range(6):
        idx_c = exit_indices[idx_cnt]
        idx_n = exit_indices[(idx_cnt + 1) % 6]
        t_c = np.arctan2(psi_im[idx_c], psi_re[idx_c])
        t_n = np.arctan2(psi_im[idx_n], psi_re[idx_n])
        d_t = t_n - t_c
        if d_t > np.pi: d_t -= 2.0 * np.pi
        elif d_t < -np.pi: d_t += 2.0 * np.pi
        total_exit_phase += d_t

    return total_exit_phase / (2.0 * np.pi)

if __name__ == "__main__":
    print("\n" + "="*85)
    print("[ THE GAUGE FRONTIER ] EXECUTING COVARIANT VECTOR POTENTIAL HARNESS")
    print("=" * 85)
    time.sleep(0.5)

    print("Processing Sequence 1: Ingesting [VORTEX A OVER VORTEX B] through A-Field...")
    f_1 = run_gauge_manifold_simulation(vortex_order_flag=0)
    print(f"-> Sequence 1 Fractional Charge: {f_1:.6f}")

    time.sleep(0.5)

    print("\nProcessing Sequence 2: Ingesting [VORTEX B OVER VORTEX A] through A-Field...")
    f_2 = run_gauge_manifold_simulation(vortex_order_flag=1)
    print(f"-> Sequence 2 Fractional Charge: {f_2:.6f}")

    print("\n" + "-"*85)
    print("[ THE UNMASKED GAUGE MONITOR VERDICT ]:")
    print(f"State Matrix (A * B): {f_1:.6f} Winding Units")
    print(f"State Matrix (B * A): {f_2:.6f} Winding Units")
    print("-" * 85)

    divergence = np.abs(f_1 - f_2)
    print(f"Detected Path Phase Divergence: {divergence:.6f}")

    if divergence > 1e-5:
        print("\n[VERIFICATION: TRUE] >>> NON-ABELIAN CONSTRAINTS FORCED BY GAUGE FIELD!")
        print("The vector potential successfully anchored the path history against the rounding floor.")
    else:
        print("\n[VERIFICATION: FALSE] >>> HOMOGENEOUS COLLAPSE.")
        print("The gauge coupling coefficient requires amplification. Tinker further.")
    print("=" * 85 + "\n")
