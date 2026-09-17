"""Three-row partial-column pads and compatibility of the shared metal router."""
import json

import pytest

from benes_layout.config import Config
from benes_layout.layout import build_layout
from benes_layout.verify import verify_manifest,verify_gds,VerificationError
from benes_layout.workflow import verify_bundle
from benes_layout.cli import main
from benes_layout.pad_routing import pad_slots


def profile(n=5, **kw):
    data=dict(active_ports=n,pad_rows=3,pad_row_stagger=25,lane_pitch=60,
              electrical_routing='three-row',interstage_routing='continuous',
              share_interstage=True,max_candidates=1,gap_factors=(1.0,),corridor_factors=(1.0,))
    data.update(kw)
    return Config(**data)


@pytest.mark.parametrize('kw',[dict(pad_rows=2),dict(pad_rows=4),dict(pad_pitch=80),
    dict(fold_bands=3),dict(electrical_stage_bias=float('nan')),
    dict(electrical_stage_bias=True),dict(electrical_stage_bias=.0005),
    dict(electrical_width_extra=-1),dict(electrical_width_extra=True),
    dict(electrical_width_extra=float('inf'))])
def test_invalid_three_row(kw):
    with pytest.raises(ValueError):profile(**kw)


def test_legacy_rejects_bias_and_reference_slots():
    with pytest.raises(ValueError):Config(electrical_stage_bias=100)
    with pytest.raises(ValueError):Config(electrical_width_extra=100)
    slots,bounds=pad_slots(profile(100),832,0,100)
    assert [sum(s['row']==i for s in slots) for i in range(3)]==[278,277,277]
    assert [s['row'] for s in slots if s['column']==277]==[0]
    assert bounds==[-13880,13880]


@pytest.mark.parametrize('n,shared,bias,reverse',[(1,True,0,False),(4,False,200,False),
    (5,True,-200,False),(5,True,200,True),(16,True,0,True)])
def test_physical_three_row(tmp_path,n,shared,bias,reverse):
    cfg=profile(n,share_interstage=shared,electrical_stage_bias=bias,
                electrical_width_extra=200 if bias else 0,
                margin=40 if n==16 else 100,pad_row_pitch=70 if n==16 else 100)
    choice=dict(id='test',gap=1,pad=1,corridor=1,row_order='reverse' if reverse else 'normal')
    lib,m=build_layout(cfg,choice)
    verify_manifest(m)
    path=tmp_path/'layout.gds';names=lib.write_gds(m['top'],path)
    assert verify_gds(path,m,names)['via_count']==5*len(m['electrical'])
    assert m['electrical_plan']['mode']=='three-row'
    for side in ('north','south'):
        bank=[e for e in m['electrical'] if e['side']==side]
        assert [sum(e['pad_row']==r for e in bank) for r in range(3)]==[
            (len(bank)+2-r)//3 for r in range(3)]
    assert m['die_bbox'][1]==-m['die_bbox'][3]


@pytest.mark.parametrize('defect',['last_column','row_offset','missing_pad','via','mode'])
def test_three_row_faults(defect):
    lib,m=build_layout(profile())
    e=m['electrical'][-1]
    if defect=='last_column':e['pad_column']+=1
    elif defect=='row_offset':e['pad_row_offset']+=1
    elif defect=='missing_pad':m['electrical'].pop()
    elif defect=='via':lib.cells[e['cell']].refs.pop()
    else:m['electrical_plan']['mode']='two-row'
    m['cells']=lib.export()
    with pytest.raises(VerificationError):verify_manifest(m)


def test_three_row_window_fault(tmp_path):
    lib,m=build_layout(profile())
    m['passive_overpasses'].pop()
    path=tmp_path/'bad.gds';names=lib.write_gds(m['top'],path)
    with pytest.raises(VerificationError,match='windows'):
        verify_gds(path,m,names)


def test_cli_three_row(tmp_path):
    path=tmp_path/'config.json';path.write_text(json.dumps(profile(4).to_dict()))
    out=tmp_path/'bundle'
    assert main(['generate','--config',str(path),'--electrical-stage-bias','-100',
                 '--electrical-width-extra','100','--out',str(out)])==0
    assert (out/'pads_detail.png').is_file()
    assert verify_bundle(out)['gds_readback_passed']
