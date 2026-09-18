"""Stage-local common grounds and compact signal-only escape planning."""
from collections import Counter
from math import ceil

from .geometry import snap, rectangle


def tap_stages(depth, count):
    return [min(depth-1, (2*i+1)*depth//(2*count)) for i in range(count)]


def plan(cfg, net, blocks, candidate):
    from .aligned_fanout import allocate
    count = net.p//4
    landing = cfg.via_size+2*cfg.via_enclosure
    step = snap((landing+cfg.metal_spacing+2*cfg.grid)*candidate['corridor'])
    trunk_step = snap(((landing+cfg.metal_width)/2+cfg.metal_spacing+2*cfg.grid)*candidate['corridor'])
    keep = snap(cfg.optical_metal_clearance+landing/2+cfg.wg_width/2+2*cfg.grid)
    origin = -(net.p-1)*cfg.lane_pitch/2
    widths = [b.metadata['width'] for b in blocks]+[0.0]
    taps = tap_stages(net.depth,cfg.ground_pads_per_side)
    bank_count = len(net.switches)//2+len(taps)
    pad_span = (ceil(bank_count/3)-1)*cfg.pad_pitch+cfg.pad_size
    # Grow only empty stage gaps if the aligned pad allocator needs more room.
    for attempt in range(40):
        cursor=cfg.margin
        stages=[]
        gap=cfg.margin*candidate['gap']+attempt*20
        for s,w in enumerate(widths):
            start=snap(cursor+cfg.mzi_length)
            launch=snap(start+keep)
            trunks=[snap(launch+keep+i*trunk_step) for i in range(count)]
            escape=snap(launch+keep)
            end=snap(max(escape+w,trunks[-1]+keep))
            stages.append(dict(stage=s,band=0,column=s,angle=0,y=origin,origin_y=origin,
                x=snap(cursor),escape_start=start,escape_end=escape,route_end=snap(escape+w),
                launch_x=launch,trunk_xs=trunks,occupied_end=end,end=0))
            cursor=snap(end+gap)
        width=snap(max(cursor,pad_span+2*cfg.margin))
        for stage in stages:stage['end']=width
        # The active electrode endpoint is computed by the device constructor.
        from .geometry import Library
        gx=Library(cfg).mzi().ports['G'][0]
        sources=sorted([x for s in stages for x in s['trunk_xs']]+
                       [stages[s]['x']+gx for s in taps])
        try:
            allocate(cfg,sources,0,width,step)
        except ValueError:
            continue
        return stages,width,[],[0,width],step
    raise ValueError('compact ground/signal pad placement cannot fit')


def segments(m,cfg):
    """Deterministic, bounded common-ground contract independent of pad fanout."""
    md=m['cells']['MZI']['metadata'] if 'cells' in m else None
    # Ground bridge follows the symmetric active electrode endpoint.
    if md is None:
        from .geometry import Library
        md=Library(cfg).mzi().metadata
    gx=md['active_x'][1]-60
    xs=[snap(s['x']+gx) for s in m['stages']]
    outer=snap(max(abs(m['extents']['core'][1]),abs(m['extents']['core'][3]))+cfg.margin/2)
    wires=[dict(layer='M2',start=[x,-outer],end=[x,outer]) for x in xs]
    wires += [dict(layer='M1',start=[xs[0],sign*outer],end=[xs[-1],sign*outer])
              for sign in (-1,1)]
    vias=[[x,sign*outer] for x in xs for sign in (-1,1)]
    return wires,vias


def polygons(wires,cfg):
    half=cfg.metal_width/2
    return [dict(layer=s['layer'],points=[[snap(v) for v in p] for p in rectangle(
        min(s['start'][0],s['end'][0])-half,min(s['start'][1],s['end'][1])-half,
        max(s['start'][0],s['end'][0])+half,max(s['start'][1],s['end'][1])+half)]) for s in wires]


def add(lib,m,top):
    cfg=lib.cfg
    wires,vias=segments(m,cfg)
    cell=lib.cell('COMMON_GROUND','ground_network')
    for p in polygons(wires,cfg):lib.poly(cell,p['layer'],p['points'])
    for at in vias:lib.ref(cell,lib.via(),*at)
    lib.ref(top,cell)
    for e in m['electrical']:
        e['electrical_net']='GND' if e['terminal']=='G' else e['net']
    m['ground_network']=dict(net='GND',cell=cell.name,segments=wires,vias=vias,
        ground_pads=2*cfg.ground_pads_per_side,mode='stage-local',
        tap_stages=tap_stages(len(m['stages']),cfg.ground_pads_per_side),
        members=[f"{i['id']}:G" for i in m['instances']],scope='quasistatic common ground')


def verify(m,cfg):
    from .verify import require
    ground=m.get('ground_network',{});c=m['cells'].get(ground.get('cell'),{})
    wires,vias=segments(m,cfg)
    require(ground.get('net')=='GND' and ground.get('mode')=='stage-local'
            and c.get('kind')=='ground_network','missing stage-local ground')
    require(ground.get('segments')==wires and ground.get('vias')==vias
            and c['polygons']==polygons(wires,cfg),'stage ground geometry differs from contract')
    require(Counter((r['cell'],r['x'],r['y'],r['angle']) for r in c['refs'])
            ==Counter(('VIA',*at,0) for at in vias),'stage ground vias differ from contract')
    require(ground.get('members')==[f"{i['id']}:G" for i in m['instances']],
            'stage ground misses MZI terminals')
    taps=tap_stages(len(m['stages']),cfg.ground_pads_per_side)
    require(ground.get('tap_stages')==taps and ground.get('ground_pads')==2*len(taps),
            'ground tap inventory mismatch')
    for side in ('north','south'):
        pads=[e for e in m['electrical'] if e['side']==side and e['terminal']=='G']
        require(sorted(e['stage'] for e in pads)==taps,'ground pads are not distributed by stage')
    for e in m['electrical']:
        require(e.get('electrical_net')==('GND' if e['terminal']=='G' else e['net']),
                'compact signal/ground net class mismatch')


def permitted_device_m2(m,cfg,instance_x):
    """Only the verified ground-spine strip, never an entire device rectangle."""
    from shapely.geometry import box
    gx=m['cells']['MZI']['metadata']['active_x'][1]-60+instance_x
    half=cfg.metal_width/2
    extent=max(abs(m['extents']['core'][1]),abs(m['extents']['core'][3]))+cfg.margin/2
    return box(gx-half,-extent,gx+half,extent)
