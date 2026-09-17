from dataclasses import replace
import pytest
from benes_layout.config import Config
from benes_layout.network import Network
from benes_layout.layout import build_layout
from benes_layout.placement import search,validate_orders,boundary_permutation,permutation_block
from benes_layout.geometry import Library
from benes_layout.verify import verify_manifest,VerificationError


def profile(n=8):
    return Config(active_ports=n,pad_rows=4,pad_distribution='stage',pad_row_stagger=25,lane_pitch=60)


@pytest.mark.parametrize('n',[8,16])
def test_search_and_independent_mapping(n):
    cfg=profile(n)
    net=Network(cfg)
    plan=search(net)
    assert plan==search(net)
    assert plan['evaluated']<=128 and 1<len(plan['selected'])<=9
    for row in plan['selected']:
        validate_orders(net,row['orders'])
        choice=dict(id=row['id'],gap=1.,pad=1.,corridor=1.,row_order='normal',stage_orders=row['orders'])
        lib,m=build_layout(cfg,choice)
        verify_manifest(m)
        assert m['crossing_count']==row['inversions']
        assert all(len(m['placement_map'][sid]['pins'])==4 for sid in net.switches)


@pytest.mark.parametrize('defect',['duplicate','missing','pin','row','pad_stage'])
def test_mapping_faults(defect):
    cfg=profile()
    row=search(Network(cfg))['selected'][1]
    choice=dict(id='map',gap=1.,pad=1.,corridor=1.,row_order='normal',stage_orders=row['orders'])
    _,m=build_layout(cfg,choice)
    if defect=='duplicate': m['candidate']['stage_orders'][1][0]=m['candidate']['stage_orders'][1][1]
    elif defect=='missing': m['placement_map'].pop(next(iter(m['placement_map'])))
    elif defect=='pin': next(iter(m['placement_map'].values()))['pins']['i0']='i1'
    elif defect=='row': m['instances'][0]['row']=2
    else: m['electrical'][0]['pad_group']=1
    with pytest.raises((ValueError,VerificationError)): verify_manifest(m)


def test_scope_and_identity_zero_crossing():
    net=Network(profile(32))
    with pytest.raises(ValueError,match='8 or 16'): search(net)
    c=permutation_block(Library(profile()),list(range(8)))
    assert not any(t['crossings'] for t in c.tracks)
