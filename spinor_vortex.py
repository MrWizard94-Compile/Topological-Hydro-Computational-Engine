import numpy as np
import time

def run_spinor_engine(vortex_order_flag):
    # =====================================================================
    # 1. PARAMETERS & SU(2) STABILITY CONSTRAINTS
    # =====================================================================
    RADIUS_Q = 6
    RADIUS_R = 4
    Z_LAYERS = 5
    HBAR = 1.0
    MASS = 1.0
    G_COEFF = 0.08        # Intra-component interaction
    G_CROSS = 0.04        # Inter-component (spin-mixing) non-linear coupling
    RHO_MAX = 1.5
    DX = 0.5
    DZ = 1.0
    DT = 0.010            # Decreased to handle highly coupled spin-orbit oscillations

    V_MAX = (HBAR * np.pi) / (MASS * DX)
    K_STEEPNESS = 0.25
    BASELINE_MU = 5.0

    # =====================================================================
    # 2. 3D HEXAGONAL LATTICE CONFIGURATION
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

    for idx_node, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        twist_angle = dist_planar * 0.15
        cos_t = np.cos(twist_angle); sin_t = np.sin(twist_angle)
        rot_matrix = np.array([[cos_t, -sin_t], [sin_t, cos_t]])

        for d_idx in range(6):
            rotated_dir = rot_matrix @ base_dirs[d_idx, :2]
            dq, dr = int(np.round(rotated_dir[0])), int(np.round(rotated_dir[1]))
            ds = -dq - dr

            nb_coord = (q + dq, r + dr, s + ds, z)
            if nb_coord in coord_to_idx:
                neighbor_matrix[idx_node, d_idx] = coord_to_idx[nb_coord]
            else:
                neighbor_matrix[idx_node, d_idx] = idx_node

        neighbor_matrix[idx_node, 6] = coord_to_idx[(q, r, s, min(z + 1, Z_LAYERS - 1))]
        neighbor_matrix[idx_node, 7] = coord_to_idx[(q, r, s, max(z - 1, 0))]

    # =====================================================================
    # 3. MEMORY ALLOCATION: DOUBLE-COMPONENT SPINOR STATE VECTORS
    # =====================================================================
    # Component 1: Spin-Up Wavefunction Registers
    psi_u_re = np.zeros(num_nodes, dtype=np.float64)
    psi_u_im = np.zeros(num_nodes, dtype=np.float64)

    # Component 2: Spin-Down Wavefunction Registers
    psi_d_re = np.zeros(num_nodes, dtype=np.float64)
    psi_d_im = np.zeros(num_nodes, dtype=np.float64)

    v_ext = np.zeros(num_nodes, dtype=np.float64)

    # Non-Abelian Gauge Fields (Spatially varying vector potentials)
    Ax = np.zeros(num_nodes, dtype=np.float64)
    Ay = np.zeros(num_nodes, dtype=np.float64)

    q_left, r_left, s_left = -3, 1, 2
    q_right, r_right, s_right = 3, -1, -2

    if vortex_order_flag == 0:
        z_vortex_A, z_vortex_B = 4, 3
    else:
        z_vortex_A, z_vortex_B = 3, 4

    for idx_node, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        angle = np.arctan2(r, q)

        v_ext[idx_node] = (dist_planar * 0.5) + (1.5 * angle)
        if dist_planar > RADIUS_Q:
            v_ext[idx_node] += 40.0

        # Initialize the non-Abelian Gauge Field configuration
        if dist_planar > 0.1:
            Ax[idx_node] = -r / (dist_planar**2)
            Ay[idx_node] = q / (dist_planar**2)

        rho = 0.05
        vx, vy, vz = 0.0, 0.0, 0.0

        # Inject Vortex A primarily into the SPIN-UP state component
        if z == z_vortex_A:
            dist_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
            if dist_A < 1.4:
                rho = RHO_MAX; vx = -r * 0.4 + 0.3; vy = q * 0.4; vz = -1.1
                theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33)
                psi_u_re[idx_node] = np.sqrt(rho) * np.cos(theta + np.pi/4)
                psi_u_im[idx_node] = np.sqrt(rho) * np.sin(theta + np.pi/4)
                continue

        # Inject Vortex B primarily into the SPIN-DOWN state component
        if z == z_vortex_B:
            dist_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)
            if dist_B < 1.4:
                rho = RHO_MAX; vx = -r * 0.4 - 0.3; vy = q * 0.4; vz = -1.2
                theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33)
                psi_d_re[idx_node] = np.sqrt(rho) * np.cos(theta - np.pi/4)
                psi_d_im[idx_node] = np.sqrt(rho) * np.sin(theta - np.pi/4)
                continue

        # Base Siphon Core Setup
        if dist_planar <= 1.5 and z < 2:
            v_ext[idx_node] -= 30.0
            vx = -r * 0.6; vy = q * 0.6; vz = -1.5; rho = 0.6
            theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33)
            psi_u_re[idx_node] = np.sqrt(rho/2) * np.cos(theta)
            psi_u_im[idx_node] = np.sqrt(rho/2) * np.sin(theta)
            psi_d_re[idx_node] = np.sqrt(rho/2) * np.cos(theta)
            psi_d_im[idx_node] = np.sqrt(rho/2) * np.sin(theta)

    INITIAL_MASS = np.sum(psi_u_re**2 + psi_u_im**2 + psi_d_re**2 + psi_d_im**2)

    # =====================================================================
    # 4. VECTORIZED SU(2) SPIN-ORBIT COUPLED SIMULATION LOOP
    # =====================================================================
    for step in range(1, 31):
        # Slice neighbor states for both components simultaneously
        u_re_nb = psi_u_re[neighbor_matrix[:, :6]]
        u_im_nb = psi_u_im[neighbor_matrix[:, :6]]
        d_re_nb = psi_d_re[neighbor_matrix[:, :6]]
        d_im_nb = psi_d_im[neighbor_matrix[:, :6]]

        # 3D Laplacian computations for Spin-Up component
        lap_u_re_p = np.sum(u_re_nb, axis=1) - 6.0 * psi_u_re
        lap_u_im_p = np.sum(u_im_nb, axis=1) - 6.0 * psi_u_im
        lap_u_re_v = (psi_u_re[neighbor_matrix[:, 6]] - 2.0 * psi_u_re + psi_u_re[neighbor_matrix[:, 7]])
        lap_u_im_v = (psi_u_im[neighbor_matrix[:, 6]] - 2.0 * psi_u_im + psi_u_im[neighbor_matrix[:, 7]])
        lap_u_re = (lap_u_re_p * (2.0 / (3.0 * DX**2))) + lap_u_re_v
        lap_u_im = (lap_u_im_p * (2.0 / (3.0 * DX**2))) + lap_u_im_v

        # 3D Laplacian computations for Spin-Down component
        lap_d_re_p = np.sum(d_re_nb, axis=1) - 6.0 * psi_d_re
        lap_d_im_p = np.sum(d_im_nb, axis=1) - 6.0 * psi_d_im
        lap_d_re_v = (psi_d_re[neighbor_matrix[:, 6]] - 2.0 * psi_d_re + psi_d_re[neighbor_matrix[:, 7]])
        lap_d_im_v = (psi_d_im[neighbor_matrix[:, 6]] - 2.0 * psi_d_im + psi_d_im[neighbor_matrix[:, 7]])
        lap_d_re = (lap_d_re_p * (2.0 / (3.0 * DX**2))) + lap_d_re_v
        lap_d_im = (lap_d_im_p * (2.0 / (3.0 * DX**2))) + lap_d_im_v

        # Local densities
        rho_u = psi_u_re**2 + psi_u_im**2
        rho_d = psi_d_re**2 + psi_d_im**2
        rho_total = rho_u + rho_d

        # Calculate localized velocity fields via phase gradient
        nb_p = neighbor_matrix[:, 0]
        vel_u = np.abs(np.arctan2(psi_u_im[nb_p], psi_u_re[nb_p]) - np.arctan2(psi_u_im, psi_u_re)) / DX
        vel_d = np.abs(np.arctan2(psi_d_im[nb_p], psi_d_re[nb_p]) - np.arctan2(psi_d_im, psi_d_re)) / DX
        vel_max_field = np.maximum(vel_u, vel_d)
        vel_max_field = np.clip(vel_max_field, 0.0, 0.999 * V_MAX)

        # Dynamic governor dampening field
        gamma = np.zeros(num_nodes)
        gov_mask = vel_max_field > (0.6 * V_MAX)
        gamma[gov_mask] = BASELINE_MU * np.exp((K_STEEPNESS * vel_max_field[gov_mask]) / ((V_MAX - vel_max_field[gov_mask]) + 1e-7))

        # --- THE SU(2) TRANSISTOR ENGINE CORE: Non-Abelian Spin-Orbit Cross-Talk ---
        # The gauge fields Ax and Ay operate directly as Pauli matrix components,
        # cross-multiplying and mixing the real and imaginary components of Up and Down states.
        soc_u_re = -(Ax * psi_d_im + Ay * psi_d_re)
        soc_u_im = (Ax * psi_d_re - Ay * psi_d_im)
        soc_d_re = -(Ax * psi_u_im - Ay * psi_u_re)
        soc_d_im = (Ax * psi_u_re + Ay * psi_u_im)

        # Base Coupled Nonlinear Schrödinger Hamiltonians
        h_u_re = -(HBAR**2 / (2 * MASS)) * lap_u_re + (v_ext + G_COEFF * rho_u + G_CROSS * rho_d) * psi_u_re + soc_u_re
        h_u_im = -(HBAR**2 / (2 * MASS)) * lap_u_im + (v_ext + G_COEFF * rho_u + G_CROSS * rho_d) * psi_u_im + soc_u_im
        h_d_re = -(HBAR**2 / (2 * MASS)) * lap_d_re + (v_ext + G_COEFF * rho_d + G_CROSS * rho_u) * psi_d_re + soc_d_re
        h_d_im = -(HBAR**2 / (2 * MASS)) * lap_d_im + (v_ext + G_COEFF * rho_d + G_CROSS * rho_u) * psi_d_im + soc_d_im

        # Simultaneous system time evolution update step
        psi_u_re_next = psi_u_re + (h_u_im + gamma * psi_u_re) * DT
        psi_u_im_next = psi_u_im + (-h_u_re + gamma * psi_u_im) * DT
        psi_d_re_next = psi_d_re + (h_d_im + gamma * psi_d_re) * DT
        psi_d_im_next = psi_d_im + (-h_d_re + gamma * psi_d_im) * DT

        # Secure Unitary Conservation across the total dual-spin matrix space
        current_mass = np.sum(psi_u_re_next**2 + psi_u_im_next**2 + psi_d_re_next**2 + psi_d_im_next**2)
        if np.isnan(current_mass) or np.isinf(current_mass): return 0.0
        norm = np.sqrt(INITIAL_MASS / current_mass)

        psi_u_re, psi_u_im = psi_u_re_next * norm, psi_u_im_next * norm
        psi_d_re, psi_d_im = psi_d_re_next * norm, psi_d_im_next * norm

    # =====================================================================
    # 5. UNMASKED COMPILER INTERFEROMETER READOUT AT SIPHON EXIT (z = 0)
    # =====================================================================
    # Scan the exit ring metrics on the base layer
    exit_ring = [(1, -1, 0, 0), (0, -1, 1, 0), (-1, 0, 1, 0), (-1, 1, 0, 0), (0, 1, -1, 0), (1, 0, -1, 0)]
    exit_indices = [coord_to_idx[c] for c in exit_ring]
    total_exit_phase = 0.0

    for idx_cnt in range(6):
        idx_c = exit_indices[idx_cnt]
        idx_n = exit_indices[(idx_cnt + 1) % 6]

        # Extract the emergent spin-coherent phase angle by combining both components
        t_c = np.arctan2(psi_u_im[idx_c] + psi_d_im[idx_c], psi_u_re[idx_c] + psi_d_re[idx_c])
        t_n = np.arctan2(psi_u_im[idx_n] + psi_d_im[idx_n], psi_u_re[idx_n] + psi_d_re[idx_n])

        d_t = t_n - t_c
        if d_t > np.pi:
            d_t -= 2.0 * np.pi
        elif d_t < -np.pi:
            d_t += 2.0 * np.pi
        total_exit_phase += d_t

    return total_exit_phase / (2.0 * np.pi)
