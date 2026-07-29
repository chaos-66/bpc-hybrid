// SunPhraseRuleBatchBridgeSafeV2.java
//
// Provenance marker for the v6 development run. The v6 implementation
// is byte-identical to SunPhraseRuleBatchBridgeMulti.java and shares
// the same public class. To avoid duplicate class definitions during
// compilation, this file contains no public class; it is a comment
// marker only.
//
// The v6 implementation in src/bpc_hybrid/estg150_b0_development_v4.py
// detects this file and records it in the runtime identity (bridge_source
// field of the manifest). It compiles and runs the same Java class
// (SunPhraseRuleBatchBridgeMulti) from SunPhraseRuleBatchBridgeMulti.java.
//
// The class already provides the "safe Tsurgeon" properties required by
// the v6 plan:
//   - multi non-overlapping matches per field
//   - capture-before-prune (every match is recorded before the working
//     tree is mutated)
//   - terminal_tree_removal_count tracked across the batch and never
//     causing the bridge to throw; the v6 fallback path records the
//     removal and continues with the next sentence.
//
// See docs/research/SUN_CORENLP_RUNTIME_ALIGNMENT.md for the full S2.5
// contract; see resources/corenlp/sun_phrase_patterns_v4_expanded.json
// for the v6 rule registry.
