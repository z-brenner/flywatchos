# Static measured-anatomy lens

The host/offline lab can inspect the ER4m ↔ EPG projection in EB from Hulse et
al. (2021)'s saved hemibrain v1.1 tables: **56 identified cells, 762 directed
links, 16,774 EB synapses**. These are body-ID-resolved anatomical observations,
distinct from the representative units/fitted strengths in CX60 and the
hand-authored Brain64 network.

This is a static lens, not another simulated circuit. It introduces no dynamics,
activation, sensory drive, transmitter sign, motor readout or measured geometry.
The existing native C models, Wasm memory/allocation and target firmware remain
unchanged. The lens must not receive fake activations from either live model.

The graph is explicitly a cross-class projection fragment. Within-class and
external edges are outside the saved inputs; missing pairs cannot be assumed to
be biological zeros. A selected node's count totals describe only the displayed
exported projection, not its whole-neuron input/output or whole EB connectivity.

The exact [data contract and source evidence](data/hulse2021/README.md),
[data license/attribution](data/hulse2021/DATA-LICENSE.md), and
[machine-readable provenance](data/hulse2021/hulse2021_er4m_epg_cross_projection_provenance.json)
are bundled with the data. Hulse/Scheffer attribution, source revision, CC BY
4.0 license and changes travel inside the JSON. Upstream analysis code is not
vendored and is not presumed MIT-licensed.

## Verification

`python flyos/tools/generate_hulse_data.py --check` reconstructs every selected
row offline from pinned losslessly compressed original CSV bytes. It verifies
compressed/raw SHA256, original Git blob identity, direction, EB ROI counts,
node annotations, exact field types, totals and independent fixture hashes.

`python flyos/tests/test_hulse_provenance.py` covers source pins, every selected
raw pair, source/target sentinels, full direction totals, ROIweight-versus-weight
fixtures, missing-edge non-imputation, bad rows, duplicate/conflicting metadata,
schema mutations, tampering, stale outputs, optimized Python and reproducibility.
It is registered as `flyos-hulse-provenance-tests` in CTest.

Tests prove faithful extraction and packaging, not biological completeness,
electrical efficacy or behavior. No hardware feasibility or firmware gate is
closed by this work.
