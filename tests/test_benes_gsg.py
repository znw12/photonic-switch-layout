"""Physical 2x2 GSG geometry, internal vias and shared-ground extraction."""
from dataclasses import replace
import json

import pytest
from benes_layout.config import Config
from benes_layout.geometry import Library,rectangle
from benes_layout.gsg_mzi import export_device
from benes_layout.gsg_verify import verify_device
from benes_layout.layout import build_layout
from benes_layout.verify import verify_manifest,verify_gds,VerificationError
from benes_layout.workflow import generate,verify_bundle


def profile(n=4,**kw):
    values=dict(active_ports=n,lane_pitch=60,pad_rows=3,pad_row_pitch=70,pad_pitch=120,
        pad_row_stagger=25,margin=40,electrical_routing='three-row',electrical_fanout='aligned',
        interstage_routing='continuous',share_interstage=True,mzi_model='paper-gsg',
        terminal_names=('G','S'),max_candidates=1,gap_factors=(1.0,),corridor_factors=(1.0,))
    values.update(kw)
    return Config(**values)


@pytest.mark.parametrize('kw',[dict(mzi_length=999),dict(radius=19),dict(gsg_gap=3),
    dict(gsg_ground_width=5),dict(terminal_names=('return','control')),dict(lane_pitch=80),
    dict(coupler_gap=30),dict(mzi_model='unknown')])
def test_invalid_gsg_config(kw):
    with pytest.raises(ValueError):profile(**kw)


@pytest.mark.parametrize('radius',[20,25,30])
def test_gsg_device_radius_and_ports(radius):
    cfg=profile(radius=radius);lib=Library(cfg);cell=lib.mzi();result=verify_device(lib.export(),cfg)
    assert set(cell.ports)=={'i0','i1','o0','o1','G','S'}
    assert result['total_length_um']==1000 and result['min_radius_um']==radius
    assert result['branch_geometric_length_um']>1000
    start,end=cell.metadata['active_x']
    assert start+end==pytest.approx(cfg.mzi_length)
    if radius==20:
        assert (start,end)==(160,840)
        assert result['active_length_um']==680
    assert result['internal_vias_per_device']==5
    assert not result['coupler_calibrated']


@pytest.mark.parametrize('active_x',[(150,840),(160,850)])
def test_gsg_electrode_bend_clearance(active_x):
    cfg=profile();lib=Library(cfg);cell=lib.mzi()
    cell.metadata['active_x']=list(active_x)
    cell.metadata['active_length_um']=active_x[1]-active_x[0]
    with pytest.raises(VerificationError,match='straight-section bend clearance'):
        verify_device(lib.export(),cfg)


@pytest.mark.parametrize('n,reverse',[(1,False),(4,False),(5,True),(16,False)])
def test_gsg_physical_matrix(tmp_path,n,reverse):
    cfg=profile(n)
    lib,m=build_layout(cfg,dict(id='test',gap=1,pad=1,corridor=1,row_order='reverse' if reverse else 'normal'))
    verify_manifest(m)
    p=tmp_path/'matrix.gds';names=lib.write_gds(m['top'],p)
    checks=verify_gds(p,m,names)
    count=len(m['instances'])
    assert checks['shared_ground_nets']==1 and checks['independent_signals']==count
    assert checks['electrical_nets']==count+1
    assert checks['via_count']==sum(len(e['vias']) for e in m['electrical'])+6*count
    assert {e['electrical_net'] for e in m['electrical'] if e['terminal']=='G'}=={'GND'}
    assert len({e['electrical_net'] for e in m['electrical'] if e['terminal']=='S'})==count


@pytest.mark.parametrize('defect',['radius','dc_gap','waveguide_break','local_metal','internal_via','ground_label','bus'])
def test_gsg_manifest_faults(defect):
    lib,m=build_layout(profile())
    c=lib.cells['MZI']
    if defect=='radius':
        next(s for s in c.metadata['optical_paths'][0] if s['kind']=='arc')['radius']=19
    elif defect=='dc_gap':
        for at in lib.cells['GSG_DC'].polygons[1]['points']:at[1]-=.2
    elif defect=='waveguide_break':lib.cells['GSG_WAVEGUIDES'].polygons.pop(0)
    elif defect=='local_metal':lib.poly(c,'M2',rectangle(690,9,750,31))
    elif defect=='internal_via':c.refs.pop()
    elif defect=='ground_label':m['electrical'][0]['electrical_net']='GND' if m['electrical'][0]['terminal']=='S' else 'wrong'
    else:lib.cells['COMMON_GROUND'].polygons.pop()
    m['cells']=lib.export()
    with pytest.raises(VerificationError):verify_manifest(m)


@pytest.mark.parametrize('defect',['ground_signal_short','signal_signal_short','ground_open','internal_ground_open'])
def test_gsg_physical_faults(tmp_path,defect):
    lib,m=build_layout(profile())
    if defect=='ground_signal_short':
        c=lib.cells['MZI'];gx=c.metadata['electrical_probes']['G'][0][0]
        sx,sy=c.metadata['electrical_probes']['S'][0]
        lib.poly(c,'M2',rectangle(gx-2.5,sy-2.5,sx+2.5,sy+2.5))
    elif defect=='signal_signal_short':
        signals=sorted((e for e in m['electrical'] if e['terminal']=='S' and e['side']=='north'),key=lambda e:e['pad'][0])
        a,b=signals[:2]
        # Connect two existing M2 pads, allowing the extractor to detect the short.
        x0,y0=a['pad'];x1,y1=b['pad']
        lib.poly(lib.cells['COMMON_GROUND'],'M2',rectangle(x0-2.5,min(y0,y1)-2.5,x0+2.5,max(y0,y1)+2.5))
        lib.poly(lib.cells['COMMON_GROUND'],'M2',rectangle(x0-2.5,y1-2.5,x1+2.5,y1+2.5))
    elif defect=='ground_open':
        lib.cells['COMMON_GROUND'].polygons.pop()  # Disconnect north and south buses.
    else:
        c=lib.cells['MZI']
        c.refs=[r for r in c.refs if not (r['cell']=='VIA' and r['y']==50)]
    m['cells']=lib.export();p=tmp_path/'bad.gds';names=lib.write_gds(m['top'],p)
    with pytest.raises(VerificationError):verify_gds(p,m,names)


def test_gsg_bundle_and_standalone(tmp_path):
    result=generate(profile(4),tmp_path,list(enumerate(range(4))))
    assert result['device']['active_length_um']==680
    assert result['summary']['vias']==result['electrical']['vias_total']
    assert (tmp_path/'device/mzi.gds').is_file() and (tmp_path/'device/mzi.png').is_file()
    assert 'electrical_net' in (tmp_path/'pads.csv').read_text().splitlines()[0]
    assert verify_bundle(tmp_path)['shared_ground_nets']==1
    result['device']['active_length_um']=1000
    (tmp_path/'report.json').write_text(json.dumps(result))
    with pytest.raises(VerificationError,match='device report'):verify_bundle(tmp_path)
