# S3.9-EXT gap comparison v1 (development-only, frozen 80-instance panel)

Panel: `data/development/stage3_synth/synthetic_controlled_error_extension_v2.json` (40 variants + 40 controls), `gamma_ext = 0.5`. Zero API. Not human Gold, not the formal Oracle.

## A. 40 mutated variants

| arm | matching path | action gamma | correct | wrong type | abstained | explicitly compliant | 4-type macro-F1 |
|---|---|---|---|---|---|---|---|
| Winter-style extension (frozen) | original label argmax on raw label text | 0.4 | 17 | 9 | 18* | n/a* | 0.4738 |
| Sun-style extension (frozen) | original label argmax on raw label text | 0.8 | 10 | 1 | 30* | n/a* | 0.2381 |
| original path + 0.4 (re-derived) | original label argmax on raw label text | 0.4 | 17 | 9 | 12 | 2 | 0.4738 |
| v3 matching path + 0.8 (existing) | v3 structured action match | 0.8 | 10 | 2 | 26 | 2 | 0.2273 |
| v3 matching path + 0.4 (diagnostic) | v3 structured action match | 0.4 | 10 | 2 | 26 | 2 | 0.2273 |
| v3 matching path + 0.4 repaired (final) | v3 match + one action resolution | 0.4 | 19 | 9 | 10 | 2 | 0.5233 |

`*` the frozen Winter-style and Sun-style blocks are reported verbatim from the frozen report; the frozen evaluator counts an explicitly compliant variant prediction inside its `unobservable` field, so those two rows have no separate false-compliance column. The re-derived and new arms split abstention from explicit compliance.

### Per-type P/R/F1 (variants)

| arm | prohibited | condition | constraint | exception |
|---|---|---|---|---|
| Winter-style extension (frozen) | 0.909/1.000/0.952 | 0.286/0.200/0.235 | 0.600/0.300/0.400 | 0.667/0.200/0.308 |
| Sun-style extension (frozen) | 0.909/1.000/0.952 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| original path + 0.4 (re-derived) | 0.909/1.000/0.952 | 0.286/0.200/0.235 | 0.600/0.300/0.400 | 0.667/0.200/0.308 |
| v3 matching path + 0.8 (existing) | 0.833/1.000/0.909 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| v3 matching path + 0.4 (diagnostic) | 0.833/1.000/0.909 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| v3 matching path + 0.4 repaired (final) | 0.909/1.000/0.952 | 0.375/0.300/0.333 | 0.667/0.400/0.500 | 0.667/0.200/0.308 |

## B. 40 compliant controls

| arm | false positives | explicitly compliant | abstained | FP rate |
|---|---|---|---|---|
| Winter-style extension (frozen) | 20 | 12 | 8 | 0.5000 |
| Sun-style extension (frozen) | 5 | 9 | 26 | 0.1250 |
| original path + 0.4 (re-derived) | 20 | 12 | 8 | 0.5000 |
| v3 matching path + 0.8 (existing) | 8 | 6 | 26 | 0.2000 |
| v3 matching path + 0.4 (diagnostic) | 8 | 6 | 26 | 0.2000 |
| v3 matching path + 0.4 repaired (final) | 20 | 14 | 6 | 0.5000 |

## C. 40 pairs

| arm | both sides correct | paired accuracy |
|---|---|---|
| Winter-style extension (frozen) | 9 | 0.2250 |
| Sun-style extension (frozen) | 7 | 0.1750 |
| original path + 0.4 (re-derived) | 9 | 0.2250 |
| v3 matching path + 0.8 (existing) | 4 | 0.1000 |
| v3 matching path + 0.4 (diagnostic) | 4 | 0.1000 |
| v3 matching path + 0.4 repaired (final) | 11 | 0.2750 |

## D. merged 80 objects (five classes, reported separately)

| arm | 5-class accuracy | 4-type macro-F1 | 5-class macro-F1 |
|---|---|---|---|
| Winter-style extension (frozen) | 0.3625 | 0.3764 | 0.3900 |
| Sun-style extension (frozen) | 0.2375 | 0.1923 | 0.2231 |
| original path + 0.4 (re-derived) | 0.3625 | 0.3764 | 0.3900 |
| v3 matching path + 0.8 (existing) | 0.2000 | 0.1667 | 0.1833 |
| v3 matching path + 0.4 (diagnostic) | 0.2000 | 0.1667 | 0.1833 |
| v3 matching path + 0.4 repaired (final) | 0.4125 | 0.4145 | 0.4316 |

## Count identities

- **Winter-style extension (frozen)**: variants 17 + 9 + 18 (incl. explicit compliance) = 40; controls 12 + 20 + 8 = 40.
- **Sun-style extension (frozen)**: variants 10 + 1 + 30 (incl. explicit compliance) = 40; controls 9 + 5 + 26 = 40.
- **original path + 0.4 (re-derived)**: variants 17 + 9 + 12 + 2 = 40; controls 12 + 20 + 8 = 40.
- **v3 matching path + 0.8 (existing)**: variants 10 + 2 + 26 + 2 = 40; controls 6 + 8 + 26 = 40.
- **v3 matching path + 0.4 (diagnostic)**: variants 10 + 2 + 26 + 2 = 40; controls 6 + 8 + 26 = 40.
- **v3 matching path + 0.4 repaired (final)**: variants 19 + 9 + 10 + 2 = 40; controls 14 + 20 + 6 = 40.

## Sources

- `winter_frozen`: `outputs/reports/s3_formula_repair_v2.json` `18fa61ae9dda8c10`
- `sun_frozen`: `outputs/reports/s3_formula_repair_v2.json` `08095d984a860503`
- `orig_04_rederived`: `outputs/development/s3_extended_baseline_04_v1` `44affe2d0e5c041e`
- `v3_08_existing`: `outputs/development/s3_extended_v3_v1` `4a3056aed1331f78`
- `v3_04_diagnostic`: `outputs/development/s3_extended_v3_gamma04_v1` `fea10b84fcc249f5`
- `v3_04_repaired`: `outputs/development/s3_extended_v3_repair_v1` `797792ba46076318`

- every arm is reported on the same 40 variants / 40 controls / 80 objects; no sample is dropped
- a control abstention is NOT counted as a correct rejection
- the frozen Winter-style and Sun-style blocks are read from the frozen report and never re-run
- the original path + 0.4 cell is re-derived in the current code state and reproduces the frozen Winter-style arm on every decision-relevant field
- the two v3 cells at 0.8 and 0.4 hold identical predictions; they differ only in the recorded action gamma
- the D view is not the A view: it mixes 40 violation objects with 40 compliant objects
