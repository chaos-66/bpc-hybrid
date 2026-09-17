# SEP-C3 full 2^3 protocol audit (zero network)

- status: **pass**
- suite: `SEP-C3-MODULAR-ESJ-002`
- existing cells: `111/011/101/110` (original execution binding)
- new cells: `000/001/010/100` (prepared_not_run)
- model: `deepseek-v4-pro` (DeepSeek-V4-Pro-0813)
- denominator: 150 per arm

| variant | E | S | J | prompt SHA256 | status |
|---|---:|---:|---:|---|---|
| 111 | 1 | 1 | 1 | `38144b7525c9ffddd001a276f6533ac4c35060b7917ae363e56a11c25824e1f3` | existing_executed |
| 011 | 0 | 1 | 1 | `d71fd965458cc0de8b4d4c5921ad3f905ed3c4b7cdc8ea70ff7955c43d042136` | existing_executed |
| 101 | 1 | 0 | 1 | `00f0ea3fc2ddf2ef7c765a83f05aa4f64eeba89966a2010c8e3a05151a111891` | existing_executed |
| 110 | 1 | 1 | 0 | `75ce93f718a7d24962a33cef95a91515261d3a69789d64d4728a838670962fd9` | existing_executed |
| 100 | 1 | 0 | 0 | `9ce3502ea56c14a58bb39d87ab7b7023c5aca51b65909a515c0244601a5b7fee` | prepared_not_run |
| 010 | 0 | 1 | 0 | `de3e33eeec7bedd22bb4df195c8353b15f6ef67dca2f4bd911ee5053cb403305` | prepared_not_run |
| 001 | 0 | 0 | 1 | `f03d5ad274df8e64b0c555559a412e09e56c59afa3e5ab39693088ebc010913c` | prepared_not_run |
| 000 | 0 | 0 | 0 | `45bb324dd1143e1f920e9f8935ed8ecda98c8ebe5a1442ec10f9843b50abdefa` | prepared_not_run |

## Batch warning

The original 111/011/101/110 cells were executed in the earlier SEP-C3-MODULAR-ESJ-001 batch; 000/001/010/100 will be a later incremental batch. Model/release/prompt/evaluator settings are matched, but batch/time is confounded with the factorial cells if the eight cells are pooled without acknowledging this.
