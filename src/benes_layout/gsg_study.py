"""Reference physical-MZI matrix generation and independent repeat evidence."""
import json
from pathlib import Path
from .config import Config


def run(cfg,out,reuse=False):
    from .workflow import generate,verify_bundle
    from .cli import save
    if cfg.mzi_model!='paper-gsg' or cfg.active_ports!=100 or cfg.internal_ports!=128:
        raise ValueError('GSG reference study requires paper-gsg and 100 active / 128 internal ports')
    out=Path(out);target=out/'n100';repeat=out/'repeat'
    original=None
    if reuse and (target/'report.json').exists():
        r=json.loads((target/'report.json').read_text())
        if (r.get('success') and Config.load(target/'config.json').digest==cfg.digest
                and all(r['checks'].get(k) for k in ('manifest_geometry_passed','gds_readback_passed','electrical_extraction_passed'))):
            original=r
    if original is None:original=generate(cfg,target,list(enumerate(range(100))))
    repeated=generate(cfg,repeat,list(enumerate(range(100))))
    for key in ('normalized_hash','summary','uniformity','realized','electrical','device','ground_network'):
        if original[key]!=repeated[key]:raise ValueError(f'GSG repeat differs: {key}')
    if original.get('crossing_device')!=repeated.get('crossing_device'):
        raise ValueError('GSG repeat differs: crossing_device')
    for name in ('settings.json','pads.csv','ports.csv'):
        if (target/name).read_bytes()!=(repeat/name).read_bytes():raise ValueError(f'GSG repeat table differs: {name}')
    result=dict(summary=original['summary'],device=original['device'],
        repeated_geometry_and_tables=True,normalized_hash=original['normalized_hash'],
        independent_readback=verify_bundle(repeat))
    if 'crossing_device' in original:result['crossing_device']=original['crossing_device']
    save(out/'study.json',result)
    return result
