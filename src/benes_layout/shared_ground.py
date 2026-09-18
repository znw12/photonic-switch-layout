"""Explicit common ground for quasi-static GSG devices; signal pads stay isolated."""
from .geometry import snap, rectangle


def add(lib,m,top):
    cfg=lib.cfg
    cell=lib.cell('COMMON_GROUND','ground_network')
    half=cfg.metal_width/2
    landing=cfg.via_size/2+cfg.via_enclosure
    left=snap(m['extents']['core'][0]-cfg.margin/2)
    outer=snap(max(abs(m['extents']['pads'][1]),abs(m['extents']['pads'][3]))+cfg.margin)
    segments,vias=[],[]

    def metal(layer,a,b):
        lib.poly(cell,layer,rectangle(min(a[0],b[0])-half,min(a[1],b[1])-half,
                                     max(a[0],b[0])+half,max(a[1],b[1])+half))
        segments.append(dict(layer=layer,start=a,end=b))

    for side,sign in (('south',-1),('north',1)):
        grounds=[e for e in m['electrical'] if e['side']==side and e['terminal']=='G']
        if not grounds:
            # N=1 assigns one electrical terminal to each side; a bank can be all S.
            continue
        y=snap(sign*outer)
        metal('M2',[left,y],[max(e['pad'][0] for e in grounds),y])
        for e in grounds:
            at=[e['pad'][0],y]
            metal('M1',e['pad'],at)
            lib.ref(cell,lib.via(),*at)
            vias.append(at)
    metal('M2',[left,-outer],[left,outer])
    # Connect an otherwise empty bank endpoint to avoid an unassigned island;
    # the vertical rail is a single conductor connected at the occupied bank.
    lib.ref(top,cell)
    for e in m['electrical']:
        e['electrical_net']='GND' if e['terminal']=='G' else e['net']
    m['ground_network']=dict(net='GND',cell=cell.name,segments=segments,vias=vias,
        bus_y=outer,left_x=left,ground_pads=len(vias),scope='quasistatic common ground')
    m['die_bbox'][1]=snap(-outer-landing-cfg.margin)
    m['die_bbox'][3]=snap(outer+landing+cfg.margin)
    m['height']=snap(m['die_bbox'][3]-m['die_bbox'][1])
    m['extents']['ground']=[left-half,-outer-landing,
        max(e['pad'][0] for e in m['electrical'] if e['terminal']=='G')+landing,outer+landing]
