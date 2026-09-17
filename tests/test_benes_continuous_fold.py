"""Three-band continuous routing retains opposite-side IO and four pad rows."""
from dataclasses import replace
import pytest

from benes_layout.config import Config
from benes_layout.layout import build_layout
from benes_layout.verify import verify_manifest, verify_gds, VerificationError, normalized_hash
from benes_layout.cli import main
from benes_layout.workflow import verify_bundle


def profile(n=5, **changes):
    return Config(active_ports=n, interstage_routing='continuous', lane_pitch=60,
                  fold_bands=3, pad_rows=4, pad_row_stagger=25, **changes)


@pytest.mark.parametrize('counts', [(1,1), (0,3,2), (-1,3,3), (True,2,2), (1,2,3), (1.,2,2), 5])
def test_partition_validation(counts):
    with pytest.raises(ValueError, match='band_stage_counts'):
        profile(band_stage_counts=counts)


@pytest.mark.parametrize('changes', [dict(interstage_routing='compressed',shuffle_pitch=40),
                                    dict(pad_distribution='stage'), dict(fold_bands=5),
                                    dict(pad_rows=3)])
def test_continuous_fold_scope(changes):
    with pytest.raises(ValueError): replace(profile(),**changes)


@pytest.mark.parametrize('n,order,counts', [(4,'normal',(1,1,1)),(5,'reverse',(2,2,1)),
                                          (16,'normal',(3,2,2)),(16,'reverse',(2,3,2))])
def test_folded_continuous_physical(tmp_path,n,order,counts):
    cfg=profile(n,band_stage_counts=counts)
    choice=dict(id='three',gap=1.,pad=1.,corridor=1.,row_order=order)
    lib,m=build_layout(cfg,choice)
    assert [len(b['stages']) for b in m['bands']]==list(counts)
    assert [m['stages'][b['stages'][0]]['angle'] for b in m['bands']]==[0,180,0]
    verify_manifest(m)
    names=lib.write_gds(m['top'],tmp_path/'fold.gds')
    check=verify_gds(tmp_path/'fold.gds',m,names)
    assert check['via_count']==3*len(m['electrical'])
    west=[p for p in m['interfaces'] if p['side']=='west']
    east=[p for p in m['interfaces'] if p['side']=='east']
    assert len({p['position'][0] for p in west})==len({p['position'][0] for p in east})==1
    assert west[0]['position'][0]<east[0]['position'][0]
    assert min(p['position'][1] for p in east)>max(p['position'][1] for p in west)
    assert sum(m['cells'][p['cell']]['kind']=='turn' for r in m['routes'] for p in r['pieces'])==2*cfg.internal_ports
    _,again=build_layout(cfg,choice)
    assert normalized_hash(m)==normalized_hash(again)


@pytest.mark.parametrize('fault',['tangent','radius','gap','partition','pad'])
def test_continuous_fold_faults(fault):
    _,m=build_layout(profile(band_stage_counts=(2,2,1)))
    if fault=='tangent':
        next(c for c in m['cells'].values() if c['kind']=='turn')['ports']['e'][2]+=5
    elif fault=='radius':
        next(c for c in m['cells'].values() if c['kind']=='turn')['metadata']['arc']['radius']=19
    elif fault=='gap':
        next(p for r in m['routes'] for p in r['pieces'] if m['cells'][p['cell']]['kind']=='fan_lane')['x']+=1
    elif fault=='partition': m['config']['band_stage_counts']=(1,2,2)
    else: m['electrical'][0]['pad'][0]+=1
    with pytest.raises(VerificationError): verify_manifest(m)


def test_three_band_metal_window_fault(tmp_path):
    lib,m=build_layout(profile())
    m['overpasses']=[]
    names=lib.write_gds(m['top'],tmp_path/'missing-windows.gds')
    with pytest.raises(VerificationError,match='overpass'):
        verify_gds(tmp_path/'missing-windows.gds',m,names)


def test_three_band_cli(tmp_path):
    out=tmp_path/'three'
    assert main(['generate','--n','5','--interstage-routing','continuous','--fold-bands','3',
                 '--band-stage-counts','2,2,1','--pad-rows','4','--pad-row-stagger','25',
                 '--lane-pitch','60','--candidates','1','--out',str(out)])==0
    assert verify_bundle(out)['electrical_extraction_passed']
