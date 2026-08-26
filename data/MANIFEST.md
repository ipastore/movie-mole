# Source manifest — pinned inputs

Ingestion **verifies every hash below before running** and aborts on mismatch.
IMDb republishes daily; MovieLens `ml-latest` is a rolling development dataset.
Reproducibility is only meaningful against these exact bytes.

## MovieLens ml-latest — release 2023-07-20

| File | Bytes | SHA-256 |
|---|---:|---|
| `genome-scores.csv` | 521514541 | `72a2d7460f30b2f3ac68bdda9e46c8320a8019faf1a7b7b79aa0e9d794902b86` |
| `genome-tags.csv` | 18103 | `c84bf1e2addbf38432426a2bb2a117a59d76c0873fc875fe8764e92842fd3bfb` |
| `links.csv` | 1925962 | `92f18202228071d5dc56a5bc7fd7ccbd06ff355c54bc48e55a059cd4896966d7` |
| `movies.csv` | 4192335 | `dd78a76a44b5ff159e66571992bac5208255f86c1a3acbbe7fcd9bbb29d87b3c` |
| `ratings.csv` | 933898879 | `ae77c01e7c895e7d61ba3594a1c5ff191b5f7f3a9d788000315a463322fa44f6` |
| `tags.csv` | 85361813 | `d485c3fff0c4b4c215ef3c213ba0b68748e805ac0f07dcba2369582b7343bd0b` |

## IMDb non-commercial — downloaded 2026-08-26

| File | Bytes | SHA-256 |
|---|---:|---|
| `name.basics.tsv.gz` | 308727999 | `5ceafcf872c0ed1bf41569c543377d9f2fb38075cd52ebc92ea1ebadb0f02fe4` |
| `title.akas.tsv.gz` | 511873631 | `0c44f2e10b7782a9b77c7a053d36c33b28a59edcb7cb6d88dbe677a8a6d21c0a` |
| `title.basics.tsv.gz` | 225992791 | `6d4a21475e09cc95638ffe8627beb4a28bf55273ba915eeb582cfb38fa1d531b` |
| `title.crew.tsv.gz` | 82856343 | `efc1f819f3cf0211aac3f4a326839cfdcd5615c8f7a2c54335aceda6f5b0389c` |
| `title.principals.tsv.gz` | 780361595 | `30f2f2e116987d1bf005c7b8d34b7e406e5177c45228b07f1ebba0e1e7e3cde3` |
| `title.ratings.tsv.gz` | 8635427 | `e6cdd3c02381eb30618720d314f063d3fc16946442d95d41d2661751edbbe9b8` |
