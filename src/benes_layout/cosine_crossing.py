"""Four convex cosine tapers within the existing crossing interface.

Shape reference only: the cited example is silicon, not a calibrated TFLN cell.
"""
from math import acos, ceil, cos, sqrt
from .geometry import snap, rectangle

REFERENCE='https://www.flexcompute.com/tidy3d/examples/notebooks/WaveguideCrossing/'


def populate(lib,cell):
    cfg=lib.cfg
    h,w,c,m,lead=(cfg.crossing_half_length,cfg.wg_width,cfg.crossing_center_width,
                   cfg.crossing_max_width,cfg.crossing_port_straight)
    lo,hi=acos(c/m),-acos(w/m)
    count=max(32,ceil(abs(hi-lo)*sqrt(m/2/(8*cfg.chord_error))))
    xs=[c/2+(h-lead-c/2)*i/count for i in range(count+1)]
    ys=[m/2*cos(lo+(hi-lo)*i/count) for i in range(count+1)]
    ys[0],ys[-1]=c/2,w/2
    arm=list(map(list,zip(xs,ys)))+[[x,-y] for x,y in reversed(list(zip(xs,ys))) ]
    tip=rectangle(h-lead,-w/2,h,w/2)
    cell.polygons=[]
    lib.poly(cell,'WG',rectangle(-c/2,-c/2,c/2,c/2))
    for _ in range(4):
        lib.poly(cell,'WG',arm)
        lib.poly(cell,'WG',tip)
        arm=[[-y,x] for x,y in arm]
        tip=[[-y,x] for x,y in tip]
    # Protect both axis-aligned and diagonal placement envelopes.
    for poly in cell.polygons:
        if any(abs(x)+abs(y)>h+w/2+cfg.grid*2 for x,y in poly['points']):
            raise ValueError('cosine crossing exceeds the original rotated footprint')
    cell.metadata.update(model='cosine',placeholder=False,geometry_defined=True,
        optical_transfer_calibrated=False,source_url=REFERENCE,
        center_width_um=c,max_width_um=m,port_width_um=w,port_straight_um=lead,
        taper_length_um=h-lead-c/2,samples_per_arm=count+1,
        footprint_um=[2*h,2*h],length_model='Straight centerline; optical phase and loss uncalibrated')


def verify(cell,cfg):
    from shapely.geometry import Polygon,Point,LineString
    from shapely.ops import unary_union
    from shapely.affinity import rotate
    from .verify import require
    h,w,c,m,lead=(cfg.crossing_half_length,cfg.wg_width,cfg.crossing_center_width,
                   cfg.crossing_max_width,cfg.crossing_port_straight)
    tol=2*cfg.grid
    md=cell['metadata'];polys=cell['polygons']
    require(md.get('model')=='cosine' and md.get('geometry_defined') is True
            and md.get('optical_transfer_calibrated') is False,'cosine crossing model mismatch')
    require(md.get('source_url')==REFERENCE and md.get('center_width_um')==c
            and md.get('max_width_um')==m and md.get('port_width_um')==w
            and md.get('port_straight_um')==lead and md.get('footprint_um')==[2*h,2*h]
            and md.get('taper_length_um')==h-lead-c/2,'cosine crossing parameter mismatch')
    require(cell['ports']=={'w':[-h,0,180],'e':[h,0,0],'s':[0,-h,270],'n':[0,h,90]},
            'cosine crossing ports corrupted')
    require(len(polys)==9 and all(p['layer']=='WG' for p in polys) and not cell['refs'],
            'cosine crossing polygon inventory corrupted')
    require(polys[0]['points']==[[snap(x),snap(y)] for x,y in rectangle(-c/2,-c/2,c/2,c/2)],
            'cosine crossing center corrupted')
    shapes=[Polygon(p['points']) for p in polys]
    require(all(s.is_valid and s.area>0 for s in shapes),'invalid cosine crossing polygon')
    region=unary_union(shapes)
    require(region.geom_type=='Polygon' and not region.interiors,'cosine crossing disconnected or holed')
    require(all(abs(a-b)<tol for a,b in zip(region.bounds,(-h,-h,h,h))),
            'cosine crossing footprint changed')
    diagonal=rotate(region,45,origin=(0,0));bound=(h+w/2)/sqrt(2)
    require(all(abs(a-b)<tol for a,b in zip(diagonal.bounds,(-bound,-bound,bound,bound))),
            'cosine crossing diagonal footprint changed')
    for k in range(4):
        arm=rotate(shapes[1+2*k],-90*k,origin=(0,0))
        tip=rotate(shapes[2+2*k],-90*k,origin=(0,0))
        require(tip.symmetric_difference(Polygon(rectangle(h-lead,-w/2,h,w/2))).area<tol*tol,
                'cosine crossing port straight corrupted')
        require(arm.hausdorff_distance(shapes[1])<tol,'cosine crossing rotational symmetry corrupted')
        n=md.get('samples_per_arm',0)
        require(n>=33 and len(arm.exterior.coords)==2*n+1,'cosine crossing sampling corrupted')
        for x,y in list(arm.exterior.coords)[:-1]:
            t=(x-c/2)/(h-lead-c/2)
            ideal=m/2*cos(acos(c/m)-t*(acos(c/m)+acos(w/m)))
            require(-tol<t<1+tol and abs(abs(y)-ideal)<tol,'cosine crossing taper shape corrupted')
        for x,expected in ((c/2,c),(h-lead,w)):
            section=arm.intersection(LineString([(x,-h),(x,h)]))
            require(abs(section.length-expected)<tol,'cosine crossing taper interface corrupted')
        require(region.covers(Point(cell['ports'][('e','n','w','s')[k]][:2])),
                'cosine crossing port disconnected')
    return dict(model='cosine',footprint_um=[2*h,2*h],port_width_um=w,
        center_width_um=c,max_width_um=m,taper_length_um=h-lead-c/2,
        port_straight_um=lead,samples_per_arm=md['samples_per_arm'],
        optical_transfer_calibrated=False,source_url=REFERENCE)


def export_device(cfg,out):
    import json
    from pathlib import Path
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    import klayout.db as kdb
    from .geometry import Library
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    lib=Library(cfg);cell=lib.crossing();cells=lib.export()
    report=verify(cells['CROSSING'],cfg)
    lib.write_gds(cell.name,out/'crossing.gds')
    ly=kdb.Layout();ly.read(str(out/'crossing.gds'))
    bounds=ly.top_cell().dbbox()
    if any(abs(v-2*cfg.crossing_half_length)>=cfg.grid for v in (bounds.width(),bounds.height())):
        raise ValueError('standalone crossing GDS footprint changed')
    fig,ax=plt.subplots(figsize=(7,7),layout='constrained')
    fig.patch.set_facecolor('#101923');ax.set_facecolor('#101923')
    ax.add_collection(PolyCollection([p['points'] for p in cell.polygons],facecolors='#52dfd4',edgecolors='none'))
    lim=cfg.crossing_half_length+1
    ax.set(xlim=(-lim,lim),ylim=(-lim,lim),aspect='equal',xlabel='x (um)',ylabel='y (um)',
        title=f'Cosine crossing | {2*cfg.crossing_half_length:g} x {2*cfg.crossing_half_length:g} um footprint')
    for name,(x,y,_) in cell.ports.items():ax.text(x,y,name.upper(),color='white',ha='center',va='center')
    ax.tick_params(colors='#afc2d3')
    for item in (ax.xaxis.label,ax.yaxis.label,ax.title):item.set_color('white')
    fig.supxlabel('Shape reference: Flexcompute / Tidy3D | TFLN optical performance uncalibrated',color='#afc2d3',fontsize=9)
    fig.savefig(out/'crossing.png',dpi=180);plt.close(fig)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'model.json').write_text(json.dumps(cells,indent=2)+'\n')
    return report
