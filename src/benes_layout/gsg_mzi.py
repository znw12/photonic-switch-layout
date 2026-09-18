"""Four-port, 1-mm physical MZI inspired by Wang et al., Nature (2018).

The GSG arrangement and 0.8-um ridge follow the paper. Directional-coupler
length/gap and electrode lateral dimensions are uncalibrated design inputs.
"""
from math import acos, sin, cos, pi
from .geometry import snap, rectangle, arc_polygon, line_polygon


def build(lib):
    if 'MZI' in lib.cells:
        return lib.cells['MZI']
    cfg = lib.cfg
    L, p, r, w = cfg.mzi_length, cfg.lane_pitch, cfg.radius, cfg.mzi_wg_width
    close = (p-cfg.coupler_gap-w)/2
    arm = (p-cfg.gsg_signal_width-cfg.gsg_gap)/2
    if not 0 < close < 4*r or not 0 < close-arm < 4*r:
        raise ValueError('GSG S-bends cannot fit the requested radius')
    t0, t1 = acos(1-close/(2*r)), acos(1-(close-arm)/(2*r))
    a, dc = 40.0, cfg.coupler_length
    b = a+2*r*sin(t0)
    c = b+dc
    d = c+2*r*sin(t1)
    # Match the two straight-section end margins; the right-side bridge and
    # pickups follow the electrode end while external electrical ports stay fixed.
    active_start = snap(max(160,d+20))
    active_end = snap(L-active_start)
    if active_end-active_start < 100 or L-2*d < 100:
        raise ValueError('1 mm MZI has no room for the requested couplers and bends')
    cell = lib.cell('MZI','mzi')
    wave = lib.cell('GSG_WAVEGUIDES','device_waveguides')
    paths = []

    # A pair of real evanescently coupled rails; no optical shorting rectangle.
    coupler = lib.cell('GSG_DC','directional_coupler')
    for y in (0,cfg.coupler_gap+w):
        lib.poly(coupler,'WG',rectangle(0,y-w/2,dc,y+w/2))
    coupler.ports = {f'{side}{i}':[x,i*(cfg.coupler_gap+w),angle]
                     for side,x,angle in (('i',0,180),('o',dc,0)) for i in (0,1)}
    coupler.metadata = dict(gap_um=cfg.coupler_gap,length_um=dc,
                            split_target=0.5,split_calibrated=False)
    lib.ref(cell,coupler,b,close,id='coupler_in')
    lib.ref(cell,coupler,L-c,close,id='coupler_out')

    def line(a0,b0,width=w):
        poly = line_polygon(a0,b0,width)
        lib.poly(wave,'WG',poly)
        return dict(kind='line',start=list(a0),end=list(b0),width=width)

    def sbend(x,y,dy):
        angle = acos(1-abs(dy)/(2*r));sgn = 1 if dy>0 else -1
        dx = 2*r*sin(angle)
        records = []
        for cx,cy,aa,bb in ((x,y+sgn*r,-sgn*pi/2,-sgn*pi/2+sgn*angle),
                           (x+dx,y+dy-sgn*r,sgn*pi/2+sgn*angle,sgn*pi/2)):
            poly = arc_polygon(cx,cy,r,aa,bb,w,cfg.chord_error)
            lib.poly(wave,'WG',poly)
            records.append(dict(kind='arc',center=[cx,cy],radius=r,start_angle=aa,end_angle=bb,
                start=[cx+r*cos(aa),cy+r*sin(aa)],end=[cx+r*cos(bb),cy+r*sin(bb)],width=w))
        # A tiny tangent overlap prevents independent 1 nm rounding at inflections
        # from splitting the two arcs into separate polygons.
        mx,my=x+r*sin(angle),y+dy/2
        vx,vy=.01*cos(angle),sgn*.01*sin(angle)
        lib.poly(wave,'WG',line_polygon((mx-vx,my-vy),(mx+vx,my+vy),w))
        return records

    for rail in (0,1):
        y0 = rail*p
        sign = 1 if rail==0 else -1
        yc, ya = (close,arm) if rail==0 else (p-close,p-arm)
        # Terminal tapers connect the 1 um matrix rails to 0.8 um device ridges.
        for start,end,wa,wb in ((0,20,cfg.wg_width,w),(L-20,L,w,cfg.wg_width)):
            lib.poly(wave,'WG',[[start,y0-wa/2],[end,y0-wb/2],[end,y0+wb/2],[start,y0+wa/2]])
        pieces = [dict(kind='taper',start=[0,y0],end=[20,y0],width_start=cfg.wg_width,width_end=w)]
        pieces.append(line((20,y0),(a,y0)))
        pieces.extend(sbend(a,y0,sign*close))
        pieces.append(dict(kind='coupler',start=[b,yc],end=[c,yc],width=w))
        pieces.extend(sbend(c,yc,-sign*(close-arm)))
        pieces.append(line((d,ya),(L-d,ya)))
        pieces.extend(sbend(L-d,ya,sign*(close-arm)))
        pieces.append(dict(kind='coupler',start=[L-c,yc],end=[L-b,yc],width=w))
        pieces.extend(sbend(L-b,yc,-sign*close))
        pieces.append(line((L-a,y0),(L-20,y0)))
        pieces.append(dict(kind='taper',start=[L-20,y0],end=[L,y0],width_start=w,width_end=cfg.wg_width))
        paths.append(pieces)
    lib.ref(cell,wave)
    edge = (cfg.mzi_height-p)/2
    lib.poly(cell,'DEVICE',rectangle(0,-edge,L,p+edge))

    mid, sw, gap, gw = p/2,cfg.gsg_signal_width,cfg.gsg_gap,cfg.gsg_ground_width
    gy0, gy1 = mid-sw/2-gap-gw/2, mid+sw/2+gap+gw/2
    for y,width in ((gy0,gw),(mid,sw),(gy1,gw)):
        lib.poly(cell,'M1',rectangle(active_start,y-width/2,active_end,y+width/2))
    ground_x, signal_x, bend_x = active_end-60, active_end-20, active_end+20
    electrical_paths = [
        ('M2',[ground_x,gy0],[ground_x,gy1]),
        ('M2',[ground_x,15],[L-60,15]),
        ('M2',[L-60,15],[L-60,20]),
        ('M2',[L-60,20],[L,20]),
        ('M2',[signal_x,mid],[bend_x,mid]),
        ('M2',[bend_x,mid],[bend_x,40]),
        ('M2',[bend_x,40],[L,40]),
    ]
    for layer,v0,v1 in electrical_paths:
        half=cfg.metal_width/2
        # At the external boundary the metal ends exactly at x=L.
        lib.poly(cell,layer,rectangle(min(v0[0],v1[0])-half,min(v0[1],v1[1])-half,
                     min(L,max(v0[0],v1[0])+half),max(v0[1],v1[1])+half))
    vias = [[ground_x,gy0],[ground_x,gy1],[signal_x,mid]]
    for at in vias:lib.ref(cell,lib.via(),*at)
    cell.ports = {'i0':[0,0,180],'i1':[0,p,180],'o0':[L,0,0],'o1':[L,p,0],
                  'G':[L,20,0],'S':[L,40,0]}
    length=L+4*r*((t0-sin(t0))+(t1-sin(t1)))
    cell.tracks=[dict(ports=[f'i{i}',f'o{j}'],length=length,bends=8,
                      angle=4*(t0+t1),crossings=0,min_radius=r) for i in (0,1) for j in (0,1)]
    cell.metadata = dict(model='paper-gsg',geometry_defined=True,optical_transfer_calibrated=False,
        source_doi='10.1038/s41586-018-0551-y',drive='quasistatic',
        terminal_names=['G','S'],electrical_port_layers={'G':'M2','S':'M2'},allowed_transforms=[0,180],
        interaction_bbox=[0,-edge,L,p+edge],bar=[['i0','o0'],['i1','o1']],cross=[['i0','o1'],['i1','o0']],
        optical_paths=paths,active_x=[active_start,active_end],active_length_um=active_end-active_start,
        phase_arm_y=[arm,p-arm],electrode_centers=[gy0,mid,gy1],internal_vias=vias,
        electrical_probes={'G':[[ground_x,gy0],[ground_x,gy1]],'S':[[signal_x,mid]]},
        local_optical_metal_clearance_um=(gap-w)/2,
        length_model='Geometric symmetric branch length; directional-coupler phase and EO delay uncalibrated',
        stack_reference=dict(cut='x',ln_thickness_um=0.6,slab_thickness_um=0.3,
                             buried_oxide_um=4.7,top_oxide_um=0.8,gold_thickness_um=1.1))
    return cell


def export_device(cfg,out):
    """Standalone hierarchical GDS and actual-polygon device views."""
    import json
    from pathlib import Path
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    import klayout.db as kdb
    from .geometry import Library
    from .gsg_verify import verify_device
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    lib=Library(cfg);c=lib.mzi();cells=lib.export()
    checks=verify_device(cells,cfg)
    names=lib.write_gds(c.name,out/'mzi.gds')
    ly=kdb.Layout();ly.read(str(out/'mzi.gds'));top=ly.top_cell()
    if abs(top.dbbox().width()-1000)>cfg.grid:
        raise ValueError('standalone MZI GDS length differs from 1 mm')
    colors={'WG':'#52dfd4','M1':'#f5ad58','M2':'#849cf7','VIA':'#fff2c9'}
    polys={key:[] for key in colors}
    from .geometry import point

    def visit(name,x=0,y=0,angle=0):
        cell=cells[name]
        for p in cell['polygons']:
            if p['layer'] in polys:polys[p['layer']].append([point(x,y,angle,v) for v in p['points']])
        for ref in cell['refs']:
            at=point(x,y,angle,[ref['x'],ref['y']]);visit(ref['cell'],*at,(angle+ref['angle'])%360)
    visit(c.name)
    fig=plt.figure(figsize=(15,7),layout='constrained');fig.patch.set_facecolor('#101923')
    grid=fig.add_gridspec(2,2,height_ratios=(1,2))
    axes=[fig.add_subplot(grid[0,:]),fig.add_subplot(grid[1,0]),fig.add_subplot(grid[1,1])]
    active_end=c.metadata['active_x'][1]
    bounds=[(-5,-12,1005,72),(25,-3,160,63),(active_end-110,-2,active_end+40,62)]
    titles=[f"2 x 2 GSG MZI | total 1000 um | active electrode {c.metadata['active_length_um']:g} um | R >= {cfg.radius:g} um",
            'Input 2 x 2 directional coupler and circular S bends',
            'GSG electrodes and insulated common-G bridge']
    for ax,(a,b,d,e),title in zip(axes,bounds,titles):
        ax.set_facecolor('#101923')
        for layer,ps in polys.items():
            ax.add_collection(PolyCollection(ps,facecolors=colors[layer],edgecolors='none',alpha=.85))
        ax.set_xlim(a,d);ax.set_ylim(b,e);ax.set_aspect('equal');ax.set_title(title,color='white',fontsize=10)
        ax.tick_params(colors='#afc2d3');ax.set_xlabel('x (um)',color='#afc2d3');ax.set_ylabel('y (um)',color='#afc2d3')
        for spine in ax.spines.values():spine.set_color('#506475')
    for y,label in zip(c.metadata['electrode_centers'],('G','S','G')):
        axes[2].text(active_end-95,y,label,color='#101923',weight='bold',va='center')
    fig.supxlabel('WG: teal  M1: amber  M2: blue  VIA: cream | Physical geometry; coupling ratio / EO transfer uncalibrated',color='#afc2d3')
    fig.savefig(out/'mzi.png',dpi=180);plt.close(fig)
    (out/'model.json').write_text(json.dumps(cells,indent=2)+'\n')
    (out/'report.json').write_text(json.dumps(dict(**checks,cell_names=names,
        source_doi=c.metadata['source_doi'],metadata=c.metadata),indent=2)+'\n')
    return checks
