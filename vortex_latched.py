import numpy as np
import time

# =====================================================================
# 1. HARDENED PARAMETERS & STABILITY CONSTRAINTS
# =====================================================================
RADIUS = 5
HBAR = 1.0
MASS = 1.0
G_COEFF = 0.15        # Non-linear repulsive coupling coefficient (g)
RHO_MAX = 1.5
DX = 1.0
DT = 0.04

V_MAX = (HBAR * np.pi) / (MASS * DX)
K_STEEPNESS = 0.2
BASELINE_MU = 6.0

# =====================================================================
# 2. THE GEOMETRIC INDEX LATTICE (q + r + s = 0)
# =====================================================================
nodes = []
coord_to_idx = {}
idx = 0

for q in range(-RADIUS, RADIUS + 1):
    for r in range(max(-RADIUS, -q - RADIUS), min(RADIUS, -q + RADIUS) + 1):
        s = -q - r
        nodes.append((q, r, s))
        coord_to_idx[(q, r, s)] = idx
        idx += 1

num_nodes = len(nodes)

# Build memory-aligned 6-way planar neighbor stencil lookup matrix
neighbor_matrix = np.full((num_nodes, 6), -1, dtype=np.int32)
directions = [(+1, -1, 0), (+1, 0, -1), (0, +1, -1), (-1, +1, 0), (-1, 0, +1), (0, -1, +1)]

for idx, (q, r, s) in enumerate(nodes):
    for d_idx, (dq, dr, ds) in enumerate(directions):
        neighbor_coord = (q + dq, r + dr, s + ds)
        if neighbor_coord in coord_to_idx:
            neighbor_matrix[idx, d_idx] = coord_to_idx[neighbor_coord]
        else:
            neighbor_matrix[idx, d_idx] = idx  # Boundary reflection folds into self

# =====================================================================
# 3. COMPONENT INITIALIZATION & THE BINDING WELL FIELD
# =====================================================================
psi_re = np.zeros(num_nodes, dtype=np.float64)
psi_im = np.zeros(num_nodes, dtype=np.float64)
v_ext = np.zeros(num_nodes, dtype=np.float64)

# Defining the initial dual injection coordinates along the q-axis
q_left, r_left, s_left = -2, 1, 1
q_right, r_right, s_right = 2, -1, -1

for idx, (q, r, s) in enumerate(nodes):
    dist_global = np.sqrt(q**2 + r**2 + s**2)

    # 1. Establish the outer smooth container trap walls
    v_ext[idx] = 0.5 * 12.0 * (dist_global / RADIUS)**4

    # BREAKTHROUGH UPGRADE: Inject the negative 'Binding Well' at the precise origin
    if (q, r, s) == (0, 0, 0):
        v_ext[idx] = -50.0  # Deep attractive potential well to trap and latch the bit

    # Calculate localized distances to the two injection sites
    dist_vortex_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
    dist_vortex_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)

    rho = 0.05  # Default background vacuum
    vx, vy = 0.0, 0.0

    # Initialize Vortex A: Hypothesis Field (Clockwise Spin, Moving Right)
    if dist_vortex_A < 1.5:
        rho = RHO_MAX
        vx = -(r - r_left) * 0.4 + 0.5
        vy = (q - q_left) * 0.4

    # Initialize Vortex B: Constraint Field (MATCHED Clockwise Chirality, Moving Left)
    elif dist_vortex_B < 1.5:
        rho = RHO_MAX
        vx = -(r - r_right) * 0.4 - 0.5
        vy = (q - q_right) * 0.4

    # Madelung Transformation execution
    theta = (MASS / HBAR) * (vx * 0.5 + vy * 0.5)
    psi_re[idx] = np.sqrt(rho) * np.cos(theta)
    psi_im[idx] = np.sqrt(rho) * np.sin(theta)

INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

# =====================================================================
# 4. RUNNING PARALLEL LATCHING EVALUATION LOOP
# =====================================================================
print("\n[ LATCHED ENGAGEMENT SECURE ] CO-ROTATING ENTRAPMENT INITIALIZED")
print(f"Lattice Footprint: {num_nodes} Nodes | Target Logic Core Well (0,0,0): -50.0 eV Locked")
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

        # Hexagonal Stencil Laplacian
        lap_re = 0.0
        lap_im = 0.0
        for j in range(6):
            nb = neighbor_matrix[i, j]
            lap_re += psi_re[nb] - re
            lap_im += psi_im[nb] - im
        lap_re *= (2.0 / (3.0 * (DX**2)))
        lap_im *= (2.0 / (3.0 * (DX**2)))

        # Monitor localized Phase Gradient
        nb_p = neighbor_matrix[i, 0]
        t_me = np.arctan2(im, re)
        t_nb = np.arctan2(psi_im[nb_p], psi_re[nb_p])
        dt = t_nb - t_me
        if dt > np.pi: dt -= 2*np.pi
        if dt < -np.pi: dt += 2*np.pi
        vel = (HBAR / MASS) * (abs(dt) / DX)
        if vel > max_v: max_v = vel

        # Asymptotic Nyquist Governor
        gamma = 0.0
        if vel > (0.6 * V_MAX):
            gov_count += 1
            gamma = BASELINE_MU * np.exp((K_STEEPNESS * vel) / (V_MAX - vel))

        # Hamiltonian non-linear step update
        h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext[i] + G_COEFF * rho) * re
        h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext[i] + G_COEFF * rho) * im

        psi_re_next[i] = re + (h_im + gamma * re) * DT
        psi_im_next[i] = im + (-h_re + gamma * im) * DT

    # Strict Unitary Normalization Lock
    current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
    psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
    psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    print(f"Clock Step {step:02d} | Locked Mass: {np.sum(psi_re**2 + psi_im**2):.2f} | Peak Vel: {max_v:.4f} | Gov Triggers: {gov_count}")

# =====================================================================
# 5. CONTOUR LINE INTEGRAL COMPILER READOUT (braid_scanner.py)
# =====================================================================
print("-" * 85)
print("[COMPILER RUNTIME] ENGAGING TOPO-SCANNER COAXIAL READOUT OVER WELL...")

contour_coords = [(1, -1, 0), (0, -1, 1), (-1, 0, 1), (-1, 1, 0), (0, 1, -1), (1, 0, -1)]
contour_indices = [coord_to_idx[c] for c in contour_coords]
total_phase = 0.0

for idx in range(6):
    idx_c = contour_indices[idx]
    idx_n = contour_indices[(idx + 1) % 6]
    t_c = np.arctan2(psi_im[idx_c], psi_re[idx_c])
    t_n = np.arctan2(psi_im[idx_n], psi_re[idx_n])
    d_t = t_n - t_c
    if d_t > np.pi: d_t -= 2.0 * np.pi
    elif d_t < -np.pi: d_t += 2.0 * np.pi
    total_phase += d_t

w_charge = int(np.round(total_phase / (2.0 * np.pi)))

print(f"[SCANNER STATE] Net Phase Accumulation: {total_phase:.4f} Radians")
print(f"[SCANNER STATE] Detected Winding Number (Topological Charge): {w_charge}")

if w_charge >= 1:
    print(f"[COMPILER OUTPUT] >>> LOGICAL STATE: {w_charge} (TRUE / BIT LATCHED IN GEOMETRIC MEMORY WELL)")
elif w_charge == 0:
    print("[COMPILER OUTPUT] >>> LOGICAL STATE: 0 (FALSE / EMPTY MEMORY REGISTER)")
else:
    print(f"[COMPILER OUTPUT] >>> LOGICAL STATE: {w_charge} (ANTI-VORTEX ERROR / PATH FAULT)")
