"""Dense optical grid and locally aggregated ground, checked on real GDS."""
from dataclasses import replace
from pathlib import Path

import pytest

from benes_layout.config import Config
from benes_layout.geometry import Library, rectangle
from benes_layout.gsg_verify import verify_device
from benes_layout.layout import build_layout
from benes_layout.verify import verify_manifest, verify_gds, VerificationError
from benes_layout.workflow import generate, verify_bundle


def profile(n=4, **kwargs):
    cfg=Config.load(Path(__file__).parents[1]/'examples/benes/compact-gsg/n100.json')
    values=dict(active_ports=n,internal_ports=None,input_map=None,output_map=None,
                ground_pads_per_side=2 if n<=4 else 4)
    values.update(kwargs)
    return replace(cfg,**values)


def test_device_pitch_and_straight_lead():
    cfg=profile();lib=Library(cfg);device=lib.mzi()
    result=verify_device(lib.export(),cfg)
    assert result['min_radius_um']==20 and result['total_length_um']==1000
    assert device.ports['i1'][1]-device.ports['i0'][1]==25
    assert device.metadata['phase_arm_y']==[0,25]
    metal=[p for p in device.polygons if p['layer']=='M2']
    assert len(metal)==2  # Local G bridge and one straight S lead.
    assert device.ports['S']==[1000,12.5,0]


@pytest.mark.parametrize('n,reverse',[(4,False),(5,True),(16,False),(32,True)])
def test_compact_matrix_readback(tmp_path,n,reverse):
    cfg=profile(n)
    lib,m=build_layout(cfg,dict(id='test',gap=1,pad=1,corridor=1,
                              row_order='reverse' if reverse else 'normal'))
    verify_manifest(m)
    path=tmp_path/'chip.gds';names=lib.write_gds(m['top'],path)
    checks=verify_gds(path,m,names)
    switches=len(m['instances'])
    assert len(m['electrical'])==switches+2*cfg.ground_pads_per_side
    assert checks['electrical_nets']==switches+1
    assert checks['independent_signals']==switches
    assert len(m['ground_network']['members'])==switches
    assert all(r['approach_offset']>0 for r in m['interstage'])
    for side in ('north','south'):
        pads=[e for e in m['electrical'] if e['side']==side]
        assert sum(e['terminal']=='G' for e in pads)==cfg.ground_pads_per_side
        for row in range(3):
            xs=sorted(e['pad'][0] for e in pads if e['pad_row']==row)
            assert all(b-a>=120-1e-6 for a,b in zip(xs,xs[1:]))


@pytest.mark.parametrize('defect',['ground_open','electrode_open','signal_short','extra_metal'])
def test_compact_faults(tmp_path,defect):
    cfg=profile();lib,m=build_layout(cfg)
    if defect=='ground_open':
        c=lib.cells['COMMON_GROUND']
        c.polygons=[p for p in c.polygons if p['layer']!='M1']
    elif defect=='electrode_open':
        c=lib.cells['MZI'];lowest=min(p[1] for p in c.metadata['internal_vias'])
        c.refs=[r for r in c.refs if not (r['cell']=='VIA' and r['y']==lowest)]
    elif defect=='signal_short':
        c=lib.cells['MZI'];gx=c.ports['G'][0];sx=c.metadata['electrical_probes']['S'][0][0]
        lib.poly(c,'M2',rectangle(gx,10.5,sx,14.5))
    else:
        # A foreign M2 branch cannot use the common-ground strip as a blanket
        # exemption for arbitrary metal inside an optical device.
        c=lib.cells['COMMON_GROUND'];inst=m['instances'][0]
        lib.poly(c,'M2',rectangle(inst['x']+700,inst['y']-2,inst['x']+800,inst['y']+2))
    m['cells']=lib.export();path=tmp_path/'defect.gds';names=lib.write_gds(m['top'],path)
    with pytest.raises(VerificationError):verify_gds(path,m,names)


def test_compact_export_bundle(tmp_path):
    report=generate(profile(),tmp_path,[(0,3),(3,0)])
    assert report['success'] and report['ground_network']['ground_pads']==4
    assert len((tmp_path/'pads.csv').read_text().splitlines())==11
    assert report['device']['electrical_port_layer']=='M2'
    assert verify_bundle(tmp_path)['independent_signals']==6


@pytest.mark.parametrize('kwargs',[dict(ground_pads_per_side=99),dict(metal_width=5),
    dict(mzi_height=100),dict(lane_pitch=20),dict(terminal_offsets=(20,40)),
    dict(share_interstage=False),dict(pad_pitch=99)])
def test_reject_incompatible_compact_profile(kwargs):
    with pytest.raises(ValueError):profile(**kwargs)
