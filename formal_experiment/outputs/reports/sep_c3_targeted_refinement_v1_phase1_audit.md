# SEP-C3 targeted refinement Phase 1 audit

Status: **pass** (zero model/API calls).

## Deliverables

1. Implementation: `src/bpc_hybrid/modular_refinement_prompt.py`; frozen repair files under `prompts/sun_compat/modular_refinement_v1/`; build/audit script `scripts/build_sep_c3_targeted_refinement_v1.py`.
2. Rendered prompts: `prompts/sun_compat/modular_refinement_v1/generated/direct_llm_refinement_{A,B,C,D}_v1.md` and `generated/manifest.json`.
3. Deterministic sent-prompt diffs: `outputs/reports/sep_c3_targeted_refinement_v1_prompt_diffs/`.
4. Prompt audit: `outputs/reports/sep_c3_targeted_refinement_v1_prompt_audit.json`.
5. Config diff: `outputs/reports/sep_c3_targeted_refinement_v1_config_diff.json` (status `pass`).
6. Schedule: `configs/sep_c3_targeted_refinement_schedule_v1.json`, sha256 `63cd957f9ff4d3261dfcf407fac207fad910ca67b521f9b0b549737b80ac94ca`, scheme `sample_level`.
7. Budget: `configs/sep_c3_targeted_refinement_budget_v1.json`.
8. Prepared runner: `scripts/run_sep_c3_targeted_refinement_v1.py`.
9. Expected output directory: `outputs/development/sep_c3_targeted_refinement_v1/`.
10. Interleaving: supported at sample level: 150 blocks x 4 arms, order saved before runs; runner refuses mismatched schedule hash.

## Prompt hashes

| arm | system sha256 | user sha256 | composition sha256 | generated file sha256 |
|---|---|---|---|---|
| A | `9db8893c75af4c306f5f5142ea77b6c93b6a2bae79a72ba8dd0f2b3ca1985d4f` | `fb92bd110d33c22208f36816139871b6ec4f0f818e6fd731c60c5c321510abfb` | `f41d903bb86f8199499f3eb95d19042a5c321a5a06be3c38a0a04a8bfd8d2418` | `d24c0c0d5150dd6382260f91614cc6d475ecdb68efb2cfe8d48347272d74a580` |
| B | `f6de5c4fe6115d5073f44e59d98443ccec5dd55bc3356ce445b6304a82aab778` | `fb92bd110d33c22208f36816139871b6ec4f0f818e6fd731c60c5c321510abfb` | `207b54cc2f1123c7511451d7ead478654e550d438fe19d1031a13149b41917f1` | `c468c631b6e454522994d6839f6a4021a259daedea7f3a2852b7b4343cd22849` |
| C | `19af79caa77ea3e600b7894603da59a278a059b0c2a6bd5f1c5038fb704445fc` | `fb92bd110d33c22208f36816139871b6ec4f0f818e6fd731c60c5c321510abfb` | `a015da8e3f08c561050b0de1604163a6aba5a0a8d1a60e4fe8c56bd3e2eb2266` | `d58163b677c6a7bda06f4de3ea8de743d8568e0d5e2c740bdea8af48ccfa4479` |
| D | `af33cf308c98ae2bb03572d0669913b1dcb58310a4c08050e21f853d171e29b4` | `fb92bd110d33c22208f36816139871b6ec4f0f818e6fd731c60c5c321510abfb` | `7901ebe541abe25fe2753db514b284a82c4d37c54535ad54824eac597fff15c9` | `b241126dcb04001872e3bfd60deb330ed884ccad50537cc2031017a66835c091` |

Frozen `100` baseline composition sha256: `f41d903bb86f8199499f3eb95d19042a5c321a5a06be3c38a0a04a8bfd8d2418`.

## Audit answer

**否** — 除 R_A / R_C 外，四个 arms 未检测到任何非预期差异。

All common markers, source envelope rendering, E bytes, schema/interface text, and sampling/config bindings are either byte-identical to the frozen `100` baseline or differ only by the frozen repair paragraph(s). S and J are absent from every arm.

## Expected Phase 2 commands

```powershell
python formal_experiment/scripts/build_sep_c3_targeted_refinement_v1.py --write --overwrite --check
python formal_experiment/scripts/prepare_sep_c3_targeted_refinement_v1.py --prepare --check
python formal_experiment/scripts/run_sep_c3_targeted_refinement_v1.py --check
# Real 600-call run (only after explicit API authorization for this task):
python formal_experiment/scripts/run_sep_c3_targeted_refinement_v1.py --execute --allow-llm --project-env
```
