"""Independent analytic contracts for interstage optical primitives."""
from math import hypot, atan2, degrees, cos, sin, pi
from .geometry import snap, rectangle
from waksman_layout.verify import require


def verify_transfers(c, forward):
    expected = forward + [{**t, "ports": list(reversed(t["ports"]))} for t in forward]
    require(c["tracks"] == expected, "primitive through metrics corrupted")


def verify_segment(c, cfg):
    a,b = c["metadata"]["centerline"]
    dx,dy = b[0]-a[0], b[1]-a[1]
    length = hypot(dx,dy)
    require(length >= cfg.grid, "degenerate segment")
    ux,uy = dx/length,dy/length
    w = cfg.wg_width/2
    pa,pb = [a[0]-ux*3*cfg.grid,a[1]-uy*3*cfg.grid],[b[0]+ux*3*cfg.grid,b[1]+uy*3*cfg.grid]
    expected = [[pa[0]-uy*w,pa[1]+ux*w],[pb[0]-uy*w,pb[1]+ux*w],
                [pb[0]+uy*w,pb[1]-ux*w],[pa[0]+uy*w,pa[1]-ux*w]]
    require(c["polygons"] == [dict(layer="WG",points=[[snap(x),snap(y)] for x,y in expected])],
            "segment polygon differs from centerline")
    angle = degrees(atan2(dy,dx))%360
    require(c["ports"] == {"w":[*a,(angle+180)%360],"e":[*b,angle]},
            "segment port/tangent corrupted")
    verify_transfers(c,[dict(ports=["w","e"],length=length,bends=0,angle=0,crossings=0,min_radius=None)])


def verify_arc_ports(c,cfg):
    arc = c["metadata"]["arc"]
    cx,cy = arc["center"]
    r,a,b = arc["radius"],arc["start"],arc["end"]
    sign = 1 if b>a else -1
    expected = {"w":[snap(cx+r*cos(a)),snap(cy+r*sin(a)),(degrees(a+sign*pi/2)+180)%360],
                "e":[snap(cx+r*cos(b)),snap(cy+r*sin(b)),degrees(b+sign*pi/2)%360]}
    require(c["ports"] == expected,"arc port/tangent corrupted")
    verify_transfers(c,[dict(ports=["w","e"],length=r*abs(b-a),bends=1,angle=abs(b-a),crossings=0,min_radius=r)])


def verify_crossing(c,cfg):
    h,w = cfg.crossing_half_length,cfg.wg_width/2
    require(c["ports"] == {"w":[-h,0,180],"e":[h,0,0],"s":[0,-h,270],"n":[0,h,90]},
            "crossing ports corrupted")
    if cfg.crossing_model=='cosine':
        from .cosine_crossing import verify
        verify(c,cfg)
    else:
        polygons = [rectangle(-h,-w,h,w),rectangle(-w,-h,w,h)]
        require(c["polygons"] == [dict(layer="WG",points=[[snap(x),snap(y)] for x,y in p]) for p in polygons],
                "crossing geometry corrupted")
    verify_transfers(c,[dict(ports=p,length=2*h,bends=0,angle=0,crossings=1,min_radius=None)
                       for p in (["w","e"],["s","n"])])


def verify_boundaries(m,cfg,net):
    cells=m['cells']
    require(len(m.get('interstage',[]))==net.depth-1,'missing interstage strategy')
    for stage,(record,boundary) in enumerate(zip(m['interstage'],net.boundaries)):
        refs=[r for r in cells[f'ROUTING_{stage:02}']['refs'] if cells[r['cell']]['kind']=='shuffle']
        require(len(refs)==net.p//boundary['size'],'shuffle group count corrupted')
        require(len({r['cell'] for r in refs})==1,'mixed boundary strategies')
        cell=cells[refs[0]['cell']]
        require(record==dict(stage=stage,**cell['metadata']),'boundary report differs from cell')
        require(record['size']==boundary['size'] and record['inverse']==boundary['inverse'],
                'boundary size/direction corrupted')
        size=record['size']
        permutation=[i//2+(size//2 if i%2 else 0) for i in range(size)]
        if boundary['inverse']: permutation=[permutation.index(i) for i in range(size)]
        require(record['permutation']==permutation,'block transfer table corrupted')
        width=record['width']
        require(all(cell['ports'][f'w{i}']==[0,i*cfg.lane_pitch,180] and
                    cell['ports'][f'e{i}']==[width,i*cfg.lane_pitch,0] for i in range(size)),
                'block interface corrupted')
        require(abs(width-(record['core_width']+record['fanin_width']+record['fanout_width']))<=cfg.grid,
                'transition width budget corrupted')
        # Inspect the actual child interface dimensions, not just copied metadata.
        if record['inverse']: cell=cells[cell['refs'][0]['cell']]
        if record['mode']=='compressed':
            require(cfg.interstage_routing=='compressed' and record['actual_pitch']==cfg.shuffle_pitch,
                    'unrequested local pitch')
            children=[cells[r['cell']] for r in cell['refs']]
            core=next(c for c in children if c['kind']=='shuffle')
            fan=next(c for c in children if c['kind']=='transition')
            require(core['ports']['w1'][1]-core['ports']['w0'][1]==record['actual_pitch'] and
                    core['ports']['e0'][0]==record['core_width'] and
                    fan['ports']['e0'][0]==record['fanin_width']==record['fanout_width'],
                    'measured core/transition dimensions differ')
        else:
            require(record['mode']=='continuous' and record['actual_pitch']==cfg.lane_pitch and
                    (record['fanin_width']==record['fanout_width']==0 or
                     (cfg.ground_pads_per_side and record.get('approach_offset',0)>0
                      and record['fanin_width']==record['fanout_width']>0)),
                    'uncompressed strategy corrupted')
        s=m['stages'][stage]
        sign = -1 if s.get('angle',0)==180 else 1
        require(abs(s['route_end']-s['escape_end']-sign*width)<=cfg.grid,'stage width differs from block')
