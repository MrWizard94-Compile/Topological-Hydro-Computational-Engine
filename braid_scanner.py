import numpy as np

def calculate_winding_number(nodes, coord_to_idx, psi_re, psi_im):
    """
    Scans a closed geometric loop around the center of the lattice
    to calculate the topological charge (winding number) of the vortex.
    """
    # Define a closed 6-node hexagonal loop directly surrounding the origin (0,0,0)
    # Moving clockwise around the core
    contour_coords = [
        (1, -1, 0),   # E
        (0, -1, 1),   # SE
        (-1, 0, 1),   # SW
        (-1, 1, 0),   # W
        (0, 1, -1),   # NW
        (1, 0, -1)    # NE
    ]

    # Map coordinates to their linear memory array indices
    contour_indices = []
    for coord in contour_coords:
        if coord in coord_to_idx:
            contour_indices.append(coord_to_idx[coord])
        else:
            print(f"[COMPILER ERROR] Contour node {coord} missing from lattice definition.")
            return None

    total_phase_accumulation = 0.0
    num_pts = len(contour_indices)

    # Perform discrete line integration around the loop
    for idx in range(num_pts):
        idx_current = contour_indices[idx]
        idx_next = contour_indices[(idx + 1) % num_pts] # Close the circle

        # Pull real and imaginary states to extract phase via Madelung angle
        theta_current = np.arctan2(psi_im[idx_current], psi_re[idx_current])
        theta_next = np.arctan2(psi_im[idx_next], psi_re[idx_next])

        # Calculate phase difference
        d_theta = theta_next - theta_current

        # Rigorous trigonometric unwrapping to handle branch cuts at (-pi, pi]
        if d_theta > np.pi:
            d_theta -= 2.0 * np.pi
        elif d_theta < -np.pi:
            d_theta += 2.0 * np.pi

        total_phase_accumulation += d_theta

    # The winding number is the total phase wrapped divided by a full circle (2*pi)
    winding_number = total_phase_accumulation / (2.0 * np.pi)

    # Snap to closest discrete integer to eliminate floating-point precision drift
    return int(np.round(winding_number))

# =====================================================================
# INTEGRATION TESTING CORE
# =====================================================================
if __name__ == "__main__":
    print("\n[ COMPILER RUNTIME INITIALIZED ] ENGAGING TOPOLOGICAL BRAID SCANNER")
    print("-" * 85)

    # Mocking a stable Step 20 state vector array matching your 91-node lattice layout
    # Let's verify how the scanner interprets a clockwise spinning vortex core
    mock_num_nodes = 91
    mock_psi_re = np.zeros(mock_num_nodes, dtype=np.float64)
    mock_psi_im = np.zeros(mock_num_nodes, dtype=np.float64)

    # Re-importing a clean coordinate lookup index matrix
    from vortex_collision import nodes, coord_to_idx

    # Inject a known topological charge of +1 into the contour nodes
    for idx, (q, r, s) in enumerate(nodes):
        if (q, r, s) in [(1,-1,0), (0,-1,1), (-1,0,1), (-1,1,0), (0,1,-1), (1,0,-1)]:
            # Generate a clean sequential phase wrapping around the core
            angle = np.arctan2(r, q)
            mock_psi_re[idx] = np.sqrt(1.5) * np.cos(angle)
            mock_psi_im[idx] = np.sqrt(1.5) * np.sin(angle)
        else:
            mock_psi_re[idx] = np.sqrt(0.05) # Background vacuum
            mock_psi_im[idx] = 0.0

    # Execute Braid Scan
    w_charge = calculate_winding_number(nodes, coord_to_idx, mock_psi_re, mock_psi_im)

    print(f"[SCANNER STATE] Net Phase Accumulation: {w_charge * 2 * np.pi:.4f} Radians")
    print(f"[SCANNER STATE] Detected Winding Number (Topological Charge): {w_charge}")

    # --- DETERMINISTIC BINARY COMPILE MAPPING ---
    if w_charge == 1:
        print("[COMPILER OUTPUT] >>> LOGICAL STATE: 1 (TRUE / ACTIVE AST NODE)")
    elif w_charge == 0:
        print("[COMPILER OUTPUT] >>> LOGICAL STATE: 0 (FALSE / NULL ARCHITECTURE)")
    else:
        print(f"[COMPILER OUTPUT] >>> LOGICAL STATE: {w_charge} (ANTI-VORTEX ERROR / PATH FAULT)")
