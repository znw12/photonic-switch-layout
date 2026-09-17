"""Continuous primitives, inverse shuffles and physical compression faults."""
from copy import deepcopy
from dataclasses import replace
from math import hypot
import pytest
from benes_layout.config import Config
from benes_layout.geometry import Library, point
from benes_layout.layout import build_layout
from benes_layout.verify import verify_manifest, verify_gds, VerificationError
from benes_layout.interstage import shift_dimensions, fanin


def profile(n=8, **kwargs):
    return Config(active_ports=n, lane_pitch=60, pad_rows=4, pad_distribution='stage',
                  pad_row_stagger=25, interstage_routing='continuous', **kwargs)


@pytest.mark.parametrize('kwargs',[
    {'interstage_routing':'bad'}, {'interstage_routing':'continuous'},
    {'shuffle_pitch':40}, {'interstage_routing':'compressed','shuffle_pitch':float('nan')},
    {'interstage_routing':'compressed','shuffle_pitch':40.0001},
    {'interstage_routing':'compressed','shuffle_pitch':61},
])
def test_reject_invalid_modes(kwargs):
    with pytest.raises(ValueError): Config(**kwargs)


@pytest.mark.parametrize('size',[4,8,16,32,64,128])
@pytest.mark.parametrize('inverse',[False,True])
def test_module_transfers_and_hierarchy(size,inverse):
    lib=Library(profile())
    block=lib.shuffle_block(size,inverse)
    perm=[i//2+(size//2 if i%2 else 0) for i in range(size)]
    if inverse: perm=[perm.index(i) for i in range(size)]
    assert block.metadata['permutation']==perm
    assert block is lib.shuffle_block(size,inverse)
    for i,track in enumerate(block.tracks):
        previous=block.ports[f'w{i}'][:2]
        for p in track['pieces']:
            c=lib.cells[p['cell']]
            at=point(p['x'],p['y'],p['angle'],c.ports[p['entry']])
            assert hypot(at[0]-previous[0],at[1]-previous[1])<=.002
            previous=point(p['x'],p['y'],p['angle'],c.ports[p['exit']])
        assert previous == block.ports[f'e{perm[i]}'][:2]
    assert sum(t['crossings'] for t in block.tracks)//2 == (size//2)*(size//2-1)//2
    assert sum(t['bends'] for t in block.tracks)==2*(size-2)


@pytest.mark.parametrize('n,row',[(1,'normal'),(4,'normal'),(5,'reverse'),(16,'normal')])
def test_full_physical(tmp_path,n,row):
    cfg=profile(n)
    choice=dict(id='test',gap=1.,pad=1.,corridor=1.,row_order=row)
    lib,m=build_layout(cfg,choice)
    verify_manifest(m)
    names=lib.write_gds(m['top'],tmp_path/'a.gds')
    verify_gds(tmp_path/'a.gds',m,names)
    _,old=build_layout(replace(cfg,interstage_routing='legacy'),choice)
    assert m['crossing_count']==old['crossing_count']
    assert m['width']<=old['width']


@pytest.mark.parametrize('defect',['gap','tangent','radius','statistics','pair','direction','third','polygon'])
def test_primitive_faults(defect):
    _,m=build_layout(profile())
    route=next(r for r in m['routes'] if r['crossings'])
    arc=next(c for c in m['cells'].values() if c['kind']=='bend')
    cross=m['cells']['CROSSING']
    if defect=='gap': route['pieces'][1]['x']+=1
    elif defect=='tangent': arc['ports']['e'][2]+=1
    elif defect=='radius': arc['metadata']['arc']['radius']=19
    elif defect=='statistics': arc['tracks'][0]['length']+=1
    elif defect=='pair': cross['tracks'][0]['ports']=['w','n']
    elif defect=='direction': cross['metadata']['allowed_transforms']=[0,90]
    elif defect=='polygon': arc['polygons'][0]['points'][0][0]+=1
    else:
        p=next(p for p in route['pieces'] if p['cell']=='CROSSING')
        cell=next(c for c in m['cells'].values() if c['kind']=='segment')
        # An undeclared third optical object inside the crossing is not exempt.
        m['cells'][m['top']]['refs'].append(dict(cell=cell['name'],x=p['x'],y=p['y'],angle=0,id='intruder'))
    with pytest.raises(VerificationError): verify_manifest(m)


def test_small_shift_and_local_compression():
    for d in (0,.5,5,20,40,400):
        w,a,length=shift_dimensions(d,20)
        from math import sin,cos
        assert 2*20*(1-cos(a))+length*sin(a)==pytest.approx(d)
        assert w==pytest.approx(40*sin(a)+length*cos(a))
    lib=Library(replace(profile(32),interstage_routing='compressed',shuffle_pitch=40))
    block=lib.shuffle_block(32)
    assert block.metadata['mode']=='compressed'
    assert block.metadata['width']==pytest.approx(block.metadata['core_width']+2*block.metadata['fanin_width'])
    assert lib.shuffle_block(4).metadata['mode']=='continuous'
    assert fanin(lib,4,60,55).metadata['width']>0


def test_replacement_crossing_rejects_rotation():
    def factory(lib): lib.crossing().metadata['allowed_transforms']=[0,90,180,270]
    with pytest.raises(ValueError,match='transform'):
        build_layout(profile(),component_factory=factory)


def test_compressed_physical_and_boundary_faults(tmp_path):
    cfg=replace(profile(32),interstage_routing='compressed',shuffle_pitch=40)
    lib,m=build_layout(cfg)
    verify_manifest(m)
    names=lib.write_gds(m['top'],tmp_path/'compressed.gds')
    verify_gds(tmp_path/'compressed.gds',m,names)
    for defect in ('budget','crossing_count','pitch'):
        bad=deepcopy(m)
        if defect=='crossing_count': bad['crossing_count']+=1
        else:
            record=next(r for r in bad['interstage'] if r['mode']=='compressed')
            record['fanin_width' if defect=='budget' else 'actual_pitch']+=1
        with pytest.raises(VerificationError): verify_manifest(bad)


@pytest.mark.parametrize('q',[None,True,float('inf'),float('nan'),40.0001,6,61])
def test_local_pitch_validation(q):
    with pytest.raises(ValueError,match='shuffle_pitch'):
        replace(profile(),interstage_routing='compressed',shuffle_pitch=q)


def test_legacy_default_and_cells_unchanged():
    cfg=replace(profile(),interstage_routing='legacy')
    data=cfg.to_dict()
    data.pop('interstage_routing');data.pop('shuffle_pitch')
    a,m=build_layout(cfg)
    b,old=build_layout(Config(**data))
    assert m==old
    assert a.export()==b.export()


def test_comparison_area_priority_ties_and_failures(tmp_path):
    import json
    from benes_layout.comparison import compare_bundles
    directories=[]
    for name,width,spread in [('baseline',10,1),('larger',11,0),('tie',10,0)]:
        directory=tmp_path/name; directory.mkdir(); directories.append(directory)
        cfg=profile().to_dict()
        (directory/'config.json').write_text(json.dumps(cfg))
        metric=lambda lo,hi:dict(min=lo,max=hi)
        report=dict(success=True,checks=dict(manifest_geometry_passed=True,gds_readback_passed=True,electrical_extraction_passed=True),
                    summary=dict(active_ports=8,internal_ports=8,width_mm=width,height_mm=1,area_mm2=width,selected_candidate=name),
                    candidates=[dict(id=name,objective=[width*10**12,spread,0,0,0,name])],
                    uniformity=dict(metrics=dict(length=metric(10,10+spread),bends=metric(0,0),crossings=metric(0,0))),
                    metrics=dict(extents_um=dict(pads=[0,0,1,1],fanout=[0,0,1,1]),pad_bank_width_lower_bound_um=1,width_target_met=True,crossings=0),
                    normalized_hash=name)
        (directory/'report.json').write_text(json.dumps(report))
    failed=tmp_path/'failed'; failed.mkdir(); directories.append(failed)
    (failed/'report.json').write_text(json.dumps(dict(success=False,candidates=[dict(reason='cannot route')])) )
    result=compare_bundles(directories,tmp_path/'compare')
    assert result['smallest_area']==str(tmp_path/'tie')
    assert result['results'][-1]['status']=='rejected'
    assert not result['results'][1]['pareto_width_area']


def test_legacy_and_experimental_crossing_direction_guard():
    cfg=replace(profile(),interstage_routing='legacy')
    def factory(lib): lib.crossing().metadata['allowed_transforms']=[0,90,180,270]
    with pytest.raises(ValueError,match='transform'): build_layout(cfg,component_factory=factory)
