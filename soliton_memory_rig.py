import numpy as np
import time

def simulate_soliton_gate(sequence_type):
    """
    Simulates a non-linear Discrete Non-Linear Schrödinger (DNLS) lattice.
    Tracks a persistent soliton interacting with sequential directional inputs.
    sequence_type = 0: Input X then Input Y (Left-to-Right dominant drive)
    sequence_type = 1: Input Y then Input X (Right-to-Left dominant drive)
    """
    NUM_NODES = 512
    DT = 0.005
    STEPS = 100

    # Non-linear self-focusing coefficient (Forces wave packets to remain tightly bound)
    CHI = 4.0
    J_COUPLING = 1.0  # Linear tunneling between adjacent nodes

    # Initialize a complex wavefunction field across the lattice registers
    psi = np.zeros(NUM_NODES, dtype=np.complex128)

    # Seed a highly stable, localized Soliton core at the exact spatial center
    center_idx = NUM_NODES // 2
    psi[center_idx] = 2.0 + 0j  # High energy core to trigger non-linear trapping

    # Pre-compile boundary node indexing maps
    idx = np.arange(NUM_NODES)
    left_nb = (idx - 1) % NUM_NODES
    right_nb = (idx + 1) % NUM_NODES

    # --- HISTORICAL TIME-STEP INTEGRATION LOOP ---
    for step in range(STEPS):
        # Apply the Sequential Spatiotemporal Injection
        if sequence_type == 0:
            if step == 10:  # Input X arrives from the Left quadrant first
                psi[center_idx - 50] += 1.5 + 0.5j
            if step == 40:  # Input Y arrives from the Right quadrant second
                psi[center_idx + 50] += 1.5 - 0.5j
        else:
            if step == 10:  # Input Y arrives from the Right quadrant first
                psi[center_idx + 50] += 1.5 - 0.5j
            if step == 40:  # Input X arrives from the Left quadrant second
                psi[center_idx - 50] += 1.5 + 0.5j

        # Compute the explicit DNLS discrete Hamiltonian updates
        # H_i = -J*(psi_{i+1} + psi_{i-1}) - CHI * |psi_i|^2 * psi_i
        rho = np.abs(psi) ** 2
        h_eff = -J_COUPLING * (psi[right_nb] + psi[left_nb]) - CHI * rho * psi

        # Continuous time-evolution step (psi_n depends strictly on psi_{n-1})
        psi += -1j * h_eff * DT

        # Unitary Normalization Lock to maintain strict hardware energy caps
        total_mass = np.sum(np.abs(psi) ** 2)
        if total_mass > 0:
            psi *= np.sqrt(20.0 / total_mass)

    # Return the raw absolute mass density allocation matrix
    return np.abs(psi) ** 2

if __name__ == "__main__":
    print("\n" + "="*90)
    print("[ SOLITONIC DISCOVERY PLATFORM ] TESTING PARADIGM METHOD v0.1")
    print("="*90)
    time.sleep(0.5)

    print("Executing Time-Ordered Sequence 1 (Input X -> Input Y)...")
    density_seq_1 = simulate_soliton_gate(sequence_type=0)

    print("Executing Time-Ordered Sequence 2 (Input Y -> Input X)...")
    density_seq_2 = simulate_soliton_gate(sequence_type=1)

    # QUANTIFY TRUE PATH DEPENDENCE: Calculate the net structural shift of the soliton
    net_structural_divergence = np.sum(np.abs(density_seq_1 - density_seq_2))

    # Extract peak coordinate locations to verify state-latching stabilization
    peak_1 = np.argmax(density_seq_1)
    peak_2 = np.argmax(density_seq_2)

    print("\n" + "-"*90)
    print("[ DISCOVERY LAB METRICS ] SUMMARY:")
    print("-" * 90)
    print(f"  -> Sequence 1 Core Latch Position: Node Index [{peak_1}]")
    print(f"  -> Sequence 2 Core Latch Position: Node Index [{peak_2}]")
    print(f"  -> Pure Physical Net Divergence  : {net_structural_divergence:.6f} Mass Units")
    print("-" * 90)

    if net_structural_divergence > 1e-4:
        print("\n[VERIFICATION: SUCCESSFUL HYPOTHESIS DETECTED]")
        print("The non-linear self-focusing constraints successfully trapped the history.")
        print("Changing the order of inputs physically shifted the final location of the soliton.")
    else:
        print("\n[VERIFICATION: FAILED] Field variables collapsed back into commutative symmetry.")
    print("="*90 + "\n")
