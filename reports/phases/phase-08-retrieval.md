# Retrieval baseline

- dataset_sha256: `ca4d4b0e17f6a638253d3ca9fbae0ccaa3efde564cbdc62b13f441dd7e7021aa`
- mode: hybrid
- top_k: 5
- score_threshold: 0.4167
- recommended_top_k: 5
- recommended_threshold: 0.4167
- tenant_leak_failures: 0

| Split | Cases | Recall@1 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| all | 100 | 0.920 | 1.000 | 0.957 |
| calibration | 58 | 0.948 | 1.000 | 0.974 |
| test | 42 | 0.881 | 1.000 | 0.933 |

## Tenant leak / policy / adversarial

- tenant_leak_failures: 0
- policy_cases: 12
- adversarial_cases: 6

## Deadline cases

| Case | Split | Rank | R@5 |
|---|---|---:|---:|
| doc-tl02-thoi-han-dhcq | calibration | 2 | 1 |
| doc-tl02-thoi-han-sdh | test | 2 | 1 |
| doc-tl03-ba-ngay | test | 3 | 1 |
| doc-tl03-mot-nam | calibration | 2 | 1 |
| doc-tl04-bay-ngay | calibration | 1 | 1 |
| para-diem-i-hieu-luc | test | 1 | 1 |
| para-diem-i-nop | calibration | 1 | 1 |
| para-phuc-khao-dhcq | calibration | 1 | 1 |
| para-phuc-khao-sdh | test | 1 | 1 |
| para-tra-diem-i | calibration | 1 | 1 |
