import numpy as np

def simulate_soliton_hybrid(sequence_type):
    """
    Hybrid test: Lower CHI + stronger directional inputs + discrete potential wells.
    Goal: Get the soliton to latch into different stable wells based on input order.
    """
    NUM_NODES = 512
    DT = 0.002
    STEPS = 600
    CHI = 3.5                    # From Version A (good balance)
    J_COUPLING = 0.65
    INPUT_STRENGTH = 3.2
    INPUT_MOMENTUM = 0.9
    WELL_DEPTH = 1.2             # Deeper wells than Version B
    WELL_WIDTH = 18

    psi = np.zeros(NUM_NODES, dtype=np.complex128)
    center = NUM_NODES // 2
    left_well = center - 80
    right_well = center + 80

    # Start soliton in the left well
    psi[left_well] = 2.3 + 0j

    idx = np.arange(NUM_NODES)
    left_nb = (idx - 1) % NUM_NODES
    right_nb = (idx + 1) % NUM_NODES

    # Create two discrete potential wells
    potential = np.zeros(NUM_NODES)
    for i in range(NUM_NODES):
        potential[i] = -WELL_DEPTH * (
            np.exp(-((i - left_well)**2) / (2 * WELL_WIDTH**2)) +
            np.exp(-((i - right_well)**2) / (2 * WELL_WIDTH**2))
        )

    for step in range(STEPS):
        # Directional inputs with momentum
        if sequence_type == 0:  # Left → Right
            if step == 60:
                psi[left_well - 25] += INPUT_STRENGTH * (1.0 + INPUT_MOMENTUM * 1j)
            if step == 180:
                psi[right_well + 25] += INPUT_STRENGTH * (1.0 - INPUT_MOMENTUM * 1j)
        else:  # Right → Left
            if step == 60:
                psi[right_well + 25] += INPUT_STRENGTH * (1.0 - INPUT_MOMENTUM * 1j)
            if step == 180:
                psi[left_well - 25] += INPUT_STRENGTH * (1.0 + INPUT_MOMENTUM * 1j)

        # DNLS evolution + potential
        rho = np.abs(psi)**2
        h_eff = (-J_COUPLING * (psi[right_nb] + psi[left_nb])
                 - CHI * rho * psi
                 + potential * psi)

        psi += -1j * h_eff * DT

        # Normalization
        total_mass = np.sum(np.abs(psi)**2)
        if total_mass > 0:
            psi *= np.sqrt(22.0 / total_mass)

    density = np.abs(psi)**2
    peak_pos = np.argmax(density)
    peak_value = density[peak_pos]

    # Also check which well it's closest to
    dist_to_left = abs(peak_pos - left_well)
    dist_to_right = abs(peak_pos - right_well)
    final_well = "Left" if dist_to_left < dist_to_right else "Right"

    return density, peak_pos, final_well


if __name__ == "__main__":
    print("\n" + "="*90)
    print("[ HYBRID SOLITON TEST vC - A + B ]")
    print("="*90)

    d0, p0, well0 = simulate_soliton_hybrid(0)
    d1, p1, well1 = simulate_soliton_hybrid(1)

    print(f"\nSequence 0 (Left → Right) → Peak: {p0} | Well: {well0}")
    print(f"Sequence 1 (Right → Left) → Peak: {p1} | Well: {well1}")
    print(f"\nPeak Position Difference : {abs(p0 - p1)} nodes")
    print(f"Total Density Divergence : {np.sum(np.abs(d0 - d1)):.6f}")
    print("-" * 90)

    if well0 != well1:
        print("\n[RESULT] STRONG PATH DEPENDENCE")
        print(f"The soliton latched into different wells depending on input order.")
        print(f"Well 0: {well0} | Well 1: {well1}")
    elif abs(p0 - p1) >= 15:
        print("\n[RESULT] MODERATE PATH DEPENDENCE")
        print("The soliton ends in clearly different positions, but not in separate wells.")
    else:
        print("\n[RESULT] WEAK / NO PATH DEPENDENCE")
        print("The soliton returns to similar locations regardless of sequence.")
    print("="*90 + "\n")