import numpy as np
import time

# =====================================================================
# 1. 3D PARAMETERS & HARDCONSTRAINTS
# =====================================================================
RADIUS = 4            # Planar radius
Z_LAYERS = 3          # Phase 3 Expansion: 3 vertical layers stacked along Z
HBAR = 1.0
MASS = 1.0
G_COEFF = 0.10
RHO_MAX = 1.5
DX = 1.0
DZ = 1.0              # Vertical grid spacing
DT = 0.03             # Decreased to handle highly coupled 3D discrete Laplacian steps

V_MAX = (HBAR * np.pi) / (MASS * DX)
K_STEEPNESS = 0.2
BASELINE_MU = 6.0

# =====================================================================
# 2. 3D HEXAGONAL-VERTICAL LATTICE INDEX GENERATION (q+r+s=0, z)
# =====================================================================
nodes = []
coord_to_idx = {}
idx = 0

for z in range(Z_LAYERS):
    for q in range(-RADIUS, RADIUS + 1):
        for r in range(max(-RADIUS, -q - RADIUS), min(RADIUS, -q + RADIUS) + 1):
            s = -q - r
            # Permanent memory cells assigned to 4D index coordinates (q, r, s, z)
            nodes.append((q, r, s, z))
            coord_to_idx[(q, r, s, z)] = idx
            idx += 1

num_nodes = len(nodes)

# Build 3D 8-Neighbor Stencil Lookup Matrix (6 planar + 2 vertical directions)
neighbor_matrix = np.full((num_nodes, 8), -1, dtype=np.int32)
planar_dirs = [(+1, -1, 0), (+1, 0, -1), (0, +1, -1), (-1, +1, 0), (-1, 0, +1), (0, -1, +1)]

for idx, (q, r, s, z) in enumerate(nodes):
    # Map 6 horizontal planar neighbors
    for d_idx, (dq, dr, ds) in enumerate(planar_dirs):
        nb_coord = (q + dq, r + dr, s + ds, z)
        if nb_coord in coord_to_idx:
            neighbor_matrix[idx, d_idx] = coord_to_idx[nb_coord]
        else:
            neighbor_matrix[idx, d_idx] = idx

    # Map 2 vertical neighbors along Z axis (Z+1, Z-1)
    neighbor_matrix[idx, 6] = coord_to_idx[(q, r, s, min(z + 1, Z_LAYERS - 1))] # Top layer bounds fold
    neighbor_matrix[idx, 7] = coord_to_idx[(q, r, s, max(z - 1, 0))]             # Bottom layer bounds fold

# =====================================================================
# 3. 3D COMPONENT INITIALIZATION & HELICAL SIPHON VELOCITY FIELD
# =====================================================================
psi_re = np.zeros(num_nodes, dtype=np.float64)
psi_im = np.zeros(num_nodes, dtype=np.float64)
v_ext = np.zeros(num_nodes, dtype=np.float64)

# Separate dual-injection origins on the TOP layer (z = 2) to start the descending cascade
q_left, r_left, s_left = -2, 1, 1
q_right, r_right, s_right = 2, -1, -1

for idx, (q, r, s, z) in enumerate(nodes):
    dist_planar = np.sqrt(q**2 + r**2 + s**2)
    v_ext[idx] = 0.5 * 12.0 * (dist_planar / RADIUS)**4 # Boundary wall containment

    rho = 0.05
    vx, vy, vz = 0.0, 0.0, 0.0

    # Check injection maps on the input layer (Z=2)
    if z == 2:
        dist_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
        dist_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)

        if dist_A < 1.4 or dist_B < 1.4:
            rho = RHO_MAX
            # Synchronized clockwise chirality + strong localized downward siphon push (-Z)
            vx = -r * 0.4
            vy = q * 0.4
            vz = -0.8

    # Central Siphon Channel: Deep attractive vertical column routing down the origin
    if dist_planar <= 1.5:
        v_ext[idx] -= 20.0 # Form the vertical drainage pipe core
        if z < 2:          # Downward traction field active in middle and lower layers
            vx = -r * 0.5
            vy = q * 0.5
            vz = -1.0
            rho = 0.5

    # Madelung phase transformation integrated over 3 spatial dimensions
    theta = (MASS / HBAR) * (vx * 0.33 + vy * 0.33 + vz * 0.33)
    psi_re[idx] = np.sqrt(rho) * np.cos(theta)
    psi_im[idx] = np.sqrt(rho) * np.sin(theta)

INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

# =====================================================================
# 4. 3D HAMILTONIAN STENCIL SIMULATION LOOP
# =====================================================================
print("\n[ PHASE 3 ACTIVATED ] ENGAGING VERTICAL HELICAL SIPHON CORE")
print(f"Lattice Footprint: {num_nodes} 3D Matrix Nodes | Mass Envelope Locked: {INITIAL_MASS:.4f}")
print("=" * 85)
time.sleep(1)

for step in range(1, 21):
    psi_re_next = np.copy(psi_re)
    psi_im_next = np.copy(psi_im)
    gov_count = 0
    max_v = 0.0

    for i in range(num_nodes):
        re = psi_re[i]
        im = psi_im[i]
        rho = re**2 + im**2

        # Section 3.1: Complete 3D Hexagonal Discrete Laplacian Stencil
        lap_re_planar = 0.0
        lap_im_planar = 0.0
        for j in range(6):
            nb_p = neighbor_matrix[i, j]
            lap_re_planar += psi_re[nb_p] - re
            lap_im_planar += psi_im[nb_p] - im
        lap_re_planar *= (2.0 / (3.0 * (DX**2)))
        lap_im_planar *= (2.0 / (3.0 * (DX**2)))

        # Calculate Vertical Second-Derivative Component
        idx_top = neighbor_matrix[i, 6]
        idx_bot = neighbor_matrix[i, 7]
        lap_re_vert = (psi_re[idx_top] - 2.0 * re + psi_re[idx_bot]) / (DZ**2)
        lap_im_vert = (psi_im[idx_top] - 2.0 * im + psi_im[idx_bot]) / (DZ**2)

        # Combined 3D Laplacian
        lap_re = lap_re_planar + lap_re_vert
        # Fixed typos on imaginary component layout
        lap_im = lap_im_planar + lap_im_vert

        # Local Phase Gradient Monitor
        nb_axis = neighbor_matrix[i, 0]
        t_me = np.arctan2(im, re)
        t_nb = np.arctan2(psi_im[nb_axis], psi_re[nb_axis])
        dt = t_nb - t_me
        if dt > np.pi: dt -= 2*np.pi
        if dt < -np.pi: dt += 2*np.pi
        vel = (HBAR / MASS) * (abs(dt) / DX)
        if vel > max_v: max_v = vel

        # Section 4.2 Asymptotic Governor
        gamma = 0.0
        if vel > (0.6 * V_MAX):
            gov_count += 1
            gamma = BASELINE_MU * np.exp((K_STEEPNESS * vel) / (V_MAX - vel))

        h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext[i] + G_COEFF * rho) * re
        h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext[i] + G_COEFF * rho) * im

        psi_re_next[i] = re + (h_im + gamma * re) * DT
        psi_im_next[i] = im + (-h_re + gamma * im) * DT

    # Strict Unitary Normalization Lock across the 3D volume
    current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
    psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
    psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    print(f"Clock Step {step:02d} | Volume Mass: {np.sum(psi_re**2 + psi_im**2):.2f} | Peak Vel: {max_v:.4f} | Gov Triggers: {gov_count}")

# =====================================================================
# 5. POLAR SIPHON READOUT: OUTPUT COMPILER AT EXIT LAYER (z = 0)
# =====================================================================
print("-" * 85)
print("[POLAR SIPHON COMPILER] SCANNING 3D OUTPUT AT DISCHARGE LAYER (Z=0)...")

# Track the central core ring explicitly on the bottom exit slice (z=0)
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

w_charge = int(np.round(total_exit_phase / (2.0 * np.pi)))

print(f"[COMPILER STATE] Net Phase Accumulation at Exit Siphon: {total_exit_phase:.4f} Radians")
print(f"[COMPILER STATE] Extracted Topological Charge (Winding Number): {w_charge}")

if w_charge >= 1:
    print(f"[COMPILER OUTPUT] >>> LOGICAL STATE: {w_charge} (TRUE / 3D HELICAL LOGIC CORE BRAIDED & COMPILED SUCCESSFUL)")
elif w_charge == 0:
    print("[COMPILER OUTPUT] >>> LOGICAL STATE: 0 (FALSE / VACANT OUTPUT LAYER)")
else:
    print(f"[COMPILER OUTPUT] >>> LOGICAL STATE: {w_charge} (ANTI-VORTEX ERROR / PATH FAULT)")
