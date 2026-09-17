"""Bounded three-row planning screen followed by complete physical validation."""
from dataclasses import replace
import json
from pathlib import Path

from .config import Config
from .geometry import Library
from .network import Network
from .two_row import plan, channel_levels
from .cli import save


def screen(cfg):
    cfg = replace(cfg, electrical_routing='three-row',pad_rows=3,pad_distribution='central',
                  fold_bands=1,band_stage_counts=None,interstage_routing='continuous',shuffle_pitch=None,
                  share_interstage=True,pad_row_stagger=25,pad_row_pitch=100,margin=100,
                  electrical_stage_bias=0,electrical_width_extra=0,
                  pad_factors=(1.0,),gap_factors=(1.0,),corridor_factors=(1.0,),
                  row_orders=('normal',),max_candidates=1)
    if cfg.active_ports != 100 or cfg.internal_ports != 128:
        raise ValueError('three-row reference study requires 100 active / 128 internal ports')
    net,lib=Network(cfg),Library(cfg)
    blocks=[lib.shuffle_block(b['size'],b['inverse']) for b in net.boundaries]
    choices=[dict(electrical_width_extra=e,electrical_stage_bias=b,margin=100,pad_row_pitch=100)
             for e in (0,200,400,800,1200,1600,2400) for b in (-600,-300,0,300,600)]
    choices += [dict(electrical_width_extra=0,electrical_stage_bias=0,margin=m,pad_row_pitch=p)
                for m in (100,80,60,40) for p in (100,80,70)]
    records,seen=[],set()
    for params in choices:
        key=tuple(params.items())
        if key in seen:continue
        seen.add(key)
        candidate=replace(cfg,**params)
        stages,width,slots,_,step=plan(candidate,net,blocks,dict(gap=1,pad=1,corridor=1))
        levels=channel_levels([x for s in stages for x in s['trunk_xs']],
                              [s['px'] for s in slots],step)
        height=(net.p-1)*cfg.lane_pitch+cfg.mzi_height-cfg.lane_pitch+2*(
            3*candidate.margin+cfg.pad_size+max(s['row'] for s in slots)*candidate.pad_row_pitch
            +(max(levels)+2)*step)
        records.append(dict(parameters=params,planned_width_mm=(width+2*candidate.margin)/1000,
                            planned_height_mm=height/1000,
                            planned_area_mm2=(width+2*candidate.margin)*height/1e6,
                            channel_levels=max(levels)+1))
    best=min(records,key=lambda r:(r['planned_area_mm2'],abs(r['parameters']['electrical_stage_bias']),
                                  r['parameters']['electrical_width_extra']))
    return cfg,records,best


def run(cfg,out,reuse=False):
    from .workflow import generate,verify_bundle
    from .comparison import compare_bundles
    out=Path(out)
    base,records,best=screen(cfg)
    save(out/'planning-screen.json',dict(scope='Planning only; no physical verification implied.',
        candidates=records,selected=best,global_optimum_proven=False))
    profiles={'baseline':base,'optimized':replace(base,**best['parameters']),
              'separate':replace(base,share_interstage=False)}
    for name,profile in profiles.items():
        target=out/name
        if reuse and (target/'report.json').exists():
            report=json.loads((target/'report.json').read_text())
            if (report.get('success') and Config.load(target/'config.json').digest==profile.digest
                and all(report['checks'].get(k) for k in ('manifest_geometry_passed','gds_readback_passed','electrical_extraction_passed'))):
                continue
        generate(profile,target,list(enumerate(range(100))))
    result=compare_bundles([out/n for n in profiles],out/'comparison')
    chosen=Path(result['smallest_area'])
    original=json.loads((chosen/'report.json').read_text())
    repeated=generate(Config.load(chosen/'config.json'),out/'repeat-best',list(enumerate(range(100))))
    for field in ('normalized_hash','summary','uniformity','realized','electrical'):
        if original[field]!=repeated[field]:raise ValueError(f'three-row repeat differs: {field}')
    for file in ('settings.json','pads.csv','ports.csv'):
        if (chosen/file).read_bytes()!=(out/'repeat-best'/file).read_bytes():
            raise ValueError(f'three-row repeat differs: {file}')
    result['planning_candidates']=len(records)
    result['repeat']=dict(passed=True,normalized_hash=repeated['normalized_hash'],
                          independent_readback=verify_bundle(out/'repeat-best'))
    save(out/'study.json',result)
    return result
