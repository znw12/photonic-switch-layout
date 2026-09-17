"""Nonuniform three-row pads, actual turn reduction and independent extraction."""
from dataclasses import replace
import json

import pytest

from benes_layout.config import Config
from benes_layout.layout import build_layout
from benes_layout.aligned_fanout import allocate, routing_metrics
from benes_layout.verify import verify_manifest, verify_gds, VerificationError
from benes_layout.workflow import verify_bundle
from benes_layout.cli import main


def profile(n=5, **kw):
    data = dict(active_ports=n, pad_rows=3, pad_row_stagger=25, pad_row_pitch=70,
                pad_pitch=120, margin=40, lane_pitch=60, interstage_routing='continuous',
                electrical_routing='three-row', electrical_fanout='aligned',
                share_interstage=True, max_candidates=1, gap_factors=(1.0,),
                corridor_factors=(1.0,), pad_factors=(1.0,))
    data.update(kw)
    return Config(**data)


@pytest.mark.parametrize('kw', [dict(electrical_fanout='bad'), dict(electrical_routing='legacy'),
    dict(electrical_routing='two-row', pad_rows=2), dict(pad_pitch=99), dict(pad_factors=(1.1,))])
def test_invalid_aligned_config(kw):
    with pytest.raises(ValueError): profile(**kw)


@pytest.mark.parametrize('n,shared,reverse', [(1,True,False), (4,False,True),
    (5,True,False), (16,True,True)])
def test_aligned_geometry(tmp_path,n,shared,reverse):
    cfg = profile(n, share_interstage=shared)
    candidate = dict(id='test', gap=1, pad=1, corridor=1,
                     row_order='reverse' if reverse else 'normal')
    lib,m = build_layout(cfg,candidate)
    _,old = build_layout(replace(cfg,electrical_fanout='channel',pad_pitch=100),candidate)
    assert m['stages'] == old['stages']
    assert m['routes'] == old['routes']
    assert m['width'] == old['width']
    verify_manifest(m)
    path = tmp_path/'layout.gds'; names = lib.write_gds(m['top'],path)
    result = verify_gds(path,m,names)
    stats = routing_metrics(m)
    assert stats['direct_pad_nets'] > 0
    assert stats['turns_total'] < routing_metrics(old)['turns_total']
    assert set(stats['turns_histogram']) <= {'1','3'}
    assert result['via_count'] == stats['vias_total']
    assert stats['vias_total'] == 5*len(m['electrical'])-2*stats['direct_pad_nets']
    if n > 1: assert stats['same_row_pitch_min_um'] >= cfg.pad_pitch-1e-6
    assert m['die_bbox'][1] == -m['die_bbox'][3]


def test_fixed_width_allocation_failure():
    with pytest.raises(ValueError,match='fixed width'):
        allocate(profile(pad_pitch=1000), [100,125,150,175,200,225], 0, 300, 14.002)


@pytest.mark.parametrize('defect',['pitch','column','flag','via','path','layer'])
def test_aligned_faults(defect):
    lib,m = build_layout(profile())
    e = next(e for e in m['electrical'] if e['direct_pad'])
    if defect == 'pitch':
        bank = sorted((x for x in m['electrical'] if x['side']=='north' and x['pad_row']==0),
                      key=lambda x:x['pad'][0])
        bank[1]['pad'][0] = bank[0]['pad'][0]+99
    elif defect == 'column': e['pad_column'] += 1
    elif defect == 'flag': e['direct_pad'] = False
    elif defect == 'via': lib.cells[e['cell']].refs.pop()
    elif defect == 'path': e['segments'][2]['end'][0] += 1
    else: lib.cells[e['cell']].polygons[1]['layer'] = 'M1'
    m['cells'] = lib.export()
    with pytest.raises(VerificationError): verify_manifest(m)


def test_cli_aligned_bundle_and_report_fault(tmp_path):
    cfg = tmp_path/'config.json'; cfg.write_text(json.dumps(profile(4).to_dict()))
    out = tmp_path/'result'
    assert main(['generate','--config',str(cfg),'--electrical-fanout','aligned','--out',str(out)]) == 0
    assert verify_bundle(out)['electrical_extraction_passed']
    r = json.loads((out/'report.json').read_text())
    r['electrical']['turns_total'] += 1
    (out/'report.json').write_text(json.dumps(r))
    with pytest.raises(VerificationError,match='electrical report mismatch'): verify_bundle(out)
