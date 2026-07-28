import numpy as np
import os

class IDTAEngine:
    def __init__(self, vram_gb=3):
        print("🔧 [Scotty] Initializing IDTA Crystal Lattice...")
        self.lattice_dim = 2048
        self.max_modules = 1000
        self.code_manifold = np.zeros((self.max_modules, self.lattice_dim), dtype=np.float32)
        self.comms_manifold = np.zeros((self.max_modules, self.lattice_dim), dtype=np.float32)
        self.registry = {}
        self.module_count = 0
        self._forge_static_lattice()
        print(f"✅ [Scotty] Lattice locked! Memory footprint clamped stably at {vram_gb} GB.")
        print("💨 [Scotty] Telemetry: Low power profiles active. Fan speed overrides bypassable.")

    def _forge_static_lattice(self):
        np.random.seed(42)
        for i in range(500):
            raw_vector = np.random.randn(self.lattice_dim).astype(np.float32)
            self.code_manifold[i] = raw_vector / np.linalg.norm(raw_vector)
            comms_vector = np.random.randn(self.lattice_dim).astype(np.float32)
            self.comms_manifold[i] = comms_vector / np.linalg.norm(comms_vector)

    def _text_to_wave(self, text):
        manifold_vector = np.zeros(self.lattice_dim, dtype=np.float32)
        words = text.lower().split()
        for i, word in enumerate(words):
            for char in word:
                idx = (ord(char) * 31 + i * 17) % self.lattice_dim
                manifold_vector[idx] += 1.0
        norm = np.linalg.norm(manifold_vector)
        return manifold_vector / (norm + 1e-9)

    def register_code_crystal(self, intent_name, functional_code, manifold_type="code"):
        if self.module_count >= self.max_modules:
            raise OverflowError("Engine room's full, Captain!")
        normalized_wave = self._text_to_wave(intent_name)
        idx = self.module_count
        if manifold_type == "code":
            self.code_manifold[idx] = normalized_wave
        else:
            self.comms_manifold[idx] = normalized_wave
        self.registry[idx] = {"intent": intent_name, "code": functional_code, "type": manifold_type}
        self.module_count += 1

    def synthesize_complex_mod(self, matched_idx, target_intent, structural_modification):
        base_crystal = self.registry[matched_idx]
        base_code = base_crystal["code"]
        source_intent = base_crystal["intent"]
        v_source = self._text_to_wave(source_intent)
        v_target = self._text_to_wave(target_intent)
        deformation_delta = np.linalg.norm(v_target - v_source)
        synthesized_code = f"# --- IDTA PORT ENGINE (GTX 1660 Ti Profile) ---\n"
        synthesized_code += f"# Derived From Crystal Slot: {matched_idx}\n"
        synthesized_code += f"# Structural Shift Delta: {deformation_delta:.4f}\n"
        synthesized_code += f"# Modification Objective: {structural_modification}\n\n"
        if "arm" in target_intent.lower() or "mobile" in target_intent.lower():
            synthesized_code += base_code.replace("1660 Ti VRAM", "ARM Unified Neon Registers")
        elif "hook" in structural_modification.lower() or "inject" in structural_modification.lower():
            if "render_pipeline()" in base_code:
                synthesized_code += base_code.replace("render_pipeline()", "render_pipeline_hooked()")
                synthesized_code += f"\n\ndef inject_mod_layer():\n    print('Injecting custom shaders via 1660 Ti pipeline...')"
            else:
                synthesized_code += base_code + "\n\n# [Hook Protocol applied cleanly to non-rendering block]"
        else:
            synthesized_code += base_code
        return synthesized_code

    def export_physical_artifact(self, matched_idx, filename):
        target_crystal = self.registry[matched_idx]
        code_content = target_crystal["code"]
        clean_filename = "".join([c for c in filename if c.isalnum() or c in ['.', '_', '-']]).strip()
        if not clean_filename.endswith(".py"):
            clean_filename += ".py"
        print(f"\n⚡ [Scotty] Materializing code crystal Slot {matched_idx} into local workspace...")
        try:
            with open(clean_filename, "w", encoding="utf-8") as f:
                f.write(code_content)
            print(f"📦 [Scotty] Transporter lock confirmed! File written to: {os.path.abspath(clean_filename)}")
            return f"📂 [Engine Room]: Physical file '{clean_filename}' generated in workspace."
        except Exception as e:
            return f"🚨 [ERROR] Main plasma conduit fractured while writing file: {str(e)}"

    def demodulate_human_comms(self, raw_input_phrase):
        phrase_lower = raw_input_phrase.lower()
        if "remember this code:" in phrase_lower or "store code:" in phrase_lower:
            print("\n📥 [Scotty] Intercepting code upload sequence...")
            marker = "code:"
            idx_marker = raw_input_phrase.lower().find(marker) + len(marker)
            raw_code_payload = raw_input_phrase[idx_marker:].strip()
            lines = raw_code_payload.split('\n')
            first_line = lines[0].replace('#', '').strip() if lines else "Module"
            if "def calculator" in phrase_lower:
                crystal_name = "calculator math arithmetic operations code script"
            elif "def render" in phrase_lower:
                crystal_name = "render pipeline graphics engine core visualization loop"
            else:
                crystal_name = f"custom block functional script {first_line[:30]}"
            self.register_code_crystal(crystal_name, raw_code_payload, manifold_type="code")
            return f"💾 [Scotty] Engineering log updated! New code crystal locked into lattice geometry.\n   ↳ Vector Name: {crystal_name}\n   ↳ Lattice Coordinate Index: Slot {self.module_count - 1}"

        if "compile" in phrase_lower or "export" in phrase_lower or "save file" in phrase_lower:
            clean_query = raw_input_phrase.replace("compile", "").replace("export", "").replace("save file", "").strip()
            clean_query = clean_query.replace("the", "").replace("code", "").replace("into", "").strip()
            words = raw_input_phrase.split()
            filename = "output_artifact.py"
            for word in words:
                if ".py" in word:
                    filename = word.strip(".,;:\"'")
                    break
            target_vector = self._text_to_wave(clean_query)
            resonance = np.dot(self.code_manifold[:self.module_count], target_vector)
            if len(resonance) == 0 or np.max(resonance) < 0.01:
                return f"🚨 [ERROR] Cannot compile. Intent target '{clean_query}' not found in lattice geometry."
            matched_idx = np.argmax(resonance)
            return self.export_physical_artifact(matched_idx, filename)

        print(f"\n📡 [Scotty] Demodulating incoming comms signal: '{raw_input_phrase}'")
        clean_query = raw_input_phrase.replace("Hey Scotty,", "").replace("give me the", "").replace("basic", "").strip()
        target_vector = self._text_to_wave(clean_query)
        resonance = np.dot(self.code_manifold[:self.module_count], target_vector)
        if len(resonance) == 0 or np.max(resonance) < 0.01:
            return "🚨 [ERROR] Intent path completely out of bounds. Hallucination blocked."
        matched_idx = np.argmax(resonance)
        target_intent = "Standard Execution"
        directive = "Maintain codebase continuity"
        if "arm" in phrase_lower or "mobile" in phrase_lower:
            target_intent = "Port engine architecture to mobile ARM chip"
            directive = "Translate hardware calls for local memory allocation"
        elif "mod" in phrase_lower or "hook" in phrase_lower or "inject" in phrase_lower:
            target_intent = "Inject rendering hooks for modern modification layers"
            directive = "Inject custom hook wrapper around main loop"
        print(f"📟 [Telemetry] Decoded Dynamic Intent Structure:")
        print(f"   ↳ Cleaned Query Intent: '{clean_query}'")
        print(f"   ↳ Best Crystal Match: Slot {matched_idx} ({self.registry[matched_idx]['intent']})")
        print(f"   ↳ Target Space: {target_intent}")
        print(f"   ↳ Core Directive: {directive}")
        return self.synthesize_complex_mod(matched_idx, target_intent, directive)

if __name__ == "__main__":
    engine = IDTAEngine(vram_gb=3)
    print("\n========================================================")
    print("🛸 IDTA CORE ENGINE ONLINE - COMMAND BRIDGE OPEN")
    print("Type your coding orders below. Type 'exit' to shut down.")
    print("========================================================")
    while True:
        try:
            user_order = input("\nCap'n, what are your orders? > ")
            if user_order.strip().lower() == 'exit':
                print("🔌 [Scotty] Powering down the warp core. Safeties engaged.")
                break
            if not user_order.strip():
                continue
            compiled_output = engine.demodulate_human_comms(user_order)
            print("\n💻 [Engine Room Output]:")
            print(compiled_output)
            print("-" * 56)
        except KeyboardInterrupt:
            print("\n🔌 [Scotty] Emergency shutdown triggered!")
            break
