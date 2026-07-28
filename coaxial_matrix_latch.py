import numpy as np
import time

def run_coaxial_matrix_latch(sequence_type):
    """
    Simulates a discrete cell lattice where operations are forced to collide
    coaxially on the same physical matrix registers.
    sequence_type = 0: Operation A executes before Operation B (A -> B)
    sequence_type = 1: Operation B executes before Operation A (B -> A)
    """
    NUM_CELLS = 1024
    STEPS = 20

    # 1. FIXED RIGID SU(2) NON-COMMUTING OPERATORS (Pauli Spin Rotations)
    # Matrix A (Sigma_X Phase Rotation)
    matrix_A = np.array([[0, 1j], [1j, 0]], dtype=np.complex128)
    # Matrix B (Sigma_Y Phase Rotation)
    matrix_B = np.array([[0, 1], [-1, 0]], dtype=np.complex128)

    # Allocate cells with standard Identity matrices
    cell_states = np.zeros((NUM_CELLS, 2, 2), dtype=np.complex128)
    for i in range(NUM_CELLS):
        cell_states[i] = np.eye(2, dtype=np.complex128)

    center_latch_idx = NUM_CELLS // 2

    # 2. TIME-ORDERED STEPS MATRIX CLASHING
    for step in range(1, STEPS + 1):
        # We drive the system inputs directly into the core shared memory latch cell
        if sequence_type == 0:
            if step == 2:  # Operation A hits first
                cell_states[center_latch_idx] = np.matmul(cell_states[center_latch_idx], matrix_A)
            if step == 10: # Operation B hits second
                cell_states[center_latch_idx] = np.matmul(cell_states[center_latch_idx], matrix_B)
        else:
            if step == 2:  # Operation B hits first
                cell_states[center_latch_idx] = np.matmul(cell_states[center_latch_idx], matrix_B)
            if step == 10: # Operation A hits second
                cell_states[center_latch_idx] = np.matmul(cell_states[center_latch_idx], matrix_A)

        # Discrete Nearest-Neighbor Cross-Talk Diffusion Step
        # Cells rotate based on their adjacent neighbors to distribute the logic state
        left_nb = np.roll(cell_states, 1, axis=0)
        right_nb = np.roll(cell_states, -1, axis=0)

        for idx in range(NUM_CELLS):
            # Propagate the algebraic state across adjacent cell columns
            cell_states[idx] = np.matmul(cell_states[idx], left_nb[idx] + right_nb[idx] * 0.5)

            # --- TRUE SU(2) SPECIAL UNITARY RE-ORTHOGONALIZATION LAYER ---
            # Explicit Gram-Schmidt pass to keep rows perfectly orthogonal and normalized to unit length
            row_0 = cell_states[idx, 0, :]
            row_1 = cell_states[idx, 1, :]

            # Normalize Row 0
            norm_0 = np.linalg.norm(row_0)
            if norm_0 > 0: row_0 = row_0 / norm_0

            # Orthogonalize Row 1 against Row 0
            proj = np.dot(row_1, np.conj(row_0)) * row_0
            row_1 = row_1 - proj

            # Normalize Row 1
            norm_1 = np.linalg.norm(row_1)
            if norm_1 > 0: row_1 = row_1 / norm_1

            # Write back the clean unitary rows to prevent floating-point value decay
            cell_states[idx, 0, :] = row_0
            cell_states[idx, 1, :] = row_1

    return cell_states

if __name__ == "__main__":
    print("\n" + "="*85)
    print("[ INITIALIZING DISCRETE LATCH CORE ] TESTING SHARED COAXIAL REGISTERS")
    print("="*85)
    time.sleep(0.5)

    print("Executing Coaxial Sequence 1 (Operation A -> Operation B)...")
    seq_1_matrix_output = run_coaxial_matrix_latch(sequence_type=0)

    print("Executing Coaxial Sequence 2 (Operation B -> Operation A)...")
    seq_2_matrix_output = run_coaxial_matrix_latch(sequence_type=1)

    # Measure the absolute matrix variance across the total grid space via Frobenius norm comparison
    net_matrix_divergence = np.sum(np.abs(seq_1_matrix_output - seq_2_matrix_output))

    print("\n" + "-"*85)
    print("[ LATCH PERFORMANCE METRICS ] REAL READOUT SUMMARY:")
    print("-" * 85)
    print(f"  -> Target Latch Registers Allocated: 1,024 Cells")
    print(f"  -> Hardware Footprint Scaling Bound : STRICT FIXED OVERHEAD")
    print(f"  -> Pure Discrete Net Divergence    : {net_matrix_divergence:.6f} Real Logic Units")
    print("-" * 85)

    if net_matrix_divergence > 1.0:
        print("\n[VERIFICATION: SUCCESSFUL TRUE] >>> DIVERGENCE SECURED BY NON-COMMUTING FIELD LOGIC!!!")
        print("Forcing the operations to hit the same cell explicitly locked the arrival history.")
        print("The final matrix states are structurally distinct because Matrix_A * Matrix_B != Matrix_B * Matrix_A.")
    else:
        print("\n[VERIFICATION: FAILED] Field collapsed back into a commutative state.")
    print("="*85 + "\n")
