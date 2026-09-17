"""Two-row centered metal routing, real extraction and corrupt-bundle rejection."""

import json

import pytest

from benes_layout.config import Config
from benes_layout.layout import build_layout
from benes_layout.geometry import rectangle
from benes_layout.verify import verify_manifest, verify_gds, VerificationError
from benes_layout.workflow import verify_bundle
from benes_layout.cli import main


def profile(n=5, **kw):
    values = dict(active_ports=n, pad_rows=2, pad_row_stagger=25, lane_pitch=60,
                  interstage_routing='continuous', electrical_routing='two-row',
                  share_interstage=True, max_candidates=1,
                  gap_factors=(1.0,), corridor_factors=(1.0,))
    values.update(kw)
    return Config(**values)


@pytest.mark.parametrize('overrides', [dict(pad_pitch=80),dict(pad_factors=(1.1,)),
    dict(pad_rows=4),dict(fold_bands=3),dict(interstage_routing='legacy'),
    dict(insulated_m2_overpasses=False),dict(equalize=True),dict(share_interstage=1)])
def test_unsupported_profile(overrides):
    with pytest.raises(ValueError):
        profile(**overrides)


@pytest.mark.parametrize('n,shared,reverse', [(1,True,False),(4,False,False),
    (5,True,False),(5,False,True),(16,True,True)])
def test_physical_two_row(tmp_path,n,shared,reverse):
    cfg=profile(n,share_interstage=shared,row_orders=('reverse' if reverse else 'normal',))
    choice=dict(id='test',gap=1,pad=1,corridor=1,row_order=cfg.row_orders[0])
    lib,m=build_layout(cfg,choice)
    verify_manifest(m)
    path=tmp_path/'layout.gds'
    names=lib.write_gds(m['top'],path)
    result=verify_gds(path,m,names)
    assert result['via_count']==5*len(m['electrical'])
    assert m['die_bbox'][1]==-m['die_bbox'][3]
    assert m['bands'][0]['y']==-(cfg.internal_ports-1)*cfg.lane_pitch/2
    assert m['passive_overpasses']
    north={(e['pad_column'],e['pad_row']):e['pad'] for e in m['electrical'] if e['side']=='north'}
    for e in m['electrical']:
        if e['side']=='south':
            x,y=north[e['pad_column'],e['pad_row']]
            assert e['pad']==[x,-y]
    for row in (0,1):
        xs=sorted(p[0] for (col,r),p in north.items() if r==row)
        assert all(b-a==pytest.approx(100) for a,b in zip(xs,xs[1:]))


@pytest.mark.parametrize('defect',['pad','via_metadata','path_metadata','center','layer','missing_via'])
def test_contract_faults(defect):
    lib,m=build_layout(profile())
    e=m['electrical'][0]
    if defect=='pad':e['pad'][0]+=1
    elif defect=='via_metadata':e['vias'][0][0]+=1
    elif defect=='path_metadata':e['segments'][0]['end'][0]+=1
    elif defect=='center':m['bands'][0]['y']+=1
    elif defect=='layer':lib.cells[e['cell']].polygons[1]['layer']='M1'
    else:lib.cells[e['cell']].refs.pop()
    m['cells']=lib.export()
    with pytest.raises(VerificationError):verify_manifest(m)


@pytest.mark.parametrize('defect',['window','window_object','short','mzi_overlap','via_optical'])
def test_physical_faults(tmp_path,defect):
    lib,m=build_layout(profile())
    e=m['electrical'][0]
    cell=lib.cells[e['cell']]
    if defect=='window':m['passive_overpasses'].pop()
    elif defect=='window_object':m['passive_overpasses'][0]['optical'][1]+=1
    elif defect=='short':
        other=m['electrical'][1]
        x=e['launch_x'];y0,y1=sorted((e['y'],other['y']))
        lib.poly(cell,'M1',rectangle(x-2.5,y0-2.5,x+2.5,y1+2.5))
    elif defect=='mzi_overlap':
        lib.poly(cell,'M2',rectangle(e['x']-150,e['y']-2.5,e['launch_x'],e['y']+2.5))
    else:
        lib.ref(cell,lib.via(),e['launch_x'],m['bands'][0]['y'])
    m['cells']=lib.export()
    path=tmp_path/'bad.gds'; names=lib.write_gds(m['top'],path)
    with pytest.raises(VerificationError):verify_gds(path,m,names)


def test_cli_bundle(tmp_path):
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps(profile(4).to_dict()))
    out=tmp_path/'result'
    assert main(['generate','--config',str(cfg),'--out',str(out)])==0
    assert (out/'pads_detail.png').is_file()
    assert verify_bundle(out)['electrical_extraction_passed']
    report=json.loads((out/'report.json').read_text())
    assert report['electrical']['shared_interstage']
    assert report['summary']['pad_rows_per_side']==2
    report['electrical']['shared_width_um']+=1
    (out/'report.json').write_text(json.dumps(report))
    with pytest.raises(VerificationError,match='electrical report mismatch'):
        verify_bundle(out)
