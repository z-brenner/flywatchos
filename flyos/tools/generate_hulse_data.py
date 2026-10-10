#!/usr/bin/env python3
"""Re-derive the static Hulse ER4m/EPG EB projection using only Python stdlib.

No network, neuPrint login, upstream analysis code or numerical dependency is
used. --check verifies byte-identical checked-in outputs without writing. All
validation uses explicit exceptions and remains active under Python -O.
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re

DATA = Path(__file__).resolve().parents[1] / 'sim/data/hulse2021'
ANATOMY_NAME = 'hulse2021_er4m_epg_anatomy.json'
PROVENANCE_NAME = 'hulse2021_er4m_epg_cross_projection_provenance.json'
NODES_NAME = 'hulse2021_er4m_epg_cross_projection_nodes.json'
EDGES_NAME = 'hulse2021_er4m_epg_cross_projection_edges.csv'
COMMIT = '5c7a57256c15ea763e4cf0a7cf686ba0d3342d80'
REPOSITORY = 'https://github.com/jayaraman-lab/CX-connectome-analysis'
SOURCES = {
    'hulse_er2epg.csv': {
        'path': 'EBFigures/modularityAnalysis/er2epg.csv',
        'bytes': 2067645,
        'sha256': 'ceaeafa61d4aa9a3e72dce5679b00abdcdb326d489cb8dec2a7378ac2a256543',
        'git_blob_sha1': '22e86f62486c3956ebdf8d6e769dce65194bffb2',
        'raw_row_count': 8755,
        'source_class': 'ER4m', 'target_class': 'EPG',
        'selected_row_count': 460, 'selected_synapse_count': 14903,
        'storage': {'file': 'hulse_er2epg.csv.gz', 'compression': 'gzip', 'bytes': 251295,
                    'sha256': '290ffa41dc205d3cf160d4ee9b00975ecc4aea9faae6044ec1306d06bfae3b2e'},
    },
    'hulse_epg2erEB.csv': {
        'path': 'EBFigures/modularityAnalysis/epg2erEB.csv',
        'bytes': 145689,
        'sha256': '61f641d9609acffd087bc1f3ec02e1ccc78154e5dedf9eab7219b428a731a8b0',
        'git_blob_sha1': '1276bc47ad02bd05eca07575c0d591b329737d62',
        'raw_row_count': 621,
        'source_class': 'EPG', 'target_class': 'ER4m',
        'selected_row_count': 302, 'selected_synapse_count': 1871,
        'storage': {'file': 'hulse_epg2erEB.csv.gz', 'compression': 'gzip', 'bytes': 23281,
                    'sha256': 'f7036fa13a23a45bb9e4eae8b71d6faa692b4fff15cb8901d74a761cb1c14cad'},
    },
}
HEADERS = ('weight,roi,ROIweight,from,to,name.from,name.to,type.from,type.to,'
           'databaseType.to,databaseType.from,totalWeight,weightRelativeTotal,'
           'totalPreWeight,outputContributionTotal,weightROIRelativeTotal,'
           'totalPreROIweight,totalROIweight,weightRelative,outputContribution,'
           'supertype1.to,supertype1.from,supertype2.to,supertype2.from,'
           'supertype3.to,supertype3.from').split(',')
GOLDEN = {
    NODES_NAME: 'b1aa80dd687dafd32dee7f49c59c62912043914c5a1acf03047c8920ce16c385',
    EDGES_NAME: '7bb751716d2e43b1f60970f096dcc1d69462014780a136ec803824bbfef09ed8',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def metadata():
    return {
        'id': 'hulse2021-er4m-epg-eb',
        'title': 'Measured anatomy: ER4m / EPG EB projections',
        'dataset': 'Hemibrain v1.1; Hulse et al. (2021) saved EB projection tables',
        'roi': 'EB',
        'node_count': 56,
        'edge_count': 762,
        'synapse_count_sum': 16774,
        'class_counts': {'EPG': 46, 'ER4m': 10},
        'directions': [
            {'source_class': 'ER4m', 'target_class': 'EPG',
             'edge_count': 460, 'synapse_count_sum': 14903},
            {'source_class': 'EPG', 'target_class': 'ER4m',
             'edge_count': 302, 'synapse_count_sum': 1871},
        ],
        'source': {
            'paper': 'https://doi.org/10.7554/eLife.66039',
            'hemibrain_paper': 'https://doi.org/10.7554/eLife.57443',
            'repository': REPOSITORY,
            'commit': COMMIT,
            'paths': [record['path'] for record in SOURCES.values()],
        },
        'license': {
            'id': 'CC-BY-4.0',
            'url': 'https://creativecommons.org/licenses/by/4.0/',
            'source': 'https://www.janelia.org/project-team/flyem/hemibrain',
            'attribution': ('Hemibrain data: Scheffer et al. (2020), A connectome and analysis '
                            'of the adult Drosophila central brain, eLife 9:e57443. '
                            'Central-complex analysis and saved tables: Hulse et al. (2021), '
                            'A connectome of the Drosophila central complex reveals network '
                            'motifs suitable for flexible navigation and context-dependent '
                            'action selection, eLife 10:e66039. HHMI/Janelia FlyEM and '
                            'the original research teams. No endorsement is implied.'),
            'changes': ('FlyWatchOS selected every positive ER4m/EPG cross-class row in EB, '
                        'preserved body IDs, instance names, direction and ROIweight counts, '
                        'sorted by numeric body ID, and reindexed endpoints for display. '
                        'Original CSV bytes are preserved in gzip files; no biological weights '
                        'were fitted, normalized or assigned a sign.'),
            'repository_code_license': ('No standalone analysis-repository code license was '
                                        'identified at the pinned commit. No upstream analysis '
                                        'code is copied or required; CC BY 4.0 here describes '
                                        'the underlying hemibrain data, not a code license.'),
        },
        'boundary': ('A cross-class projection fragment from two saved tables; '
                     'not a complete induced subgraph, heading circuit or whole brain.'),
        'limitations': [
            'Within-class and external connections are omitted by these input tables.',
            'A missing row is not evidence of a zero-synapse biological connection; no missing edges are filled with zero.',
            'Counts are unsigned EB ROIweight synapse counts, not measured electrical efficacy or synaptic sign.',
            'Body IDs and instance labels identify source annotations; layout is schematic, not measured geometry or EPG heading angles.',
            'This static anatomical lens supplies no activation, dynamics, sensory tuning, learning or behavior model.',
            'The two saved exports do not by themselves establish completeness or an exhaustive live neuPrint query.',
        ],
    }


def positive_decimal(value, label):
    require(type(value) is str and re.fullmatch(r'[1-9][0-9]*', value) is not None,
            f'{label} must be an unsigned positive decimal integer')
    return int(value)


def extract_rows(tables):
    """Return identity records and body-ID edges; never impute absent pairs.

    This low-level parser accepts in-memory CSV fixtures. Production calls
    generated(), which verifies immutable source bytes before parsing.
    """
    nodes, edges = {}, {}
    for name, contents in tables:
        reader = csv.DictReader(io.StringIO(contents, newline=''), strict=True)
        require(reader.fieldnames == HEADERS, f'{name}: unexpected source CSV columns')
        for line, row in enumerate(reader, 2):
            label = f'{name}:{line}'
            require(set(row) == set(HEADERS) and all(v is not None for v in row.values()),
                    f'{label}: malformed source row')
            classes = row['databaseType.from'], row['databaseType.to']
            if set(classes) != {'ER4m', 'EPG'}:
                continue
            require(row['roi'] == 'EB', f'{label}: selected row is outside EB')
            count = positive_decimal(row['ROIweight'], f'{label} ROIweight')
            require(count <= 2**32-1, f'{label}: ROIweight exceeds unsigned 32-bit count')
            pair = row['from'], row['to']
            require(pair not in edges, f'{label}: duplicate directed body-ID pair')
            for side, body_id, cell_class in zip(('from', 'to'), pair, classes):
                positive_decimal(body_id, f'{label} {side} body ID')
                instance = row[f'name.{side}']
                pattern = (r'EPG\(PB08\)_[LR][1-8]' if cell_class == 'EPG'
                           else r'ER4m\(ring\)_[LR]')
                require(re.fullmatch(pattern, instance) is not None,
                        f'{label}: invalid instance for {cell_class}')
                require(row[f'type.{side}'] == cell_class + '_' + instance.split('_')[1][0],
                        f'{label}: type annotation conflicts with instance/class')
                node = {'body_id': body_id, 'class': cell_class, 'instance': instance}
                require(body_id not in nodes or nodes[body_id] == node,
                        f'{label}: conflicting annotations for body ID {body_id}')
                nodes[body_id] = node
            edges[pair] = {'source_body_id': pair[0], 'target_body_id': pair[1],
                           'neuropil': 'EB', 'synapse_count': count, 'source_export': name}
    return ([nodes[body_id] for body_id in sorted(nodes, key=int)],
            [edges[pair] for pair in sorted(edges, key=lambda p: (int(p[0]), int(p[1])))])


def exact_keys(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), f'{label}: unexpected schema fields')


def validate_anatomy(document):
    """Strict v1 contract, including scientific totals and projection boundary."""
    exact_keys(document, ('schema_version', 'metadata', 'nodes', 'links'), 'anatomy')
    require(type(document['schema_version']) is int and document['schema_version'] == 1,
            'unsupported anatomy schema version')
    # Serialized comparison enforces types too (Python equality equates True/1).
    require(json.dumps(document['metadata'], sort_keys=True, allow_nan=False) ==
            json.dumps(metadata(), sort_keys=True), 'anatomy metadata differs from pinned contract')
    nodes, links = document['nodes'], document['links']
    require(type(nodes) is list and len(nodes) == 56, 'anatomy must contain 56 cells')
    require(type(links) is list and len(links) == 762, 'anatomy must contain 762 directed links')
    seen_ids, classes = set(), Counter()
    for node in nodes:
        exact_keys(node, ('body_id', 'class', 'instance'), 'node')
        positive_decimal(node['body_id'], 'node body ID')
        require(node['body_id'] not in seen_ids, 'duplicate anatomy body ID')
        seen_ids.add(node['body_id'])
        require(node['class'] in ('EPG', 'ER4m'), 'unknown cell class')
        pattern = (r'EPG\(PB08\)_[LR][1-8]' if node['class'] == 'EPG'
                   else r'ER4m\(ring\)_[LR]')
        require(type(node['instance']) is str and re.fullmatch(pattern, node['instance']) is not None,
                'invalid anatomy instance')
        classes[node['class']] += 1
    require(classes == {'EPG': 46, 'ER4m': 10}, 'incorrect anatomy class counts')
    require([n['body_id'] for n in nodes] == sorted(seen_ids, key=int), 'noncanonical node ordering')
    pairs, directions, totals = set(), Counter(), Counter()
    for link in links:
        exact_keys(link, ('source', 'target', 'count'), 'link')
        for endpoint in ('source', 'target'):
            require(type(link[endpoint]) is int and 0 <= link[endpoint] < len(nodes),
                    'invalid indexed link endpoint')
        require(type(link['count']) is int and 0 < link['count'] <= 2**32-1,
                'link count must be an unsigned positive integer')
        pair = link['source'], link['target']
        require(pair not in pairs, 'duplicate indexed directed pair')
        pairs.add(pair)
        direction = nodes[pair[0]]['class'], nodes[pair[1]]['class']
        require(set(direction) == {'ER4m', 'EPG'}, 'within-class edges are outside this projection')
        directions[direction] += 1
        totals[direction] += link['count']
    require([(e['source'], e['target']) for e in links] == sorted(pairs), 'noncanonical link ordering')
    require(directions == {('ER4m', 'EPG'): 460, ('EPG', 'ER4m'): 302}, 'incorrect direction edge counts')
    require(totals == {('ER4m', 'EPG'): 14903, ('EPG', 'ER4m'): 1871}, 'incorrect EB synapse totals')


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def digest_record(contents):
    return {'bytes': len(contents), 'sha256': hashlib.sha256(contents).hexdigest()}


def generated(data_dir=DATA):
    tables = []
    for name, pin in SOURCES.items():
        storage = pin['storage']
        packed = (data_dir / storage['file']).read_bytes()
        require(digest_record(packed) == {key: storage[key] for key in ('bytes', 'sha256')},
                f'{name}: compressed source bytes/SHA256 do not match pinned storage')
        contents = gzip.decompress(packed)
        require(digest_record(contents) == {key: pin[key] for key in ('bytes', 'sha256')},
                f'{name}: source bytes/SHA256 do not match pinned input')
        blob = b'blob ' + str(len(contents)).encode('ascii') + b'\0' + contents
        require(hashlib.sha1(blob).hexdigest() == pin['git_blob_sha1'],
                f'{name}: source Git blob does not match pinned commit')
        text = contents.decode('utf-8')
        require(len(list(csv.DictReader(io.StringIO(text, newline='')))) == pin['raw_row_count'],
                f'{name}: unexpected source row count')
        tables.append((name, text))
    nodes, edges = extract_rows(tables)
    for name, pin in SOURCES.items():
        selected = [edge for edge in edges if edge['source_export'] == name]
        require(len(selected) == pin['selected_row_count'] and
                sum(edge['synapse_count'] for edge in selected) == pin['selected_synapse_count'],
                f'{name}: incorrect selected projection totals')
    indices = {node['body_id']: index for index, node in enumerate(nodes)}
    anatomy = {'schema_version': 1, 'metadata': metadata(), 'nodes': nodes,
               'links': [{'source': indices[e['source_body_id']],
                          'target': indices[e['target_body_id']], 'count': e['synapse_count']}
                         for e in edges]}
    validate_anatomy(anatomy)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=('source_body_id', 'target_body_id',
                                               'neuropil', 'synapse_count', 'source_export'),
                            lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(edges)
    # Preserve the vetted sidecar's class-first order without constraining the
    # indexed UI payload, whose node contract is numeric body-ID ordering.
    fixture_nodes = sorted(nodes, key=lambda node: (node['class'], int(node['body_id'])))
    outputs = {ANATOMY_NAME: json_bytes(anatomy), NODES_NAME: json_bytes(fixture_nodes),
               EDGES_NAME: stream.getvalue().encode('utf-8')}
    for name, expected in GOLDEN.items():
        require(hashlib.sha256(outputs[name]).hexdigest() == expected,
                f'{name}: extraction differs from independently vetted projection fixture')
    provenance = {
        'schema_version': 1,
        'metadata': metadata(),
        'extraction': {
            'implementation': 'flyos/tools/generate_hulse_data.py; independently written Python standard library',
            'selection': 'Every row with databaseType.from/to equal to ER4m/EPG in either direction; roi must be EB; ROIweight must be a positive integer.',
            'orientation': 'source = from (presynaptic); target = to (postsynaptic); count = ROIweight; no transposition, aggregation or normalization.',
            'absence': 'Missing pairs remain absent; no claim that omitted pairs are biological zeroes.',
            'ordering': 'Nodes sorted by numeric body ID; directed edges sorted by source then target numeric body ID; body IDs remain strings.',
            'validation': 'Raw bytes, SHA256 and Git blob SHA1; exact columns; unique directed pairs; consistent endpoint annotations; fixed totals; independently vetted node/edge fixture SHA256.',
        },
        'evidence': {
            'checked_on': '2026-10-10',
            'source_tree': f'https://api.github.com/repos/jayaraman-lab/CX-connectome-analysis/git/trees/{COMMIT}?recursive=1',
            'source_tree_entries': 146,
            'source_tree_truncated': False,
            'repository_license_file_found': False,
            'dataset_version': f'{REPOSITORY}/blob/{COMMIT}/README.md',
            'orientation_and_count_semantics': f'{REPOSITORY}/blob/{COMMIT}/EBFigures/modularityAnalysis/computeModularity.m',
            'code_note': 'Evidence was inspected only. No upstream analysis code is distributed in this data bundle.',
        },
        'sources': {name: dict(record, url=f'{REPOSITORY}/blob/{COMMIT}/{record["path"]}')
                    for name, record in SOURCES.items()},
        'artifacts': {name: digest_record(contents) for name, contents in outputs.items()},
    }
    outputs[PROVENANCE_NAME] = json_bytes(provenance)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify without writing any files')
    parser.add_argument('--data-dir', type=Path, default=DATA, help='directory with pinned raw CSVs')
    args = parser.parse_args()
    try:
        outputs = generated(args.data_dir)
        if args.check:
            for name, contents in outputs.items():
                path = args.data_dir / name
                require(path.is_file() and path.read_bytes() == contents, f'{name}: generated artifact is stale')
        else:
            # Verification finishes before any write; bytes avoid platform newline conversion.
            for name, contents in outputs.items():
                (args.data_dir / name).write_bytes(contents)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f'Hulse anatomy verification failed: {error}\n')
    print('Hulse anatomy: 56 cells, 762 directed EB links, 16774 synapses; pinned provenance verified')


if __name__ == '__main__':
    main()
