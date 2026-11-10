# Retrieval baseline

- dataset_sha256: `1423dd9acfb2087e715880edeb19e9ffed780967b55258f52bcfca3f35ff1f52`
- mode: hybrid
- top_k: 5
- score_threshold: 0.0
- recommended_top_k: 5
- recommended_threshold: 0.4167
- tenant_leak_failures: 0

| Split | Cases | Recall@1 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| all | 97 | 0.928 | 1.000 | 0.960 |
| calibration | 58 | 0.966 | 1.000 | 0.983 |
| test | 39 | 0.872 | 1.000 | 0.927 |

## Dense-only Recall@5

- all: 0.969
- calibration: 0.983
- test: 0.949

## Tenant leak / policy / adversarial

- tenant_leak_failures: 0
- policy_cases: 11
- adversarial_cases: 5

## Deadline cases

| Case | Split | Rank | R@5 |
|---|---|---:|---:|
| doc-tl02-thoi-han-dhcq | calibration | 2 | 1 |
| doc-tl02-thoi-han-sdh | test | 2 | 1 |
| doc-tl03-ba-ngay | test | 3 | 1 |
| doc-tl03-mot-nam | calibration | 1 | 1 |
| doc-tl04-bay-ngay | calibration | 1 | 1 |
| para-diem-i-hieu-luc | test | 1 | 1 |
| para-diem-i-nop | calibration | 1 | 1 |
| para-phuc-khao-dhcq | calibration | 1 | 1 |
| para-phuc-khao-sdh | test | 1 | 1 |
| para-tra-diem-i | calibration | 1 | 1 |
