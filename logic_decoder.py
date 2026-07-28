import numpy as np

class TopologicalLogicMatrix:
    def __init__(self, target_drift=0.056, tolerance=0.01):
        """
        Initializes the logic gate matrix with the physical characteristics
        discovered in the SU(2) spinor simulation.
        """
        self.target_drift = target_drift
        self.tolerance = tolerance

    def decode_phase_to_bit(self, raw_drift):
        """
        Maps continuous relative spin phase drift to a rigid binary classification.
        Implements a topological guard band to filter out numerical noise.
        """
        # Upper Window: Sequence 1 behavior (A over B)
        if hasattr(raw_drift, '__iter__'):
            raise ValueError("Input must be a scalar float phase value.")

        if abs(raw_drift - self.target_drift) <= self.tolerance:
            return 1

        # Lower Window: Sequence 2 behavior (B over A)
        elif abs(raw_drift - (-self.target_drift)) <= self.tolerance:
            return 0

        # Abelian Collapse Protection / Null State
        else:
            # If the system settles near 0.0, it's a commutative error state
            return -1

    def compile_truth_matrix(self, test_runs):
        """
        Compiles an array of simulated physical states into a clean
        computational truth table.
        """
        print("\n=====================================================================")
        print("[ LOGIC DECODER MATRIX ] COMPILING FRACTIONAL TO BINARY TRANSLATION")
        print("=====================================================================")
        print(f"{'Braid Sequence':<25} | {'Raw Phase Drift':<18} | {'Binary Output'}")
        print("---------------------------------------------------------------------")

        binary_states = []
        for label, raw_val in test_runs.items():
            bit = self.decode_phase_to_bit(raw_val)
            bit_str = "ERROR (ABELIAN)" if bit == -1 else f"BIT {bit}"
            print(f"{label:<25} | {raw_val:^18.6f} | {bit_str}")
            binary_states.append(bit)

        print("=====================================================================\n")
        return np.array(binary_states)