#!/usr/bin/env python3
"""Build a portable, self-contained replay lab from the real C trace exporter.

The output is offline HTML plus its source trace and hashes. No network access,
firmware inputs, device communication, or third-party Python packages are used.
Existing output directories are rejected to preserve previous captures.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import struct
import subprocess
import zlib
from urllib.parse import urlparse

PALETTE = ((8, 10, 9), (54, 69, 59), (218, 231, 211),
           (135, 184, 122), (184, 122, 135), (242, 210, 94))


def load_anatomy_data(path: Path) -> dict:
    """Bound and reconcile the static anatomy presentation contract.

    This checks structural consistency, not scientific provenance. The separate
    Hulse source verifier pins and re-derives the underlying measured fragment.
    No connection count is converted into a simulated activity or signed weight.
    """
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('invalid anatomy schema')
    nodes, links, meta = value.get('nodes'), value.get('links'), value.get('metadata')
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 64 or not isinstance(links, list) or len(links) > 4096 or not isinstance(meta, dict):
        raise ValueError('invalid anatomy bounds')
    ids = set()
    counts = Counter()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('body_id'), str) or not re.fullmatch(r'[1-9][0-9]{0,19}', node['body_id']):
            raise ValueError('anatomy body identifiers must be decimal strings')
        if node['body_id'] in ids or node.get('class') not in ('EPG', 'ER4m'):
            raise ValueError('duplicate anatomy identity or unsupported class')
        if not isinstance(node.get('instance'), str) or not 1 <= len(node['instance']) <= 256:
            raise ValueError('invalid anatomy instance')
        ids.add(node['body_id'])
        counts[node['class']] += 1
    seen = set()
    directions = {}
    total = 0
    for link in links:
        if not isinstance(link, dict) or any(type(link.get(key)) is not int for key in ('source', 'target', 'count')):
            raise ValueError('invalid anatomy connection')
        source, target, count = link['source'], link['target'], link['count']
        if not 0 <= source < len(nodes) or not 0 <= target < len(nodes) or not 1 <= count <= 1000000:
            raise ValueError('invalid anatomy connection bounds')
        key = source, target
        if key in seen or nodes[source]['class'] == nodes[target]['class']:
            raise ValueError('duplicate or non-cross-class anatomy projection')
        seen.add(key)
        total += count
        direction = nodes[source]['class'], nodes[target]['class']
        record = directions.setdefault(direction, {'edge_count': 0, 'synapse_count_sum': 0})
        record['edge_count'] += 1
        record['synapse_count_sum'] += count
    if (any(type(meta.get(key)) is not int for key in ('node_count', 'edge_count', 'synapse_count_sum'))
            or meta.get('roi') != 'EB' or meta.get('node_count') != len(nodes)
            or meta.get('edge_count') != len(links) or meta.get('synapse_count_sum') != total
            or meta.get('class_counts') != dict(counts)):
        raise ValueError('anatomy totals do not match supplied data')
    declared = meta.get('directions')
    if not isinstance(declared, list) or len(declared) != len(directions):
        raise ValueError('invalid anatomy direction totals')
    reported = {}
    for item in declared:
        if not isinstance(item, dict):
            raise ValueError('invalid anatomy direction')
        if (item.get('source_class') not in ('EPG', 'ER4m') or item.get('target_class') not in ('EPG', 'ER4m')
                or any(type(item.get(key)) is not int for key in ('edge_count', 'synapse_count_sum'))):
            raise ValueError('invalid anatomy direction fields')
        key = item.get('source_class'), item.get('target_class')
        if key in reported:
            raise ValueError('duplicate anatomy direction')
        reported[key] = {name: item.get(name) for name in ('edge_count', 'synapse_count_sum')}
    if reported != directions:
        raise ValueError('anatomy direction totals do not match')
    for name in ('id', 'title', 'dataset', 'boundary'):
        if not isinstance(meta.get(name), str) or not 1 <= len(meta[name]) <= 4096:
            raise ValueError('invalid anatomy description')
    limitations = meta.get('limitations')
    if not isinstance(limitations, list) or not limitations or any(not isinstance(item, str) or not item for item in limitations):
        raise ValueError('invalid anatomy limitations')
    source, license_ = meta.get('source'), meta.get('license')
    if not isinstance(source, dict) or not isinstance(license_, dict) or license_.get('id') != 'CC-BY-4.0':
        raise ValueError('missing anatomy source or attribution')
    for url in [source.get(key) for key in ('paper', 'hemibrain_paper', 'repository')] + [license_.get('url')]:
        if not isinstance(url, str):
            raise ValueError('invalid anatomy citation')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('anatomy citations must be plain HTTPS links')
    if not isinstance(source.get('commit'), str) or not re.fullmatch(r'[0-9a-f]{40}', source['commit']):
        raise ValueError('missing pinned anatomy source revision')
    for key in ('attribution', 'changes'):
        if not isinstance(license_.get(key), str) or not license_[key]:
            raise ValueError('missing anatomy attribution or modification notice')
    return value


def load_model_metadata(path: Path) -> list[dict]:
    """Validate bounded descriptive metadata; connectivity comes from C only.

    Citation links are optional user navigation, never loaded resources. This
    validates presentation contracts, not the scientific truth of a source.
    """
    document = json.loads(path.read_text(encoding='utf-8'))
    models = document.get('models') if isinstance(document, dict) else None
    if not isinstance(models, list) or not 1 <= len(models) <= 8:
        raise ValueError('invalid model metadata list')
    ids = set()
    for model in models:
        if not isinstance(model, dict) or type(model.get('id')) is not int:
            raise ValueError('invalid model id')
        if model['id'] in ids or not 0 <= model['id'] <= 7:
            raise ValueError('duplicate or unsupported model id')
        ids.add(model['id'])
        for key in ('key', 'label', 'description', 'biological_basis'):
            if not isinstance(model.get(key), str) or not 1 <= len(model[key]) <= 4096:
                raise ValueError(f'invalid model {key}')
        if type(model.get('scale')) is not int or not 1 <= model['scale'] <= 32768:
            raise ValueError('invalid model activation scale')
        approximations = model.get('approximations')
        if not isinstance(approximations, list) or not approximations or any(
                not isinstance(item, str) or not 1 <= len(item) <= 4096 for item in approximations):
            raise ValueError('invalid model approximations')
        units = model.get('units')
        if not isinstance(units, list) or not 1 <= len(units) <= 64:
            raise ValueError('invalid model unit count')
        for index, unit in enumerate(units):
            if (not isinstance(unit, dict) or type(unit.get('id')) is not int or unit['id'] != index
                    or any(not isinstance(unit.get(key), str) or not 1 <= len(unit[key]) <= 256
                           for key in ('label', 'group'))):
                raise ValueError('invalid model unit identity')
        sources = model.get('sources')
        if not isinstance(sources, list) or len(sources) > 32:
            raise ValueError('invalid model sources')
        for source in sources:
            if (not isinstance(source, dict) or not isinstance(source.get('title'), str)
                    or not 1 <= len(source['title']) <= 512 or not isinstance(source.get('url'), str)):
                raise ValueError('invalid model source')
            url = urlparse(source.get('url', ''))
            if url.scheme != 'https' or not url.netloc or url.username or url.password:
                raise ValueError('model source must be a plain HTTPS citation')
    if 0 not in ids:
        raise ValueError('model metadata must preserve baseline id zero')
    return models


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def frame_png(runs: list[list[int]]) -> bytes:
    pixels = bytearray()
    count = 0
    for role, length in runs:
        if type(role) is not int or type(length) is not int or not 0 <= role < len(PALETTE) or length <= 0:
            raise ValueError('invalid semantic framebuffer run')
        count += length
        if count > 240 * 240:
            raise ValueError('framebuffer exceeds 240 x 240')
        pixels.extend(bytes(PALETTE[role]) * length)
    if count != 240 * 240:
        raise ValueError('incomplete framebuffer')
    rows = b''.join(b'\0' + pixels[offset:offset + 720] for offset in range(0, len(pixels), 720))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 240, 240, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def build(exporter: Path, output: Path, wasm: Path | None = None) -> None:
    # Reserve before invoking the exporter; never overwrite an existing capture.
    output.mkdir(parents=True, exist_ok=False)
    raw = subprocess.run([str(exporter.resolve())], check=True, capture_output=True).stdout
    data = json.loads(raw)
    if data.get('schema') != 1 or data.get('scope') != 'host-only' or data.get('hardware_verified') is not False:
        raise ValueError('unsupported or misleading trace contract')
    data['models'] = load_model_metadata(Path(__file__).parents[1] / 'sim' / 'circuit_models.json')
    data['anatomy'] = load_anatomy_data(Path(__file__).parents[1] / 'sim' / 'data' / 'hulse2021' /
                                      'hulse2021_er4m_epg_anatomy.json')
    (output / 'trace.json').write_bytes(raw)
    if wasm is not None:
        module = wasm.read_bytes()
        if not module.startswith(b'\x00asm\x01\x00\x00\x00') or len(module) > 4 * 1024 * 1024:
            raise ValueError('invalid WebAssembly module header or size')
        data['live_wasm'] = base64.b64encode(module).decode('ascii')
        data['live_wasm_sha256'] = hashlib.sha256(module).hexdigest()
    for scenario in data['scenarios']:
        for frame in scenario['frames']:
            frame['image'] = 'data:image/png;base64,' + base64.b64encode(frame_png(frame.pop('pixels'))).decode('ascii')
    payload = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = Path(__file__).with_name('interaction_lab.html').read_text(encoding='utf-8')
    if template.count('/*__LAB_DATA__*/') != 1:
        raise ValueError('lab template must contain one data marker')
    live_script = Path(__file__).with_name('interaction_lab_live.js').read_text(encoding='utf-8')
    if template.count('/*__LIVE_SCRIPT__*/') != 1 or '</script' in live_script.lower():
        raise ValueError('invalid live script template')
    circuit_script = Path(__file__).with_name('interaction_lab_circuit.js').read_text(encoding='utf-8')
    if template.count('/*__CIRCUIT_SCRIPT__*/') != 1 or '</script' in circuit_script.lower():
        raise ValueError('invalid circuit script template')
    anatomy_script = Path(__file__).with_name('interaction_lab_anatomy.js').read_text(encoding='utf-8')
    if template.count('/*__ANATOMY_SCRIPT__*/') != 1 or '</script' in anatomy_script.lower():
        raise ValueError('invalid anatomy script template')
    (output / 'index.html').write_text(template.replace('/*__LAB_DATA__*/', payload)
                                      .replace('/*__CIRCUIT_SCRIPT__*/', circuit_script)
                                      .replace('/*__ANATOMY_SCRIPT__*/', anatomy_script)
                                      .replace('/*__LIVE_SCRIPT__*/', live_script), encoding='utf-8')
    files = [output / 'index.html', output / 'trace.json']
    (output / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in files), encoding='ascii')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exporter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new directory; existing captures are never replaced')
    parser.add_argument('--wasm', type=Path, help='optional compiled real-C host bridge for the interactive sandbox')
    args = parser.parse_args()
    try:
        build(args.exporter, args.output, args.wasm)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'lab build failed: {error}\n')
    print(f'Open {args.output / "index.html"} in a browser. Offline host model only.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
