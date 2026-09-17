"""Explicit primitive routes for continuous and locally compressed shuffles.

All coordinates are micrometres. Reverse modules use a 180-degree placement
and reverse *paired* transfers, never a four-way crossing graph node.
"""
from hashlib import sha256
import json
from math import pi, sqrt, sin, cos, atan2, degrees, hypot, acos

from .geometry import snap, point

METRICS = ("length", "bends", "angle", "crossings")


def key(prefix, value):
    return prefix + sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def bidirectional(cell):
    for track in list(cell.tracks):
        reverse = list(reversed(track["ports"]))
        if not any(t["ports"] == reverse for t in cell.tracks):
            cell.tracks.append({**track, "ports": reverse})
    return cell


def segment(lib, a, b):
    a, b = [snap(v) for v in a], [snap(v) for v in b]
    length = hypot(b[0] - a[0], b[1] - a[1])
    if length <= 2*lib.cfg.grid:
        return None
    name = key("SEG_", [a, b])
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name, "segment")
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    w = lib.cfg.wg_width / 2
    # Three grid units absorb polygon rounding at tangent joints; ports and
    # analytic path lengths stay unchanged. Spatial checks bound the overlap.
    cap = 3*lib.cfg.grid
    pa, pb = [a[0]-ux*cap,a[1]-uy*cap], [b[0]+ux*cap,b[1]+uy*cap]
    lib.poly(c, "WG", [[pa[0]-uy*w, pa[1]+ux*w], [pb[0]-uy*w, pb[1]+ux*w],
                       [pb[0]+uy*w, pb[1]-ux*w], [pa[0]+uy*w, pa[1]-ux*w]])
    angle = degrees(atan2(b[1]-a[1], b[0]-a[0])) % 360
    c.ports = {"w": [*a, (angle+180) % 360], "e": [*b, angle]}
    c.metadata = {"centerline": [a, b]}
    c.tracks = [dict(ports=["w", "e"], length=length, bends=0, angle=0,
                     crossings=0, min_radius=None)]
    return bidirectional(c)


def arc(lib, cx, cy, start, end):
    return bidirectional(lib.bend(key("ARC_", [cx, cy, start, end]), cx, cy, start, end))


def attach(lib, parent, parts, cell, x=0, y=0, angle=0, entry="w", exit="e", place=True):
    if cell is None:
        return
    if place:
        lib.ref(parent, cell, x, y, angle)
    parts.append(dict(cell=cell.name, x=snap(x), y=snap(y), angle=angle,
                      entry=entry, exit=exit))


def finish(lib, c, parts, permutation, pitch, width, **metadata):
    c.metadata = dict(width=snap(width), size=len(parts), permutation=permutation, **metadata)
    for i, pieces in enumerate(parts):
        c.ports[f"w{i}"] = [0, snap(i*pitch), 180]
        c.ports[f"e{i}"] = [snap(width), snap(i*pitch), 0]
        totals = dict.fromkeys(METRICS, 0)
        for part in pieces:
            t = next(t for t in lib.cells[part["cell"]].tracks
                     if t["ports"] == [part["entry"], part["exit"]])
            for k in totals:
                totals[k] += t[k]
        c.tracks.append(dict(ports=[f"w{i}", f"e{permutation[i]}"], pieces=pieces, **totals))
    return c


def continuous(lib, size, pitch):
    name = key("CONT_", [size, pitch, lib.cfg.radius])
    if name in lib.cells:
        return lib.cells[name]
    cfg = lib.cfg
    r = cfg.radius
    ax, ay = r/sqrt(2), r*(1-1/sqrt(2))
    offset = ax-ay
    if (pitch/2-ay)*sqrt(2) <= cfg.crossing_half_length + cfg.wg_clearance:
        raise ValueError("shuffle pitch cannot fit crossing approaches")
    width = snap((size//2-1)*pitch + 2*offset)
    c = lib.cell(name, "shuffle")
    perm = [i//2 + (size//2 if i%2 else 0) for i in range(size)]
    crossings = [[] for _ in range(size)]
    cross = bidirectional(lib.crossing())
    if 45 not in cross.metadata["allowed_transforms"]:
        raise ValueError("crossing transform 45 is not permitted")
    for i in range(size):
        for j in range(i+1, size):
            if perm[i] <= perm[j]:
                continue
            x, y = snap((j-i)*pitch/2+offset), snap((i+j)*pitch/2)
            lib.ref(c, cross, x, y, 45, id=f"cross_{i}_{j}")
            crossings[i].append((x, y, "w", "e"))
            crossings[j].append((x, y, "n", "s"))
    parts = [[] for _ in range(size)]
    for i, path in enumerate(parts):
        y0, y1 = i*pitch, perm[i]*pitch
        d = y1-y0
        if not d:
            attach(lib, c, path, segment(lib, [0, y0], [width, y0]))
            continue
        sign = 1 if d > 0 else -1
        endx = snap(abs(d)+2*offset)
        first = arc(lib, 0, y0+sign*r, -sign*pi/2, -sign*pi/4)
        last = arc(lib, endx, y1-sign*r, sign*3*pi/4, sign*pi/2)
        attach(lib, c, path, first)
        previous = first.ports["e"][:2]
        for x, y, entry, exit in sorted(crossings[i]):
            start = point(x, y, 45, cross.ports[entry])
            attach(lib, c, path, segment(lib, previous, start))
            attach(lib, c, path, cross, x, y, 45, entry, exit, place=False)
            previous = point(x, y, 45, cross.ports[exit])
        attach(lib, c, path, segment(lib, previous, last.ports["w"][:2]))
        attach(lib, c, path, last)
        attach(lib, c, path, segment(lib, [endx, y1], [width, y1]))
    return finish(lib, c, parts, perm, pitch, width, mode="continuous", inverse=False,
                  actual_pitch=pitch, core_width=width, fanin_width=0, fanout_width=0)


def reverse_block(lib, source, pitch):
    name = "REV_" + source.name
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name, "shuffle")
    size, width = source.metadata["size"], source.metadata["width"]
    h = (size-1)*pitch
    lib.ref(c, source, width, h, 180)
    paths, perm = [None]*size, [None]*size
    for i, t in enumerate(source.tracks):
        dest = source.metadata["permutation"][i]
        row = size-1-dest
        perm[row] = size-1-i
        paths[row] = []
        for p in reversed(t["pieces"]):
            x, y = point(width, h, 180, [p["x"], p["y"]])
            bidirectional(lib.cells[p["cell"]])
            paths[row].append({**p, "x": x, "y": y, "angle": (p.get("angle",0)+180)%360,
                               "entry": p["exit"], "exit": p["entry"]})
    metadata = {k:v for k,v in source.metadata.items() if k not in ("width", "size", "permutation")}
    metadata["inverse"] = True
    return finish(lib, c, paths, perm, pitch, width, **metadata)


def shift_dimensions(delta, radius, max_angle=75*pi/180):
    """Two circular arcs plus tangent; small offsets reduce the bend angle."""
    d = abs(delta)
    if not d:
        return 0.0, 0.0, 0.0
    angle = min(max_angle, acos(max(-1.0, 1-d/(2*radius))))
    length = max(0.0, (d-2*radius*(1-cos(angle)))/sin(angle))
    width = 2*radius*sin(angle)+length*cos(angle)
    return width, angle, length


def fanin(lib, size, pitch, q):
    name = key("FANIN_", [size, pitch, q])
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name, "transition")
    offset = (size-1)*(pitch-q)/2
    # Match the final arc's snapped endpoint without inserting sub-grid stubs.
    width = snap(shift_dimensions(offset, lib.cfg.radius)[0])
    paths = [[] for _ in range(size)]
    for i, path in enumerate(paths):
        y0, y1 = i*pitch, offset+i*q
        d = y1-y0
        w, angle, length = shift_dimensions(d, lib.cfg.radius)
        if d:
            sign, r = (1 if d>0 else -1), lib.cfg.radius
            first = arc(lib, 0, y0+sign*r, -sign*pi/2, -sign*pi/2+sign*angle)
            last = arc(lib, w, y1-sign*r, sign*pi/2+sign*angle, sign*pi/2)
            attach(lib,c,path,first)
            attach(lib,c,path,segment(lib,first.ports["e"][:2],last.ports["w"][:2]))
            attach(lib,c,path,last)
        attach(lib,c,path,segment(lib,[snap(w),y1],[snap(width),y1]))
    # Transition output spacing differs from its input spacing.
    finish(lib,c,paths,list(range(size)),pitch,width,offset=offset,actual_pitch=q)
    for i in range(size):
        c.ports[f"e{i}"] = [snap(width), snap(offset+i*q), 0]
    return c


def translated_parts(paths, x, y):
    return [{**p, "x": snap(p["x"]+x), "y": snap(p["y"]+y)} for p in paths]


def compressed(lib, size, q):
    pitch = lib.cfg.lane_pitch
    base = continuous(lib,size,pitch)
    if q == pitch:
        return base
    core, fan = continuous(lib,size,q), fanin(lib,size,pitch,q)
    f, offset = fan.metadata["width"], fan.metadata["offset"]
    width = snap(2*f+core.metadata["width"])
    if width >= base.metadata["width"]:
        return base
    name = key("COMP_",[size,pitch,q])
    if name in lib.cells:
        return lib.cells[name]
    c = lib.cell(name,"shuffle")
    lib.ref(c,fan)
    lib.ref(c,core,f,offset)
    lib.ref(c,fan,width,(size-1)*pitch,180)
    paths = []
    for i in range(size):
        dest = core.metadata["permutation"][i]
        path = list(fan.tracks[i]["pieces"])
        path += translated_parts(core.tracks[i]["pieces"],f,offset)
        for p in reversed(fan.tracks[size-1-dest]["pieces"]):
            x,y = point(width,(size-1)*pitch,180,[p["x"],p["y"]])
            path.append({**p,"x":x,"y":y,"angle":(p.get("angle",0)+180)%360,
                         "entry":p["exit"],"exit":p["entry"]})
        paths.append(path)
    return finish(lib,c,paths,core.metadata["permutation"],pitch,width,mode="compressed",
                  inverse=False,actual_pitch=q,core_width=core.metadata["width"],
                  fanin_width=f,fanout_width=f)


def shuffle_block(lib,size,inverse=False):
    c = (compressed(lib,size,lib.cfg.shuffle_pitch) if lib.cfg.interstage_routing == "compressed"
         else continuous(lib,size,lib.cfg.lane_pitch))
    return reverse_block(lib,c,lib.cfg.lane_pitch) if inverse else c
