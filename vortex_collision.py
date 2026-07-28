import numpy as np
import time

# =====================================================================
# 1. PARAMETERS & HARD-LOCKED CONSTRAINTS
# =====================================================================
RADIUS = 5            # Expanded grid radius to allow spatial buffer for collision
HBAR = 1.0
MASS = 1.0
G_COEFF = 0.15        # Non-linear interaction strength (g)
RHO_MAX = 1.5
DX = 1.0
DT = 0.04             # Strict small time-step to preserve unitary conservation

V_MAX = (HBAR * np.pi) / (MASS * DX)
K_STEEPNESS = 0.2
BASELINE_MU = 6.0     # Increased dampening slightly for the violent collision phase

# =====================================================================
# 2. DUAL-CORE HEXAGONAL LATTICE GENERATION
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

neighbor_matrix = np.full((num_nodes, 6), -1, dtype=np.int32)
directions = [(+1, -1, 0), (+1, 0, -1), (0, +1, -1), (-1, +1, 0), (-1, 0, +1), (0, -1, +1)]

for idx, (q, r, s) in enumerate(nodes):
    for d_idx, (dq, dr, ds) in enumerate(directions):
        neighbor_coord = (q + dq, r + dr, s + ds)
        if neighbor_coord in coord_to_idx:
            neighbor_matrix[idx, d_idx] = coord_to_idx[neighbor_coord]
        else:
            neighbor_matrix[idx, d_idx] = idx

# =====================================================================
# 3. INITIALIZING DUAL COLLIDING VORTICES (Hypothesis vs Constraint)
# =====================================================================
psi_re = np.zeros(num_nodes, dtype=np.float64)
psi_im = np.zeros(num_nodes, dtype=np.float64)
v_ext = np.zeros(num_nodes, dtype=np.float64)

# Define the coordinates for the Left Center and Right Center of collision
q_left, r_left, s_left = -2, 1, 1
q_right, r_right, s_right = 2, -1, -1

for idx, (q, r, s) in enumerate(nodes):
    dist_global = np.sqrt(q**2 + r**2 + s**2)
    v_ext[idx] = 0.5 * 12.0 * (dist_global / RADIUS)**4 # Smooth container wall

    # Calculate localized distances to the two distinct vortex centers
    dist_vortex_A = np.sqrt((q - q_left)**2 + (r - r_left)**2 + (s - s_left)**2)
    dist_vortex_B = np.sqrt((q - q_right)**2 + (r - r_right)**2 + (s - s_right)**2)

    rho = 0.05 # Default vacuum background
    vx, vy = 0.0, 0.0

    # Initialize Vortex A: Hypothesis Field (Spinning Clockwise, Moving Right)
    if dist_vortex_A < 1.5:
        rho = RHO_MAX
        vx = -(r - r_left) * 0.4 + 0.5  # Local torque + global rightward linear momentum
        vy = (q - q_left) * 0.4

    # Initialize Vortex B: Constraint Field (Spinning Counter-Clockwise, Moving Left)
    elif dist_vortex_B < 1.5:
        rho = RHO_MAX
        vx = (r - r_right) * 0.4 - 0.5  # Local reverse torque + global leftward linear momentum
        vy = -(q - q_right) * 0.4

    # Madelung Transformation to lock initial wave state
    theta = (MASS / HBAR) * (vx * 0.5 + vy * 0.5)
    psi_re[idx] = np.sqrt(rho) * np.cos(theta)
    psi_im[idx] = np.sqrt(rho) * np.sin(theta)

INITIAL_MASS = np.sum(psi_re**2 + psi_im**2)

# =====================================================================
# 4. COLLISION EXECUTION & LIVE MOVEMENT LOOP
# =====================================================================
print("\n[ COLLISION HAZARD ENGAGED ] INJECTING PROPAGATING DUAL FIELDS")
print(f"Lattice Footprint: {num_nodes} Nodes | Immutable Mass System: {INITIAL_MASS:.4f} Fixed")
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

        # Monitor Local Velocity
        nb_p = neighbor_matrix[i, 0]
        t_me = np.arctan2(im, re)
        t_nb = np.arctan2(psi_im[nb_p], psi_re[nb_p])
        dt = t_nb - t_me
        if dt > np.pi: dt -= 2*np.pi
        if dt < -np.pi: dt += 2*np.pi
        vel = (HBAR / MASS) * (abs(dt) / DX)
        if vel > max_v: max_v = vel

        # Asymptotic Governor
        gamma = 0.0
        if vel > (0.6 * V_MAX):
            gov_count += 1
            gamma = BASELINE_MU * np.exp((K_STEEPNESS * vel) / (V_MAX - vel))

        # Hamiltonian evolution mapping
        h_re = - (HBAR**2 / (2 * MASS)) * lap_re + (v_ext[i] + G_COEFF * rho) * re
        h_im = - (HBAR**2 / (2 * MASS)) * lap_im + (v_ext[i] + G_COEFF * rho) * im

        psi_re_next[i] = re + (h_im + gamma * re) * DT
        psi_im_next[i] = im + (-h_re + gamma * im) * DT

    # Strict Unitary Normalization Lock
    current_mass = np.sum(psi_re_next**2 + psi_im_next**2)
    psi_re = psi_re_next * np.sqrt(INITIAL_MASS / current_mass)
    psi_im = psi_im_next * np.sqrt(INITIAL_MASS / current_mass)

    # Visual ASCII Real-time Render
    grid_visualization = ""
    for idx, (q, r, s) in enumerate(nodes):
        node_density = psi_re[idx]**2 + psi_im[idx]**2
        if node_density > (RHO_MAX * 0.9):
            grid_visualization += "🌀" # Primary concentrated vortex cores
        elif node_density > (RHO_MAX * 0.3):
            grid_visualization += "░░" # Advancing interference fronts
        else:
            grid_visualization += "  " # Spatial background

    # Print dynamic status tracking
    print(f"Clock Step {step:02d} | Locked Mass: {np.sum(psi_re**2 + psi_im**2):.2f} | Peak Vel: {max_v:.4f} | Gov Triggers: {gov_count}")

    # FIXED LINE: Enforced the explicit printing interval array [3]
    if step in [1, 5, 10, 15, 20]:
        phase_labels = {1: "INITIAL INJECTION", 5: "APPROACH & FIRST CONTACT", 10: "MAXIMUM INTERFERENCE IMPACT", 15: "STRUCTURAL FILTRATION", 20: "STEADY-STATE RESOLUTION"}
        print(f"--- PHASE STATE: {phase_labels[step]} ---")
        print(f"{grid_visualization}\n" + "-" * 85)
        time.sleep(0.5)
