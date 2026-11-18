# Static analysis and disc inventory

| Input | Analysis | Disc inventory |
| --- | --- | --- |
| NTSC-U `SLUS-00643`, FullRUS | [Function map and analysis](ntsc-u-slus-00643/) | [FullRUS inventory](disc_fullrus.json) |
| PAL `SLES-01417`, Europe | [Function map and analysis](pal-sles-01417/) | [Europe inventory](disc_europe.json) |

Each analysis directory contains the analyzer's function table, call edges,
data references, indirect sites and widescreen candidates. The candidates are
heuristic findings from static analysis and still need runtime verification.

The disc inventories record CUE track counts, checksums and ISO 9660 paths,
sizes and sector positions. They include comparisons to the stock USA Track 01
checksum, so hash mismatches are expected for these variants.
