"""Fixed-width partial trunk/pad alignment with mixed one/three-turn routes."""
from bisect import bisect_left, insort
from collections import Counter

from .geometry import snap, rectangle
from .two_row import channel_levels


def allocate(cfg, sources, left, right, step):
    """Reserve exact alignments, then fill legal holes without crossing M2 trunks.

    Returns slots in source order, not x order. This intentionally frees the pad
    assignment from a global ordering constraint; every slot retains its net.
    """
    total = len(sources)
    caps = [(total + 2 - r) // 3 for r in range(3)]
    rows, xs, slots, matched = [[], [], []], [], [], set()
    trunk_clear = snap((cfg.via_size + 2*cfg.via_enclosure + cfg.metal_width)/2
                       + cfg.metal_spacing + 2*cfg.grid)
    lo, hi = snap(left + cfg.pad_size/2), snap(right - cfg.pad_size/2)

    def conflicts(values, x, clearance):
        j = bisect_left(values, x)
        return [v + clearance for v in values[max(0, j-1):j+1]
                if abs(v-x) < clearance - cfg.grid/10]

    def add(x, row, source=None):
        insort(rows[row], x)
        insort(xs, x)
        slots.append(dict(px=x, row=row, source=source))

    for i, x in enumerate(sources):
        available = [r for r in range(3) if len(rows[r]) < caps[r]
                     and lo <= x <= hi and not conflicts(xs, x, step)
                     and not conflicts(rows[r], x, cfg.pad_pitch)]
        if available:
            add(x, min(available, key=lambda r: (len(rows[r]), r)), i)
            matched.add(i)
    for row in range(3):
        x = lo
        while x <= hi and len(rows[row]) < caps[row]:
            obstacles = (conflicts(sources, x, trunk_clear) + conflicts(xs, x, step)
                         + conflicts(rows[row], x, cfg.pad_pitch))
            if obstacles:
                x = snap(max(obstacles))
                continue
            add(x, row)
            x = snap(x + cfg.pad_pitch)
        if len(rows[row]) != caps[row]:
            raise ValueError('aligned pad allocation cannot fit the fixed width at this pitch')
    remaining = iter(i for i in range(total) if i not in matched)
    for slot in sorted(slots, key=lambda s: s['px']):
        if slot['source'] is None:
            slot['source'] = next(remaining)
        slot['column'] = bisect_left(rows[slot['row']], slot['px'])
        # Each row has its own coordinates; no fixed horizontal row-offset contract.
        slot['offset'] = 0.0
    return sorted(slots, key=lambda s: s['source'])


def schedule(sources, slots, step):
    indirect = [i for i, (x, s) in enumerate(zip(sources, slots)) if x != s['px']]
    local = channel_levels([sources[i] for i in indirect], [slots[i]['px'] for i in indirect], step)
    levels = [-1] * len(sources)
    for i, level in zip(indirect, local):
        levels[i] = level
    return levels


def route(lib, m, groups, terminals, optical, step):
    cfg = lib.cfg
    banks = {side: sorted((t for t in terminals if t['side'] == side), key=lambda t:t['tx'])
             for side in ('south', 'north')}
    sources = [t['tx'] for t in banks['north']]
    slots = allocate(cfg, sources, optical[0], optical[2], step)
    levels = schedule(sources, slots, step)
    edge = max(abs(optical[1]), abs(optical[3]))
    transfer = snap(edge + cfg.margin + (max(levels, default=-1)+2)*step)
    pad_base = snap(transfer + cfg.margin + cfg.pad_size/2)
    m['electrical_plan'] = dict(mode=cfg.electrical_routing, fanout='aligned',
        channel_levels=max(levels, default=-1)+1, transfer_y=transfer, pad_base_y=pad_base,
        via_per_net=None, shared_interstage=cfg.share_interstage, optical_center_y=0,
        passive_m2_contract='insulated-placeholder-v1',
        stage_bias_um=cfg.electrical_stage_bias, width_extra_um=cfg.electrical_width_extra)
    for side, sign in (('south', -1), ('north', 1)):
        for i, (t, slot, level) in enumerate(zip(banks[side], slots, levels)):
            tx, sx, launch = t['tx'], slot['px'], t['launch_x']
            direct = tx == sx
            fy = snap(sign*(edge + cfg.margin + max(0, level)*step))
            ly = snap(sign*transfer)
            py = snap(sign*(pad_base + slot['row']*cfg.pad_row_pitch))
            cell = lib.cell(f'ALIGNED_NET_{side}_{i}', 'electrical_route')
            segments = []

            def metal(layer, a, b):
                if a == b:
                    return
                if a[0] != b[0] and a[1] != b[1]:
                    raise ValueError('non-Manhattan aligned segment')
                w = cfg.metal_width/2
                lib.poly(cell, layer, rectangle(min(a[0], b[0])-w, min(a[1], b[1])-w,
                                                max(a[0], b[0])+w, max(a[1], b[1])+w))
                segments.append(dict(layer=layer, start=list(a), end=list(b)))

            m2_source = t.get('source_layer','M1') == 'M2'
            if m2_source:
                metal('M2', (t['x'], t['y']), (tx, t['y']))
            else:
                metal('M1', (t['x'], t['y']), (launch, t['y']))
                metal('M2', (launch, t['y']), (tx, t['y']))
            if direct:
                metal('M2', (tx, t['y']), (tx, ly))
                vias = [[launch, t['y']], [tx, ly], [sx, py]]
            else:
                metal('M2', (tx, t['y']), (tx, fy))
                metal('M1', (tx, fy), (sx, fy))
                # Close sub-rule same-net slots around enlarged via landings.
                if abs(tx-sx) < cfg.via_size + 2*cfg.via_enclosure + cfg.metal_spacing:
                    metal('M2', (tx, fy), (sx, fy))
                metal('M2', (sx, fy), (sx, ly))
                vias = [[launch, t['y']], [tx, fy], [sx, fy], [sx, ly], [sx, py]]
            metal('M1', (sx, ly), (sx, py))
            if m2_source:
                vias = vias[1:]
            for at in vias:
                lib.ref(cell, lib.via(), *at)
            lib.ref(groups['ELECTRICAL_FANOUT'], cell, id=t['net'])
            lib.ref(groups[side.upper()+'_PADS'], lib.pad(), sx, py, id=t['net'])
            m['electrical'].append({**t, 'cell':cell.name, 'pad':[sx, py],
                'pad_row':slot['row'], 'pad_column':slot['column'], 'pad_row_offset':0.0,
                'vias':vias, 'fanout_y':fy, 'segments':segments, 'direct_pad':direct})
    half = cfg.pad_size/2
    last = max(s['row'] for s in slots)
    return [snap(min(s['px'] for s in slots)-half), snap(-pad_base-last*cfg.pad_row_pitch-half),
            snap(max(s['px'] for s in slots)+half), snap(pad_base+last*cfg.pad_row_pitch+half)]


def routing_metrics(m):
    """Measure directions on the terminal-to-pad chain, ignoring layer-only changes.

    The optional same-net M2 landing bridge parallels an M1 segment and is not
    another segment in the terminal-to-pad chain.
    """
    turns, lengths = [], []
    for e in m['electrical']:
        directions, length, end = [], 0.0, [e['x'], e['y']]
        for s in e['segments']:
            a, b = s['start'], s['end']
            if a != end:
                continue  # Parallel via-landing bridge, not part of the serial path.
            direction = (0 if a[0] == b[0] else 1, (b[0]+b[1]) > (a[0]+a[1]))
            if not directions or directions[-1] != direction:
                directions.append(direction)
            length += abs(b[0]-a[0]) + abs(b[1]-a[1])
            end = b
        if end != e['pad']:
            raise ValueError('electrical metrics found an incomplete path')
        turns.append(len(directions)-1)
        lengths.append(length)
    bank = [e for e in m['electrical'] if e['side'] == 'north']
    spacings = []
    for row in range(m['config']['pad_rows']):
        xs = sorted(e['pad'][0] for e in bank if e['pad_row'] == row)
        spacings.extend(b-a for a,b in zip(xs, xs[1:]))
    return dict(turns_total=sum(turns), turns_per_net_mean=sum(turns)/len(turns),
                turns_histogram={str(k):v for k,v in sorted(Counter(turns).items())},
                direct_pad_nets=sum(e['tx'] == e['pad'][0] for e in m['electrical']),
                vias_total=sum(len(e['vias']) for e in m['electrical']),
                serial_metal_length_um=sum(lengths),
                same_row_pitch_min_um=min(spacings, default=None),
                same_row_pitch_max_um=max(spacings, default=None))
