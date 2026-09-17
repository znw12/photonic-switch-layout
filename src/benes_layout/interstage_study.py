"""Reproducible full-size A/B evaluation and bounded placement studies."""
from dataclasses import replace
import json
from pathlib import Path
from .cli import save
from .config import Config
from .network import Network
from .workflow import generate, verify_bundle
from .comparison import compare_bundles
from .placement import search


def run_full(cfg,out,reuse=False):
    out=Path(out)
    bundles=[]
    modes=[('legacy',None),('continuous',None)]+[('compressed',q) for q in (40,45,50,55,60)]
    for mode,q in modes:
        profile=replace(cfg,interstage_routing=mode,shuffle_pitch=q)
        target=out/(mode+(f'-q{q}' if q else ''))
        bundles.append(target)
        old=target/'config.json'
        if reuse and old.exists() and Config.load(old).digest==profile.digest:
            verify_bundle(target)
            continue
        try:
            generate(profile,target,list(enumerate(range(cfg.active_ports))))
        except ValueError:
            if not (target/'report.json').exists(): raise
    result=compare_bundles(bundles,out/'comparison')
    best=Path(result['smallest_area'])
    original=json.loads((best/'report.json').read_text())
    repeat=out/'repeat-best'
    repeated=generate(Config.load(best/'config.json'),repeat,list(enumerate(range(cfg.active_ports))))
    for name in ('normalized_hash','uniformity','realized','summary'):
        if repeated[name]!=original[name]: raise ValueError(f'repeat differs: {name}')
    for name in ('settings.json','ports.csv','pads.csv'):
        if (repeat/name).read_bytes()!=(best/name).read_bytes(): raise ValueError(f'repeat differs: {name}')
    result['repeat']=dict(bundle=str(repeat),matches=str(best),normalized_hash=repeated['normalized_hash'],passed=True)
    compressed=[]
    for target in bundles:
        report=json.loads((target/'report.json').read_text())
        if report.get('success') and report.get('interstage',{}).get('compressed_boundaries'):
            compressed.append(str(target))
    result['compressed_verified']=compressed
    result['complete']=bool(compressed) and json.loads((out/'continuous'/'report.json').read_text()).get('success',False)
    save(out/'study.json',result)
    if not result['complete']:
        raise ValueError('full study incomplete: a verified continuous and genuinely compressed candidate are required')
    return result


def run_placement(cfg,out):
    out=Path(out)
    results=[]
    for size in (8,16):
        profile=replace(cfg,active_ports=size,internal_ports=size,input_map=None,output_map=None,
                        interstage_routing='legacy',shuffle_pitch=None)
        plan=search(Network(profile))
        root=out/f'n{size}'
        save(root/'search.json',plan)
        bundles=[]
        for row in plan['selected']:
            target=root/row['id']
            bundles.append(target)
            choice=dict(id=row['id'],gap=1.,pad=1.,corridor=1.,row_order='normal',baseline=True,stage_orders=row['orders'])
            try:
                generate(profile,target,list(enumerate(range(size))),choices=[choice])
            except ValueError:
                if not (target/'report.json').exists(): raise
        physical=compare_bundles(bundles,root/'comparison')
        baseline=json.loads((bundles[0]/'report.json').read_text())
        best=json.loads((Path(physical['smallest_area'])/'report.json').read_text())
        physical.update(search_budget=plan['budget'],evaluated=plan['evaluated'],budget_exhausted=plan['budget_exhausted'],
                        area_improved=best['summary']['area_mm2']<baseline['summary']['area_mm2'],
                        conclusion=('smaller verified layout found' if best['summary']['area_mm2']<baseline['summary']['area_mm2']
                                    else 'no improvement within this bounded search'),
                        backend='experimental-adjacent; reference backends are not part of ranking')
        for mode in ('legacy','continuous'):
            generate(replace(profile,interstage_routing=mode),root/f'reference-{mode}',list(enumerate(range(size))))
        save(root/'study.json',physical)
        results.append(dict(size=size,**physical))
    save(out/'study.json',dict(scope='8/16-port physical experiments only',results=results))
    return results
