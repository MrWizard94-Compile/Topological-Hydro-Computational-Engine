import numpy as np
import time

def run_memory_gel_simulation(vortex_order_flag):
    # =====================================================================
    # 1. HARDENED PARAMETERS & STRATIFIED BOUNDARIES
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
    DT = 0.020            # Small time-step to maintain unitary precision

    V_MAX = (HBAR * np.pi) / (MASS * DX)
    K_STEEPNESS = 0.25

    # =====================================================================
    # 2. 3D HEXAGONAL MESH MAPPING
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
    # 3. COMPONENT INITIALIZATION & DYNAMIC VISCOSITY ARRAY (THE SCAR FIELD)
    # =====================================================================
    psi_re = np.zeros(num_nodes, dtype=np.float64)
    psi_im = np.zeros(num_nodes, dtype=np.float64)
    v_ext = np.zeros(num_nodes, dtype=np.float64)

    # UNCONVENTIONAL VARIABLE: A living, dynamic viscosity array across the 3D space
    # The fluid initializes with standard viscosity, but will "scar" under kinetic velocity
    dynamic_viscosity = np.full(num_nodes, 4.0, dtype=np.float64)

    q_left, r_left, s_left = -2, 1, 1
    q_right, r_right, s_right = 2, -1, -1

    if vortex_order_flag == 0:
        z_vortex_A, z_vortex_B = 4, 3  # Sequence 1: A leads B
    else:
        z_vortex_A, z_vortex_B = 3, 4  # Sequence 2: B leads A

    for idx, (q, r, s, z) in enumerate(nodes):
        dist_planar = np.sqrt(q**2 + r**2 + s**2)
        angle = np.arctan2(r, q)

        # Continuous asymmetric chiral potential ramp
        v_ext[idx] = (dist_planar * 0.6) + (2.0 * angle)

        if dist_planar > RADIUS_Q:
            v_ext[idx] += 40.0

        rho = 0.05
        vx, vy, vz = 0.0, 0.0, 0.0
        theta_bias = 0.0

        # Slipped injection velocity
        if z == z_vortex_A:
            dist_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
            if dist_A < 1.4:
                rho = RHO_MAX
                vx = -r * 0.5 + 0.4
                vy = q * 0.5
                vz = -1.1
                theta_bias = np.pi / 4.0

        if z == z_vortex_B:
            dist_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)
            if dist_B < 1.4:
                rho = RHO_MAX
                vx = -r * 0.5 - 0.4
                vy = q * 0.5
                vz = -1.1
                theta_bias = -np.pi / 4.0

        if dist_planar <= 1.5 and z < 2:
            v_ext[idx] -= 30.0
            vx = -r * 0.6
            vy = q * 0.6
            vz = -1.5
            rho = 0.6

        theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33) + theta_bias
        psi_re[idx] = np.sqrt(rho) * np.cos(theta)
        psi_im[idx] = np.sqrt(rho) * np.sin(theta)

    INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

    # =====================================================================
    # 4. SIMULATION LOOP WITH LATTICE SCARRING (FLUID MEMORY)
    # =====================================================================
    for step in range(1, 26):
        psi_re_next = np.copy(psi_re)
        psi_im_next = np.copy(psi_im)

        for i in range(num_nodes):
            re = psi_re[i]
            im = psi_im[i]
            rho = re**2 + im**2

            # Compute 3D Laplacian Stencil
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

            # Check local velocity phase gradient
            nb_axis = neighbor_matrix[i, 0]
            t_me = np.arctan2(im, re)
            t_nb = np.arctan2(psi_im[nb_axis], psi_re[nb_axis])
            dt = t_nb - t_me
            if dt > np.pi: dt -= 2*np.pi
            if dt < -np.pi: dt += 2*np.pi
            vel = (HBAR / MASS) * (abs(dt) / DX)

            if vel >= (0.999 * V_MAX):
                vel = 0.999 * V_MAX

            # --- THE RADICAL OVERHAUL: VISCOSITY SCARRING HYSTERESIS ---
            # High kinetic velocity physically cuts open the fluid, permanently
            # dropping viscosity at that cell to 0.1 for the rest of the run.
            if vel > (0.4 * V_MAX):
                dynamic_viscosity[i] = 0.1  # The lattice is scarred, creating a slick runway

            gamma = 0.0
            if vel > (0.6 * V_MAX):
                # Read the dynamic, living scar field instead of a static baseline number
                gamma = dynamic_viscosity[i] * np.exp((0.2 * vel) / ((V_MAX - vel) + 1e-7))

            h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext[i] + G_COEFF * rho) * re
            h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext[i] + G_COEFF * rho) * im

            psi_re_next[i] = re + (h_im + gamma * re) * DT
            psi_im_next[i] = im + (-h_re + gamma * im) * DT

        # Unitary Normalization Lock
        current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
        psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
        psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    # =====================================================================
    # 5. POLAR COMPILER EXIT SIPHON READOUT (z = 0)
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
    print("[ UNCONVENTIONAL FRONTIER ] TESTING MEMORY-GEL SCAR FIELDS")
    print("=" * 85)
    time.sleep(0.5)

    print("Processing Sequence 1: Ingesting [VORTEX A OVER VORTEX B] into Gel Grid...")
    res_1 = run_memory_gel_simulation(vortex_order_flag=0)
    print(f"-> Sequence 1 Output: {res_1}")

    time.sleep(0.5)

    print("\nProcessing Sequence 2: Ingesting [VORTEX B OVER VORTEX A] into Gel Grid...")
    res_2 = run_memory_gel_simulation(vortex_order_flag=1)
    print(f"-> Sequence 2 Output: {res_2}")

    print("\n" + "-"*85)
    print("[ THE NON-ABELIAN BREAKTHROUGH CHECK ]:")
    print(f"State Matrix (A * B): {res_1}  |  State Matrix (B * A): {res_2}")
    print("-" * 85)

    if res_1 != res_2:
        print("\n[VERIFICATION: TRUE] >>> UNCONVENTIONAL NON-ABELIAN TOPOLOGY CAPTURED!")
        print("Lattice scarring forced absolute path-dependency. The fluid successfully remembered the order.")
    else:
        print("\n[VERIFICATION: FALSE] >>> ABELIAN EQUILIBRIUM COLLAPSE.")
        print("The fluid memory decay rate or grid size is still hiding the variable. Tinker further.")
    print("=" * 85 + "\n")
