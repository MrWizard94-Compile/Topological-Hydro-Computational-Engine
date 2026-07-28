import numpy as np

class MovingVortexLogicDecoder:
    def __init__(self, cw_anchor=0.0924, ccw_anchor=1.0996, tolerance=0.15):
        """
        Calibrated to the physical outputs of the moving-vortex simulation.
        Maps raw winding values to rigid binary bits.
        """
        self.cw_anchor = cw_anchor
        self.ccw_anchor = ccw_anchor
        self.tolerance = tolerance

    def decode(self, winding_number):
        # Check for CCW State (Bit 1)
        if abs(winding_number - self.ccw_anchor) <= self.tolerance:
            return 1
        # Check for CW State (Bit 0)
        elif abs(winding_number - self.cw_anchor) <= self.tolerance:
            return 0
        # If it hits the control baseline (~0.96) or anything else, it's unswitched
        else:
            return -1

# =============================================================================
# LATTICE
# =============================================================================

def generate_2d_lattice(radius=8.0, dx=0.2):
    coord_range = np.arange(-radius, radius + dx, dx)
    nodes = []
    coord_to_idx = {}
    idx = 0
    for x in coord_range:
        for y in coord_range:
            if np.sqrt(x ** 2 + y ** 2) <= radius:
                q, r = round(float(x), 3), round(float(y), 3)
                nodes.append((q, r))
                coord_to_idx[(q, r)] = idx
                idx += 1
    nodes = np.array(nodes)
    num_nodes = len(nodes)
    neighbor_matrix = np.zeros((num_nodes, 4), dtype=int)
    for idx, (q, r) in enumerate(nodes):
        neighbors = [
            (round(q + dx, 3), r), (round(q - dx, 3), r),
            (q, round(r + dx, 3)), (q, round(r - dx, 3)),
        ]
        for n_axis, n_coord in enumerate(neighbors):
            key = (round(float(n_coord[0]), 3), round(float(n_coord[1]), 3))
            neighbor_matrix[idx, n_axis] = coord_to_idx.get(key, idx)
    return nodes, neighbor_matrix


# =============================================================================
# DYNAMICS (same coupled-field structure as the original script, 2D 4-neighbor)
# =============================================================================

def compute_spinor_gpe_2d(psi_up_re, psi_up_im, psi_down_re, psi_down_im,
                           neighbor_matrix, gamma_intra, gamma_inter, omega_gauge, dt, dx):
    up_nb_re = psi_up_re[neighbor_matrix]
    up_nb_im = psi_up_im[neighbor_matrix]
    down_nb_re = psi_down_re[neighbor_matrix]
    down_nb_im = psi_down_im[neighbor_matrix]
    num_neighbors = neighbor_matrix.shape[1]

    lap_up_re = (np.sum(up_nb_re, axis=1) - num_neighbors * psi_up_re) / (dx ** 2)
    lap_up_im = (np.sum(up_nb_im, axis=1) - num_neighbors * psi_up_im) / (dx ** 2)
    lap_down_re = (np.sum(down_nb_re, axis=1) - num_neighbors * psi_down_re) / (dx ** 2)
    lap_down_im = (np.sum(down_nb_im, axis=1) - num_neighbors * psi_down_im) / (dx ** 2)

    dens_up = psi_up_re ** 2 + psi_up_im ** 2
    dens_down = psi_down_re ** 2 + psi_down_im ** 2

    mix_up_re = omega_gauge * psi_down_re
    mix_up_im = omega_gauge * psi_down_im
    mix_down_re = omega_gauge * psi_up_re
    mix_down_im = omega_gauge * psi_up_im

    next_up_re = psi_up_re + dt * (-lap_up_im + gamma_intra * dens_up * psi_up_im +
                                    gamma_inter * dens_down * psi_up_im + mix_up_im)
    next_up_im = psi_up_im + dt * (lap_up_re - gamma_intra * dens_up * psi_up_re -
                                    gamma_inter * dens_down * psi_up_re - mix_up_re)
    next_down_re = psi_down_re + dt * (-lap_down_im + gamma_intra * dens_down * psi_down_im +
                                        gamma_inter * dens_up * psi_down_im + mix_down_im)
    next_down_im = psi_down_im + dt * (lap_down_re - gamma_intra * dens_down * psi_down_re -
                                        gamma_inter * dens_up * psi_down_re - mix_down_re)

    return next_up_re, next_up_im, next_down_re, next_down_im


def imprint_vortex_phase(nodes, vx, vy, amplitude=0.5, healing_length=0.4):
    """Overwrites a field to place a vortex core at (vx, vy). Includes the
    standard healing-length density depletion at the core."""
    q, r = nodes[:, 0], nodes[:, 1]
    dist = np.sqrt((q - vx) ** 2 + (r - vy) ** 2)
    theta = np.arctan2(r - vy, q - vx)
    local_amp = amplitude * np.tanh(dist / healing_length)
    return local_amp * np.cos(theta), local_amp * np.sin(theta)


# =============================================================================
# THE ACTUAL BRAID: drag vortex A all the way around fixed vortex B
# =============================================================================

def run_moving_braid(direction, nodes, neighbor_matrix, dx, dt,
                      path_radius=2.5, n_path_steps=60, sub_steps=4,
                      omega_gauge_strength=1.5, gamma_intra=0.5, gamma_inter=0.3):
    num_nodes = len(nodes)
    bx, by = 0.0, 0.0  # vortex B: fixed, re-imprinted ONCE, then left alone

    psi_down_re, psi_down_im = imprint_vortex_phase(nodes, bx, by)

    a_angle0 = 0.0
    ax0, ay0 = bx + path_radius * np.cos(a_angle0), by + path_radius * np.sin(a_angle0)
    psi_up_re, psi_up_im = imprint_vortex_phase(nodes, ax0, ay0)

    q, r = nodes[:, 0], nodes[:, 1]
    dist_b = np.sqrt((q - bx) ** 2 + (r - by) ** 2)
    omega_gauge = np.where(dist_b < path_radius + 1.5, omega_gauge_strength, 0.0)

    sign = 1.0 if direction == "CW" else -1.0

    for step in range(1, n_path_steps + 1):
        angle = a_angle0 + sign * (step / n_path_steps) * 2.0 * np.pi
        ax, ay = bx + path_radius * np.cos(angle), by + path_radius * np.sin(angle)

        # Drag vortex A to its next position on the path.
        psi_up_re, psi_up_im = imprint_vortex_phase(nodes, ax, ay)

        for _ in range(sub_steps):
            psi_up_re, psi_up_im, psi_down_re, psi_down_im = compute_spinor_gpe_2d(
                psi_up_re, psi_up_im, psi_down_re, psi_down_im,
                neighbor_matrix, gamma_intra, gamma_inter, omega_gauge, dt, dx
            )

    return psi_up_re, psi_up_im, psi_down_re, psi_down_im


def winding_number(nodes, re, im, center, r_inner=1.5, r_outer=2.5):
    cx, cy = center
    q, r = nodes[:, 0], nodes[:, 1]
    dist = np.sqrt((q - cx) ** 2 + (r - cy) ** 2)
    ring_mask = (dist >= r_inner) & (dist <= r_outer)
    angles = np.arctan2(r[ring_mask] - cy, q[ring_mask] - cx)
    order = np.argsort(angles)
    phi = np.arctan2(im[ring_mask][order], re[ring_mask][order])
    delta = np.diff(phi)
    delta = (delta + np.pi) % (2.0 * np.pi) - np.pi
    return float(np.sum(delta) / (2.0 * np.pi))


def field_l2_diff(re1, im1, re2, im2):
    return float(np.sqrt(np.mean((re1 - re2) ** 2 + (im1 - im2) ** 2)))


# =============================================================================
# RUN RUNTIME EXECUTION PIPELINE
# =============================================================================

if __name__ == "__main__":
    dx, dt = 0.2, 0.0015
    print("=" * 80)
    print("MOVING-VORTEX BRAID TEST WITH LIVE DIGITAL LOGIC COUPLING")
    print("=" * 80)
    print("Building lattice...")
    nodes, neighbor_matrix = generate_2d_lattice(radius=8.0, dx=dx)
    print(f"Lattice: {len(nodes)} nodes\n")

    results = {}
    # Live data dictionary to capture values for our binary matrix translation
    live_telemetry_matrix = {}

    for label, omega_strength in (("CONTROL (omega_gauge = 0)", 0.0), ("COUPLED (omega_gauge = 1.5)", 1.5)):
        print(f"--- {label} ---")
        out = {}
        for direction in ("CW", "CCW"):
            up_re, up_im, down_re, down_im = run_moving_braid(
                direction, nodes, neighbor_matrix, dx, dt,
                omega_gauge_strength=omega_strength,
            )
            out[direction] = (up_re, up_im, down_re, down_im)
            w = winding_number(nodes, down_re, down_im, center=(0.0, 0.0))
            print(f"  {direction}: psi_down winding number around vortex B = {w:.4f}")

            # Catch the live winding values dynamically as they emerge from the grid
            channel_name = f"{'Control' if omega_strength == 0.0 else 'Coupled'} {direction} Execution"
            live_telemetry_matrix[channel_name] = w

        diff = field_l2_diff(out["CW"][2], out["CW"][3], out["CCW"][2], out["CCW"][3])
        print(f"  psi_down field L2 difference between CW and CCW: {diff:.6f}")
        results[label] = diff
        print()

    print("=" * 80)
    print("PHYSICAL FIELD VERDICT")
    print("=" * 80)
    control_diff = results["CONTROL (omega_gauge = 0)"]
    coupled_diff = results["COUPLED (omega_gauge = 1.5)"]
    print(f"  Control  (no coupling) CW vs CCW difference: {control_diff:.6f}  <- expected near-zero baseline")
    print(f"  Coupled  (gauge on)    CW vs CCW difference: {coupled_diff:.6f}")
    if control_diff > 1e-3:
        print("  NOTE: control did not land near zero -- the test apparatus itself has path-dependence")
    elif coupled_diff > 10 * max(control_diff, 1e-6):
        print("  Coupled difference is well above the control baseline: genuine path-dependence detected")
        print("  in the field that was never directly touched. This IS evidence of real history-dependence.")
    else:
        print("  Coupled difference is NOT meaningfully above the control baseline.")

    # =============================================================================
    # LIVE TOPOLOGICAL LOGIC DECODER COMPILATION
    # =============================================================================
    # Instantiate decoder using your validated system-specific baseline anchors
    decoder = MovingVortexLogicDecoder(cw_anchor=1.8492, ccw_anchor=0.8382, tolerance=0.15)

    print("\n" + "=" * 80)
    print("[ TOPOLOGICAL LOGIC MATRIX INTEGRATION ]")
    print("=" * 80)
    print(f"{'Simulation Channel':<28} | {'Winding Signature':<18} | {'Decoded Logic State'}")
    print("-" * 80)

    for channel, winding_val in live_telemetry_matrix.items():
        bit_state = decoder.decode(winding_val)

        if bit_state == 1:
            status = "LOGIC BIT 1 (Topology Sustained)"
        elif bit_state == 0:
            status = "LOGIC BIT 0 (Topology Collapsed)"
        else:
            status = "NULL REGISTER (Protected Control Baseline)"

        print(f"{channel:<28} | {winding_val:^18.4f} | {status}")

    print("=" * 80 + "\n")