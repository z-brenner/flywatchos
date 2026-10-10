# Hulse 2021: measured ER4m / EPG EB projection data

This is a **static anatomical data bundle** for the host/offline lab. It contains
56 identified cells (46 EPG, 10 ER4m), 762 directed cross-class connections, and
16,774 EB synapses selected from two saved tables. It supplies no neural dynamics,
activation values, synaptic signs, geometry, or firmware data structures.

## Source and attribution

- Hulse et al. (2021), *A connectome of the Drosophila central complex reveals
  network motifs suitable for flexible navigation and context-dependent action
  selection*, eLife 10:e66039. <https://doi.org/10.7554/eLife.66039>
- Scheffer et al. (2020), *A connectome and analysis of the adult Drosophila
  central brain*, eLife 9:e57443. <https://doi.org/10.7554/eLife.57443>
- Original data: HHMI/Janelia FlyEM and the original research teams.
- Saved analysis tables: `jayaraman-lab/CX-connectome-analysis`, revision
  `5c7a57256c15ea763e4cf0a7cf686ba0d3342d80`.
  [Pinned source directory](https://github.com/jayaraman-lab/CX-connectome-analysis/tree/5c7a57256c15ea763e4cf0a7cf686ba0d3342d80/EBFigures/modularityAnalysis)

The [upstream README](https://github.com/jayaraman-lab/CX-connectome-analysis/blob/5c7a57256c15ea763e4cf0a7cf686ba0d3342d80/README.md)
identifies hemibrain v1.1 as the database used for the paper's figures. These are
the pinned **saved exports**, not a fresh query against today's neuPrint release.
The [upstream modularity analysis](https://github.com/jayaraman-lab/CX-connectome-analysis/blob/5c7a57256c15ea763e4cf0a7cf686ba0d3342d80/EBFigures/modularityAnalysis/computeModularity.m)
selects `er2epg.csv` for ring-neuron inputs to EPG and `epg2erEB.csv` for the reverse
direction, and provides `ROIweight` as its synaptic-count option. That code was
inspected for provenance only; it is not copied or required here.

Underlying hemibrain data is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
as linked by [Janelia's hemibrain page](https://www.janelia.org/project-team/flyem/hemibrain).
See [DATA-LICENSE.md](DATA-LICENSE.md). The complete pinned repository tree was
checked on 2026-10-10: no standalone LICENSE, COPYING or NOTICE file was found.
Do not infer an MIT license for that repository's analysis code. This directory
vendors data only; the new extractor is independently written FlyWatchOS code.

## Exact selection and meaning

Every row whose `databaseType.from` and `databaseType.to` are ER4m and EPG in
either direction is selected. Selected rows must have `roi == EB` and positive
integer `ROIweight`. There is no top-N selection or additional count threshold.

| Source export | Original rows | Selected direction | Selected rows | EB synapses |
|---|---:|---|---:|---:|
| `er2epg.csv` | 8,755 | ER4m → EPG | 460 | 14,903 |
| `epg2erEB.csv` | 621 | EPG → ER4m | 302 | 1,871 |

`from` is the presynaptic/source body ID; `to` is the postsynaptic/target body ID.
`ROIweight` is the EB synapse count. Whole-neuron `weight` and relative-weight
columns are not used, even where their values happen to equal `ROIweight` in
this class-pair selection. Repeated directed pairs or conflicting endpoint
annotations fail validation rather than being summed, overwritten or relabeled.

This is a **cross-class projection fragment**, not a complete induced subgraph:
within-class and external connections are omitted by the two source tables.
Of the 920 mathematically possible directed cross-class pairs among these cells,
158 have no exported row. They remain absent; that absence is not evidence for
zero biological synapses. The saved exports alone do not establish exhaustiveness
of the original queries or biological completeness.

Counts are anatomy, not electrical efficacy. No excitatory/inhibitory sign,
firing rate, heading angle, visual tuning, learning or behavior follows from this
bundle. Any displayed layout is schematic, not measured geometry. In particular,
instance names remain source annotations and are not converted into headings.

## Files and reproducibility

- `hulse_er2epg.csv.gz` and `hulse_epg2erEB.csv.gz`: lossless gzip storage of the
  exact original CSV bytes (2,067,645 and 145,689 bytes after decompression).
  The gzip header contains no filename or timestamp (`mtime=0`). Storage totals
  274,576 bytes. Both compressed and decompressed byte counts/SHA256 are pinned,
  as are the original Git blob SHA1 values independently checked against GitHub.
- `hulse2021_er4m_epg_anatomy.json`: standalone indexed UI payload, carrying full
  attribution, license links, source revision, changes, boundary and limitations.
- `hulse2021_er4m_epg_cross_projection_nodes.json`: identity fixture, sorted by
  class then numeric body ID, byte-identical to the independently vetted selection.
- `hulse2021_er4m_epg_cross_projection_edges.csv`: explicit directed body-ID
  fixture, sorted by numeric source then target; preserves the vetted CRLF bytes.
- `hulse2021_er4m_epg_cross_projection_provenance.json`: source locations, raw and
  storage pins, extraction/evidence notes and derived artifact sizes/SHA256.

From the repository root, with Python 3 standard library only:

```sh
python flyos/tools/generate_hulse_data.py --check
python flyos/tests/test_hulse_provenance.py
```

To regenerate the four derived artifacts from the compressed raw inputs:

```sh
python flyos/tools/generate_hulse_data.py
```

No network, credentials, MATLAB, R, SciPy or package installation is needed.
Source verification completes before writes. `--check` never writes. All
validation stays active with `python -O`; no `assert` is used in the extractor.
JSON is explicitly encoded UTF-8 with LF, and Git attributes preserve all pinned
CSV/gzip bytes. Regeneration verifies the independently vetted node/edge fixture
hashes as well as the raw source pins.

## Indexed JSON contract, schema version 1

Top-level fields are exactly `schema_version`, `metadata`, `nodes`, and `links`.
`metadata` has exactly the pinned source/license/interpretation fields emitted by
`metadata()` in the extractor. Totals and directions are reconciled against the
records, and provenance metadata must match the contract exactly.

Each node has exactly:

- `body_id`: positive decimal **string**, never narrowed to a 32-bit integer.
- `class`: `EPG` or `ER4m`, copied from the `databaseType` columns.
- `instance`: original `name` column, e.g. `EPG(PB08)_L3` or `ER4m(ring)_R`.

The indexed node array is sorted by numeric body ID. Equal instance names can
identify distinct cells, so identity is always the body ID, not the instance.

Each link has exactly:

- `source`: zero-based integer index into `nodes`, from the source `from` column.
- `target`: zero-based integer index into `nodes`, from the source `to` column.
- `count`: positive integer EB `ROIweight`, bounded as an unsigned 32-bit count.

Links are sorted by source index then target index. No duplicates, out-of-range
indices, within-class edges, signed counts, float counts, boolean counts, or
extra fields such as activation/angle/sign are accepted. `validate_anatomy()`
implements the strict offline contract. Array order is storage order only,
never an anatomical coordinate. No C or Wasm model reads these files.
