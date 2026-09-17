"""Bounded pad-spacing comparison with physical and repeatability evidence."""
from dataclasses import replace
import json
from pathlib import Path

from .aligned_fanout import allocate, schedule, routing_metrics
from .config import Config
from .geometry import Library
from .network import Network
from .two_row import plan


def screen(cfg):
    if cfg.active_ports != 100 or cfg.internal_ports != 128:
        raise ValueError('aligned reference study requires 100 active / 128 internal ports')
    lib, net = Library(cfg), Network(cfg)
    blocks = [lib.shuffle_block(b['size'], b['inverse']) for b in net.boundaries]
    choice = dict(gap=1, pad=1, corridor=1)
    base = replace(cfg, electrical_fanout='channel', pad_pitch=100)
    stages, width, _, _, step = plan(base, net, blocks, choice)
    sources = [x for stage in stages for x in stage['trunk_xs']]
    records = []
    for pitch in (100, 105, 110, 120):
        candidate = replace(base, electrical_fanout='aligned', pad_pitch=pitch)
        slots = allocate(candidate, sources, 0, width, step)
        levels = schedule(sources, slots, step)
        direct = 2*sum(x == s['px'] for x,s in zip(sources, slots))
        height = (net.p-1)*cfg.lane_pitch + cfg.mzi_height-cfg.lane_pitch + 2*(
            3*cfg.margin + (max(levels)+2)*step + cfg.pad_size + 2*cfg.pad_row_pitch)
        full_width = width + 2*cfg.margin
        records.append(dict(pitch=pitch, direct_nets=direct,
            turns=6*len(sources)-2*direct, vias=10*len(sources)-2*direct,
            channel_levels=max(levels)+1, width_mm=full_width/1000,
            height_mm=height/1000, area_mm2=full_width*height/1e6))
    return records


def run(cfg, out, reuse=False):
    from .cli import save
    from .workflow import generate, verify_bundle
    from .comparison import compare_bundles
    out = Path(out)
    records = screen(cfg)
    save(out/'planning-screen.json', dict(scope='Planning estimates, not physical verification', candidates=records))
    profiles = {f'pitch-{r["pitch"]}':replace(cfg, electrical_fanout='aligned', pad_pitch=r['pitch'])
                for r in records}
    for name, profile in profiles.items():
        target = out/name
        if reuse and (target/'report.json').exists():
            report = json.loads((target/'report.json').read_text())
            if (report.get('success') and Config.load(target/'config.json').digest == profile.digest
                and all(report['checks'].get(k) for k in ('manifest_geometry_passed',
                    'gds_readback_passed', 'electrical_extraction_passed'))):
                continue
        generate(profile, target, list(enumerate(range(100))))
    result = compare_bundles([out/name for name in profiles], out/'comparison')
    result['routing'] = {name:routing_metrics(json.loads((out/name/'manifest.json').read_text()))
                         for name in profiles}
    chosen = Path(result['smallest_area'])
    original = json.loads((chosen/'report.json').read_text())
    repeated = generate(Config.load(chosen/'config.json'), out/'repeat-best', list(enumerate(range(100))))
    for field in ('normalized_hash', 'summary', 'uniformity', 'realized', 'electrical'):
        if original[field] != repeated[field]:
            raise ValueError(f'aligned repeat differs: {field}')
    for file in ('settings.json', 'pads.csv', 'ports.csv'):
        if (chosen/file).read_bytes() != (out/'repeat-best'/file).read_bytes():
            raise ValueError(f'aligned repeat differs: {file}')
    result['repeat'] = dict(passed=True, normalized_hash=repeated['normalized_hash'],
                           independent_readback=verify_bundle(out/'repeat-best'))
    save(out/'study.json', result)
    return result
