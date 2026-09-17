"""Centered, two-metal channel routing with an explicit passive-overpass contract."""

from bisect import bisect_left
import heapq
from math import ceil, floor

from .geometry import snap, rectangle
from .pad_routing import pad_slots


def rails(start, count, step, stems, clearance):
    """Increasing M2 trunks, outside all foreign pad-stem keepouts."""
    result = []
    x = snap(start)
    while len(result) < count:
        i = bisect_left(stems, x - clearance + 1e-7)
        if i < len(stems) and stems[i] - x < clearance - 1e-8:
            x = snap(stems[i] + clearance)
            continue
        result.append(x)
        x = snap(x + step)
    return result


def plan(cfg, net, blocks, candidate):
    landing = cfg.via_size + 2 * cfg.via_enclosure
    step = snap((landing + cfg.metal_spacing + 2 * cfg.grid) * candidate['corridor'])
    trunk_step = snap(((landing + cfg.metal_width) / 2 + cfg.metal_spacing + 2 * cfg.grid) * candidate['corridor'])
    keep = snap(cfg.optical_metal_clearance + landing / 2 + cfg.wg_width / 2 + 2 * cfg.grid)
    count = net.p // 2
    _, pb = pad_slots(cfg, len(net.switches), 0, cfg.pad_pitch)
    span = pb[1] - pb[0]
    widths = [b.metadata['width'] for b in blocks] + [0.0]
    width = snap(max(span, sum(cfg.mzi_length + 2*keep + (max(w, count*trunk_step) if cfg.share_interstage else w+count*trunk_step) + cfg.margin for w in widths) + 2*cfg.margin))
    origin = snap(-(net.p - 1)*cfg.lane_pitch/2)
    extra_applied = False
    for _ in range(30):
        slots, bounds = pad_slots(cfg, len(net.switches), width/2, cfg.pad_pitch)
        slots.sort(key=lambda s: s['px'])
        stems = [s['px'] for s in slots]
        if any(b-a < step for a,b in zip(stems, stems[1:])):
            raise ValueError('two-row pad stagger cannot fit independent via stems')

        def stage_at(index, x):
            launch = snap(x + cfg.mzi_length + keep)
            txs = rails(launch + keep, count, trunk_step, stems, trunk_step)
            escape = snap(launch + keep if cfg.share_interstage else txs[-1] + keep)
            route = snap(escape + widths[index])
            end = snap(max(route, txs[-1] + keep))
            return dict(stage=index, band=0, column=index, angle=0, y=origin,
                        origin_y=origin, x=snap(x), escape_start=snap(x+cfg.mzi_length),
                        escape_end=escape, route_end=route, launch_x=launch,
                        trunk_xs=txs, occupied_end=end, end=width)

        limits = [0.0]*net.depth
        cap = width - cfg.margin
        for s in reversed(range(net.depth)):
            lo, hi = floor((cap-cfg.mzi_length-widths[s]-count*cfg.pad_pitch-4*keep)/cfg.grid), floor(cap/cfg.grid)
            while hi-lo > 1:
                mid = (lo+hi)//2
                if stage_at(s, mid*cfg.grid)['occupied_end'] <= cap:
                    lo = mid
                else:
                    hi = mid
            limits[s] = snap(lo*cfg.grid)
            cap = limits[s] - cfg.margin*candidate['gap']
        if limits[0] >= cfg.margin:
            if cfg.electrical_width_extra and not extra_applied:
                width = snap(width + cfg.electrical_width_extra)
                extra_applied = True
                continue
            stages, cursor = [], cfg.margin
            for s in range(net.depth):
                group = stems[s*count:(s+1)*count]
                desired = snap((group[0]+group[-1])/2 - cfg.mzi_length - keep - count*trunk_step/2
                               + cfg.electrical_stage_bias)
                stage = stage_at(s,max(cursor,min(desired,limits[s])))
                stages.append(stage)
                cursor = snap(stage['occupied_end']+cfg.margin*candidate['gap'])
            return stages, width, slots, bounds, step
        width = snap(width + cfg.margin-limits[0] + 2*cfg.grid)
    raise ValueError('two-row floorplan did not converge')


def channel_levels(sources, destinations, clearance):
    """Optimal interval coloring; vertical routes use M2, so no M1-stem DAG."""
    intervals = sorted((min(a,b),max(a,b),i) for i,(a,b) in enumerate(zip(sources,destinations)))
    busy, free, levels, count = [], [], [0]*len(sources), 0
    for a,b,i in intervals:
        while busy and busy[0][0]+clearance <= a:
            _, level = heapq.heappop(busy)
            heapq.heappush(free, level)
        if free:
            level = heapq.heappop(free)
        else:
            level, count = count, count+1
        levels[i] = level
        heapq.heappush(busy,(b,level))
    return levels


def route(lib, m, groups, terminals, optical, step, slots):
    cfg = lib.cfg
    banks = {side: sorted((t for t in terminals if t['side']==side),key=lambda t:t['tx']) for side in ('south','north')}
    levels = {side:channel_levels([t['tx'] for t in bank],[s['px'] for s in slots],step) for side,bank in banks.items()}
    maximum = max(max(v) for v in levels.values())
    edge = max(abs(optical[1]),abs(optical[3]))
    transfer = snap(edge + cfg.margin + (maximum+2)*step)
    pad_base = snap(transfer + cfg.margin + cfg.pad_size/2)
    m['electrical_plan'] = dict(mode=cfg.electrical_routing, channel_levels=maximum+1,
        transfer_y=transfer, pad_base_y=pad_base, via_per_net=5,
        shared_interstage=cfg.share_interstage, optical_center_y=0,
        passive_m2_contract='insulated-placeholder-v1')
    if cfg.electrical_routing == 'three-row':
        m['electrical_plan']['stage_bias_um'] = cfg.electrical_stage_bias
        m['electrical_plan']['width_extra_um'] = cfg.electrical_width_extra
    for side, sign in (('south',-1),('north',1)):
        for i,(t,slot,level) in enumerate(zip(banks[side],slots,levels[side])):
            tx, sx = t['tx'], slot['px']
            fy = snap(sign*(edge+cfg.margin+level*step))
            py = snap(sign*(pad_base+slot['row']*cfg.pad_row_pitch))
            ly = snap(sign*transfer)
            launch = t['launch_x']
            prefix = 'TWO' if cfg.pad_rows == 2 else 'THREE'
            cell = lib.cell(f'{prefix}_NET_{side}_{i}', 'electrical_route')
            segments = []
            def metal(layer,a,b):
                if a==b:
                    return
                if a[0]!=b[0] and a[1]!=b[1]:
                    raise ValueError('non-Manhattan electrical segment')
                w = cfg.metal_width/2
                lib.poly(cell,layer,rectangle(min(a[0],b[0])-w,min(a[1],b[1])-w,
                                               max(a[0],b[0])+w,max(a[1],b[1])+w))
                segments.append(dict(layer=layer,start=list(a),end=list(b)))
            metal('M1',(t['x'],t['y']),(launch,t['y']))
            metal('M2',(launch,t['y']),(tx,t['y']))
            metal('M2',(tx,t['y']),(tx,fy))
            metal('M1',(tx,fy),(sx,fy))
            # Join nearby same-net M2 landings instead of leaving a sub-rule slot.
            if abs(tx-sx) < cfg.via_size+2*cfg.via_enclosure+cfg.metal_spacing:
                metal('M2',(tx,fy),(sx,fy))
            metal('M2',(sx,fy),(sx,ly))
            metal('M1',(sx,ly),(sx,py))
            vias = [[launch,t['y']],[tx,fy],[sx,fy],[sx,ly],[sx,py]]
            for at in vias:
                lib.ref(cell,lib.via(),*at)
            lib.ref(groups['ELECTRICAL_FANOUT'],cell,id=t['net'])
            lib.ref(groups[side.upper()+'_PADS'],lib.pad(),sx,py,id=t['net'])
            m['electrical'].append({**t,'cell':cell.name,'pad':[sx,py],
                'pad_row':slot['row'],'pad_column':slot['column'],
                'pad_row_offset':slot['offset'],'vias':vias,'fanout_y':fy,'segments':segments})
    half = cfg.pad_size/2
    last_row = max(s['row'] for s in slots)
    return [snap(min(s['px'] for s in slots)-half),
            snap(-pad_base-last_row*cfg.pad_row_pitch-half),
            snap(max(s['px'] for s in slots)+half),
            snap(pad_base+last_row*cfg.pad_row_pitch+half)]


def overpass_records(m):
    """Actual M2/optical proximity windows, tied to primitive instance identities."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    from .verify import spatial_objects, VerificationError
    objs, shapes, _ = spatial_objects(m)
    tree = STRtree(shapes)
    cfg = m['config']
    records = []
    for e in m['electrical']:
        polys = [Polygon(p['points']) for p in m['cells'][e['cell']]['polygons'] if p['layer']=='M2']
        metal = unary_union(polys)
        for index in sorted(tree.query(metal,predicate='dwithin',distance=cfg['optical_metal_clearance'])):
            obj = objs[int(index)]
            if m['cells'][obj[0]]['kind'] not in ('straight','segment','bend','crossing'):
                raise VerificationError('two-row M2 overlaps an unauthorized optical device')
            conflict = metal.intersection(shapes[int(index)].buffer(cfg['optical_metal_clearance']))
            if not conflict.is_empty:
                g = cfg['grid']
                a,b,c,d = conflict.bounds
                records.append(dict(net=e['net'],optical=list(obj),
                    bbox=[floor(a/g)*g,floor(b/g)*g,ceil(c/g)*g,ceil(d/g)*g]))
    return records


def statistics(m):
    """Report measured routing extents separately from the pad-limited die."""
    return {
        **m['electrical_plan'],
        'passive_overpass_windows': len(m['passive_overpasses']),
        'fabric_span_um': m['stages'][-1]['occupied_end']-m['stages'][0]['x'],
        'shared_width_um': sum(max(0,min(s['route_end'],s['trunk_xs'][-1])-s['escape_end']) for s in m['stages']),
        'metal_length_um': sum(abs(s['end'][0]-s['start'][0])+abs(s['end'][1]-s['start'][1]) for e in m['electrical'] for s in e['segments']),
    }
