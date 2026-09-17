"""Bounded 8/16-port placement experiments with a shared exchange backend."""
from .geometry import snap
from .interstage import key, finish


def validate_orders(net, orders):
    if net.cfg.active_ports != net.p or net.p not in (8,16):
        raise ValueError('placement experiments require 8 or 16 active/internal ports')
    identity=list(range(net.p//2))
    if (len(orders)!=net.depth or any(len(o)!=len(identity) or any(type(i) is not int for i in o) or sorted(o)!=identity for o in orders)
        or orders[0]!=identity or orders[-1]!=identity):
        raise ValueError('placement maps must be bijective with fixed first/last stages')


def boundary_permutation(net,orders,stage):
    result=[None]*net.p
    for lane,dest in enumerate(net.boundaries[stage]['permutation']):
        source=2*orders[stage][lane//2]+lane%2
        result[source]=2*orders[stage+1][dest//2]+dest%2
    return result


def permutation_block(lib,permutation):
    """Stable odd-even adjacent exchange schedule, shared by all C candidates."""
    name=key('PERM_',permutation)
    if name in lib.cells: return lib.cells[name]
    size=len(permutation)
    if sorted(permutation)!=list(range(size)): raise ValueError('invalid permutation')
    c=lib.cell(name,'shuffle')
    current=list(range(size))
    paths=[[] for _ in current]
    exchange=lib.exchange()
    width=exchange.metadata['width']
    column=0
    # Each phase compares disjoint pairs. Empty phases still preserve spacing.
    while [permutation[i] for i in current]!=list(range(size)):
        for parity in (0,1):
            used=set()
            x=snap(column*width)
            for row in range(parity,size-1,2):
                if permutation[current[row]]<permutation[current[row+1]]: continue
                lib.ref(c,exchange,x,row*lib.cfg.lane_pitch,id=f'c{column}_r{row}')
                for pin in (0,1):
                    paths[current[row+pin]].append(dict(cell=exchange.name,x=x,y=row*lib.cfg.lane_pitch,
                                                        entry=f'w{pin}',exit=f'e{1-pin}'))
                current[row],current[row+1]=current[row+1],current[row]
                used.update((row,row+1))
            for row,wire in enumerate(current):
                if row in used: continue
                straight=lib.straight(width)
                lib.ref(c,straight,x,row*lib.cfg.lane_pitch)
                paths[wire].append(dict(cell=straight.name,x=x,y=row*lib.cfg.lane_pitch,entry='w',exit='e'))
            column+=1
            if [permutation[i] for i in current]==list(range(size)): break
        if column>2*size: raise RuntimeError('adjacent exchange scheduler did not converge')
    if not column:
        straight=lib.straight(lib.cfg.grid)
        for row in range(size):
            lib.ref(c,straight,0,row*lib.cfg.lane_pitch)
            paths[row].append(dict(cell=straight.name,x=0,y=row*lib.cfg.lane_pitch,entry='w',exit='e'))
    return finish(lib,c,paths,permutation,lib.cfg.lane_pitch,snap(column*width) if column else lib.cfg.grid,
                  mode='experimental-adjacent',inverse=False,columns=column)


def proxy(net,orders):
    inversions,displacement=0,0
    for stage in range(net.depth-1):
        p=boundary_permutation(net,orders,stage)
        inversions+=sum(a>b for i,a in enumerate(p) for b in p[i+1:])
        displacement=max(displacement,max(abs(i-j) for i,j in enumerate(p)))
    return inversions,displacement


def search(net,budget=128,physical_limit=8):
    if not 1<=budget<=128 or not 1<=physical_limit<=8: raise ValueError('experiment budget exceeded')
    identity=[list(range(net.p//2)) for _ in range(net.depth)]
    validate_orders(net,identity)
    records=[]
    seen=set()
    def evaluate(orders,label):
        token=tuple(tuple(o) for o in orders)
        if token in seen or len(records)>=budget: return None
        seen.add(token)
        score=proxy(net,orders)
        row=dict(id=f'map-{len(records):03}',orders=orders,operation=label,
                 inversions=score[0],max_displacement=score[1])
        records.append(row)
        return row
    base=evaluate(identity,'identity')
    best=base
    n=net.p//2
    bits=(n-1).bit_length()
    transforms=[]
    for group in (2,4,8):
        if group>n: continue
        transforms.append((f'swap-g{group}',[i^ (group//2) for i in range(n)]))
        transforms.append((f'reverse-g{group}',[(i//group)*group+group-1-i%group for i in range(n)]))
    transforms.append(('bit-reverse',[int(f'{i:0{bits}b}'[::-1],2) for i in range(n)]))
    # Two forward/backward passes; changes are accepted only by stable proxy rank.
    for stages in (range(1,net.depth-1),range(net.depth-2,0,-1))*2:
        for stage in stages:
            start=best
            for label,permutation in transforms:
                orders=[list(o) for o in start['orders']]
                orders[stage]=[permutation[r] for r in orders[stage]]
                item=evaluate(orders,f's{stage}:{label}')
                if item and (item['inversions'],item['max_displacement'],item['id']) < (best['inversions'],best['max_displacement'],best['id']): best=item
    selected=[base]+sorted(records[1:],key=lambda r:(r['inversions'],r['max_displacement'],r['id']))[:physical_limit]
    return dict(budget=budget,evaluated=len(records),budget_exhausted=len(records)>=budget,
                records=records,selected=selected,physical_limit=physical_limit)
