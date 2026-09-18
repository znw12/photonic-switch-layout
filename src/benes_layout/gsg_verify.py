"""Checks specific to physical coupled rails and declared GSG/common-ground nets."""
from math import hypot, sin, cos
from collections import Counter
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from .geometry import snap, rectangle


def verify_device(cells,cfg):
    from .verify import require, cell_geometries
    c=cells['MZI'];md=c['metadata'];shape=cell_geometries(cells)
    wg=shape('MZI','WG');tol=cfg.grid*2
    require(md.get('model')=='paper-gsg' and md.get('geometry_defined') is True
            and md.get('optical_transfer_calibrated') is False,'GSG device contract mismatch')
    require(wg.is_valid and wg.geom_type=='MultiPolygon' and len(wg.geoms)==2,
            'GSG waveguide branches disconnected or optically shorted')
    rails=sorted(wg.geoms,key=lambda g:g.centroid.y)
    require(abs(wg.bounds[0])<tol and abs(wg.bounds[2]-1000)<tol,'GSG total length is not 1000 um')
    require(rails[0].distance(rails[1])>=cfg.coupler_gap-tol,'directional coupler gap too small')
    for i,g in enumerate(rails):
        for at in ([0,i*cfg.lane_pitch],[1000,i*cfg.lane_pitch]):
            require(g.buffer(tol).covers(Point(at)),'GSG rail misses external port')
    refs=[r for r in c['refs'] if cells[r['cell']]['kind']=='directional_coupler']
    require(len(refs)==2,'GSG must have two 2x2 couplers')
    dc=cells[refs[0]['cell']]
    require(len(dc['polygons'])==2 and all(p['layer']=='WG' for p in dc['polygons']),
            'directional coupler must have two separate rails')
    require(abs(Polygon(dc['polygons'][0]['points']).distance(Polygon(dc['polygons'][1]['points']))
                -cfg.coupler_gap)<tol,'directional coupler actual gap differs')
    for ref in refs:
        for i,g in enumerate(rails):
            at=Point(ref['x']+cfg.coupler_length/2,ref['y']+i*(cfg.coupler_gap+cfg.mzi_wg_width))
            require(g.covers(at),'GSG coupler is disconnected from rail')
    lengths=[]
    for i,path in enumerate(md['optical_paths']):
        length,bends,angle=0.0,0,0.0
        last=[0,i*cfg.lane_pitch]
        for seg in path:
            a,b=seg['start'],seg['end']
            require(hypot(a[0]-last[0],a[1]-last[1])<tol,'GSG centerline discontinuity')
            if seg['kind']=='arc':
                radius=seg['radius'];aa,bb=seg['start_angle'],seg['end_angle'];cx,cy=seg['center']
                require(radius>=max(20,cfg.radius)-tol,'GSG bend radius below limit')
                require(abs(hypot(a[0]-cx,a[1]-cy)-radius)<tol
                        and abs(hypot(b[0]-cx,b[1]-cy)-radius)<tol,'GSG arc radius metadata wrong')
                samples=[[cx+radius*cos(aa+(bb-aa)*j/100),cy+radius*sin(aa+(bb-aa)*j/100)] for j in range(101)]
                length+=radius*abs(bb-aa);bends+=1;angle+=abs(bb-aa)
            else:
                samples=[[a[0]+(b[0]-a[0])*j/50,a[1]+(b[1]-a[1])*j/50] for j in range(51)]
                length+=hypot(b[0]-a[0],b[1]-a[1])
            require(all(rails[i].buffer(tol).covers(Point(v)) for v in samples),
                    'GSG actual waveguide misses centerline')
            last=b
        require(hypot(last[0]-1000,last[1]-i*cfg.lane_pitch)<tol and bends==8,
                'GSG branch endpoints/bends mismatch')
        lengths.append(length)
        for t in c['tracks'][i*2:i*2+2]:
            require(abs(t['length']-length)<tol and t['bends']==bends and abs(t['angle']-angle)<tol
                    and t['min_radius']>=20,'GSG track metrics mismatch')
    require(abs(lengths[0]-lengths[1])<tol,'GSG arms are not geometrically balanced')
    start,end=md['active_x'];mid=cfg.lane_pitch/2
    require(abs(end-start-md['active_length_um'])<tol and 0<start<end<1000,
            'GSG effective electrode length mismatch')
    ys=[mid-(cfg.gsg_signal_width+cfg.gsg_gap)/2,mid+(cfg.gsg_signal_width+cfg.gsg_gap)/2]
    require(md['phase_arm_y']==ys,'GSG arms not centered in electrode gaps')
    for g,y in zip(rails,ys):
        require(g.covers(Point((start+end)/2,y)),'GSG phase waveguide missing')
    for path,y in zip(md['optical_paths'],ys):
        phase=[s for s in path if s['kind']=='line'
               and abs(s['start'][1]-y)<tol and abs(s['end'][1]-y)<tol
               and s['start'][0]<=start and s['end'][0]>=end]
        require(len(phase)==1 and start-phase[0]['start'][0]>=20-tol
                and phase[0]['end'][0]-end>=20-tol,
                'GSG electrode lacks straight-section bend clearance')
    clearance=(cfg.gsg_gap-cfg.mzi_wg_width)/2
    require(abs(md['local_optical_metal_clearance_um']-clearance)<tol,'GSG optical clearance contract changed')
    require(shape('MZI','M1').distance(wg)>=clearance-tol,'GSG electrode touches or approaches optical rail')
    require(shape('MZI','VIA').distance(wg)>=clearance+cfg.via_enclosure-tol,'GSG via too close to optical rail')
    for y,width in zip(md['electrode_centers'],[cfg.gsg_ground_width,cfg.gsg_signal_width,cfg.gsg_ground_width]):
        require(shape('MZI','M1').buffer(tol).covers(box(start,y-width/2,end,y+width/2)),
                'GSG electrode missing or too narrow')
    centers=[mid-cfg.gsg_signal_width/2-cfg.gsg_gap-cfg.gsg_ground_width/2,mid,
             mid+cfg.gsg_signal_width/2+cfg.gsg_gap+cfg.gsg_ground_width/2]
    require(md['electrode_centers']==centers,'GSG electrode arrangement changed')
    require(md['electrical_probes']=={'G':[[end-60,centers[0]],[end-60,centers[2]]],
                                     'S':[[end-20,mid]]},'GSG electrical probe contract changed')
    # Reconstruct the approved local metal independently from the declared
    # electrode dimensions, not from the exported list of arbitrary polygons.
    expected=[]
    for y,width in zip(centers,[cfg.gsg_ground_width,cfg.gsg_signal_width,cfg.gsg_ground_width]):
        expected.append(dict(layer='M1',points=rectangle(start,y-width/2,end,y+width/2)))
    port_layers=md.get('electrical_port_layers',{'G':'M1','S':'M1'})
    require(port_layers in ({'G':'M1','S':'M1'},{'G':'M2','S':'M2'}),
            'GSG electrical port layer contract mismatch')
    m2_ports=port_layers['G']=='M2'
    gx,sx,bx,ex=end-60,end-20,end+20,(1000 if m2_ports else 980)
    paths=[('M2',[gx,centers[0]],[gx,centers[2]]),('M2',[gx,15],[940,15]),
           ('M2',[940,15],[940,20]),('M2',[940,20],[ex,20]),
           ('M2',[sx,mid],[bx,mid]),('M2',[bx,mid],[bx,40]),('M2',[bx,40],[ex,40])]
    if cfg.ground_pads_per_side:
        require(m2_ports and c['ports']['G']==[gx,mid,90] and c['ports']['S']==[1000,mid,0],
                'compact GSG electrical ports changed')
        paths=[('M2',[gx,centers[0]],[gx,centers[2]]),('M2',[sx,mid],[1000,mid])]
    if not m2_ports:
        paths += [('M1',[ex,20],[1000,20]),('M1',[ex,40],[1000,40])]
    half=cfg.metal_width/2
    for layer,a,b in paths:
        expected.append(dict(layer=layer,points=rectangle(min(a[0],b[0])-half,min(a[1],b[1])-half,
                    min(1000,max(a[0],b[0])+half),max(a[1],b[1])+half)))
    for poly in expected:poly['points']=[[snap(v) for v in at] for at in poly['points']]
    require([p for p in c['polygons'] if p['layer'] in ('M1','M2')]==expected,
            'GSG device metal differs from approved local contract')
    vias=[r for r in c['refs'] if r['cell']=='VIA']
    expected_vias=[[gx,centers[0]],[gx,centers[2]],[sx,mid]]
    if not m2_ports:expected_vias += [[ex,20],[ex,40]]
    require(md['internal_vias']==expected_vias
            and Counter((r['x'],r['y']) for r in vias)==Counter(map(tuple,expected_vias)),
            'GSG internal via inventory mismatch')
    return dict(total_length_um=1000,active_length_um=md['active_length_um'],
        branch_geometric_length_um=lengths[0],bends_per_branch=8,min_radius_um=cfg.radius,
        internal_vias_per_device=len(vias),coupler_calibrated=False,
        **({'electrical_port_layer':'M2'} if m2_ports else {}))


def verify_ground(m,cfg):
    if cfg.ground_pads_per_side:
        from .local_ground import verify
        return verify(m,cfg)
    from .verify import require
    ground=m.get('ground_network',{});cell=m['cells'].get(ground.get('cell'),{})
    require(ground.get('net')=='GND' and cell.get('kind')=='ground_network','missing shared GSG ground')
    expected_vias=[];expected_segments=[]
    left=ground['left_x'];outer=ground['bus_y'];half=cfg.metal_width/2
    require(left<m['extents']['core'][0]-cfg.optical_metal_clearance-half,
            'ground spine overlaps optical interface keepout')
    require(outer>max(abs(m['extents']['pads'][1]),abs(m['extents']['pads'][3]))+cfg.metal_spacing,
            'ground bus overlaps pad banks')
    for side,sign in (('south',-1),('north',1)):
        bank=[e for e in m['electrical'] if e['side']==side and e['terminal']=='G']
        if not bank:continue
        y=sign*outer
        expected_segments.append(dict(layer='M2',start=[left,y],end=[max(e['pad'][0] for e in bank),y]))
        for e in bank:
            at=[e['pad'][0],y];expected_vias.append(at)
            expected_segments.append(dict(layer='M1',start=e['pad'],end=at))
    expected_segments.append(dict(layer='M2',start=[left,-outer],end=[left,outer]))
    require(ground.get('segments')==expected_segments and ground.get('vias')==expected_vias,
            'shared ground routes or vias differ from G pads')
    expected=[]
    for s in expected_segments:
        a,b=s['start'],s['end']
        expected.append(dict(layer=s['layer'],points=[[snap(v) for v in p] for p in rectangle(
            min(a[0],b[0])-half,min(a[1],b[1])-half,max(a[0],b[0])+half,max(a[1],b[1])+half)]))
    require(cell['polygons']==expected,'shared ground polygons changed')
    require(Counter((r['cell'],r['x'],r['y'],r['angle']) for r in cell['refs'])
            ==Counter(('VIA',*at,0) for at in expected_vias),'shared ground via hierarchy wrong')
    for e in m['electrical']:
        require(e.get('electrical_net')==('GND' if e['terminal']=='G' else e['net']),
                'GSG ground/signal net class mismatch')
