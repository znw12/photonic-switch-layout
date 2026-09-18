"""Cosine profile, fixed interfaces, actual GDS integration and failure checks."""
from dataclasses import replace
import json
import pytest
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
from shapely.affinity import rotate
from benes_layout.config import Config
from benes_layout.geometry import Library
from benes_layout.cosine_crossing import verify,export_device
from benes_layout.layout import build_layout
from benes_layout.verify import verify_manifest,verify_gds,VerificationError
from benes_layout.workflow import generate,verify_bundle


def profile(n=4,**kw):
    base=Config.load('examples/benes/gsg/n100.json')
    return replace(base,active_ports=n,internal_ports=None,input_map=None,output_map=None,**kw)


@pytest.mark.parametrize('kw',[{},dict(crossing_half_length=12),dict(wg_width=.8),
    dict(crossing_center_width=2.5,crossing_max_width=3.5,crossing_port_straight=1)])
def test_cosine_shape_and_rotated_footprints(kw):
    cfg=profile(**kw);lib=Library(cfg);cell=lib.crossing()
    verify(lib.export()['CROSSING'],cfg)
    old=Library(replace(cfg,crossing_model='placeholder')).crossing()
    assert cell.ports==old.ports and cell.tracks==old.tracks
    geom=unary_union([Polygon(p['points']) for p in cell.polygons])
    before=unary_union([Polygon(p['points']) for p in old.polygons])
    assert geom.area>before.area and geom.geom_type=='Polygon'
    for angle in range(0,360,45):
        assert rotate(geom,angle,origin=(0,0)).bounds==pytest.approx(rotate(before,angle,origin=(0,0)).bounds,abs=.002)
    for angle in (90,180,270):
        assert geom.symmetric_difference(rotate(geom,angle,origin=(0,0))).area<1e-6
    arm=Polygon(cell.polygons[1]['points'])
    # The convex bulge must widen past the center width then narrow to the port.
    samples=[arm.intersection(LineString([(x,-10),(x,10)])).length
             for x in [cfg.crossing_center_width/2+i*(cfg.crossing_half_length-cfg.crossing_port_straight-cfg.crossing_center_width/2)/100 for i in range(101)]]
    assert max(samples)>cfg.crossing_center_width
    assert max(samples)==pytest.approx(cfg.crossing_max_width,abs=.01)
    assert samples[0]==pytest.approx(cfg.crossing_center_width)
    assert samples[-1]==pytest.approx(cfg.wg_width)


@pytest.mark.parametrize('kw',[dict(crossing_model='unknown'),dict(crossing_center_width=1),
    dict(crossing_max_width=2),dict(crossing_port_straight=0),dict(crossing_port_straight=9),
    dict(crossing_max_width=float('nan'))])
def test_cosine_bad_parameters(kw):
    with pytest.raises(ValueError):profile(**kw)


@pytest.mark.parametrize('defect',['center','taper','port','metadata'])
def test_cosine_faults(defect):
    cfg=profile();lib=Library(cfg);c=lib.crossing()
    if defect=='center':c.polygons.pop(0)
    elif defect=='taper':c.polygons[1]['points'][8][1]+=.3
    elif defect=='port':c.ports['e'][0]+=.1
    else:c.metadata['optical_transfer_calibrated']=True
    with pytest.raises(VerificationError):verify(lib.export()['CROSSING'],cfg)


@pytest.mark.parametrize('n',[1,4,16])
def test_cosine_matrix(tmp_path,n):
    cfg=profile(n);lib,m=build_layout(cfg)
    verify_manifest(m)
    names=lib.write_gds(m['top'],tmp_path/'layout.gds')
    checks=verify_gds(tmp_path/'layout.gds',m,names)
    _,before=build_layout(replace(cfg,crossing_model='placeholder'))
    assert (m['width'],m['height'],m['crossing_count'])==(before['width'],before['height'],before['crossing_count'])
    assert m['electrical']==before['electrical']
    assert checks['shared_ground_nets']==1
    assert checks['independent_signals']==len(m['instances'])


@pytest.mark.parametrize('n',[1,4])
def test_cosine_bundle_and_report(tmp_path,n):
    cfg=profile(n);result=generate(cfg,tmp_path,list(enumerate(range(n))))
    assert result['crossing_device']['footprint_um']==[20,20]
    assert (tmp_path/'crossing/crossing.gds').is_file()
    assert (tmp_path/'crossing/crossing.png').is_file()
    verify_bundle(tmp_path)
    result['crossing_device']['center_width_um']=5
    (tmp_path/'report.json').write_text(json.dumps(result))
    with pytest.raises(VerificationError,match='crossing device report'):
        verify_bundle(tmp_path)
