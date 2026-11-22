"""Render gambar asli dari arahan teks yang berbentuk komposisi geometri.

Arahan kanonis terdiri dari CANVAS dan layer dengan warna RGBA.
Renderer menerapkan antialias empat sampel, campuran dan kliping
berbatas. Receipt menunjuk arahan dan digest piksel yang dihasilkan.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,identifier,read,schema,text
from ._raster import Raster,blank,color,dimensions,png,ppm


MAX_LAYERS=90
WORK_LIMIT=10_000_000
INT=re.compile(r"-?(?:0|[1-9][0-9]{0,4})")
SAMPLES=((1,1),(3,1),(1,3),(3,3))


@dataclass(frozen=True)
class Layer:
    type:str
    bounds:tuple
    palette:tuple
    geometry:tuple


def _integer(values,label):
    if any(not INT.fullmatch(value) for value in values):
        raise ContractError(f"{label} perlu koordinat integer.")
    return tuple(map(int,values))


def _clip(lo,hi,limit):
    return max(0,min(limit,lo)),max(0,min(limit,hi))


def _inside(x,y,w,h,extent):
    if not -extent<=x<=extent or not -extent<=y<=extent or not 1<=w<=extent or not 1<=h<=extent:
        raise ContractError("Geometri layer ukuran atau koordinat tak sah.")


def _outline(command,values,width,height):
    large=max(width,height)*2
    if command in ("RECT","ELLIPSE") and len(values)==5:
        x,y,w,h=_integer(values[:4],command)
        _inside(x,y,w,h,large)
        left,right=_clip(x,x+w,width)
        top,bottom=_clip(y,y+h,height)
        return Layer(command.lower(),(left,top,right,bottom),(color(values[4]),),(x,y,w,h))
    if command=="LINE" and len(values)==6:
        x0,y0,x1,y1,thick=_integer(values[:5],command)
        if not all(-large<=value<=large for value in (x0,y0,x1,y1)) or not 1<=thick<=256 or (x0,y0)==(x1,y1):
            raise ContractError("LINE perlu dua titik berbeda dan ketebalan dalam batas.")
        radius=(thick+1)//2
        left,right=_clip(min(x0,x1)-radius,max(x0,x1)+radius+1,width)
        top,bottom=_clip(min(y0,y1)-radius,max(y0,y1)+radius+1,height)
        return Layer("line",(left,top,right,bottom),(color(values[5]),),(x0,y0,x1,y1,thick))
    if command=="GRADIENT" and len(values)==3 and values[0] in ("x","y"):
        return Layer("gradient",(0,0,width,height),(color(values[1]),color(values[2])),(values[0],))
    if command=="POLYGON" and 4<=len(values)<=25:
        vertices=[]
        for raw in values[1:]:
            pair=raw.split(",")
            if len(pair)!=2:
                raise ContractError("Vertex perlu x,y.")
            point=_integer(pair,command)
            if any(abs(value)>large for value in point):
                raise ContractError("Vertex di luar batas.")
            vertices.append(point)
        if len(set(vertices))!=len(vertices):
            raise ContractError("Vertex polygon ganda.")
        area=sum(x*y1-x1*y for (x,y),(x1,y1) in zip(vertices,vertices[1:]+vertices[:1],strict=True))
        if not area:
            raise ContractError("POLYGON tidak memiliki luas.")
        xs,ys=zip(*vertices,strict=True)
        left,right=_clip(min(xs),max(xs)+1,width)
        top,bottom=_clip(min(ys),max(ys)+1,height)
        return Layer("polygon",(left,top,right,bottom),(color(values[0]),),tuple(vertices))
    raise ContractError(f"Perintah atau jumlah operand tidak sah pada {command[:30]}.")


def parse_instructions(raw):
    if not isinstance(raw,str) or len(raw)>18_000 or any(not (c.isprintable() or c in "\r\n\t") for c in raw):
        raise ContractError("Arahan gambar di luar batas.")
    commands=[(number,row.split()) for number,row in enumerate(raw.splitlines(),1)
              if row.strip() and not row.lstrip().startswith("//")]
    if not 2<=len(commands)<=MAX_LAYERS+1:
        raise ContractError("Arahan memerlukan canvas dan layer berbatas.")
    canvas=commands[0][1]
    if len(canvas)!=4 or canvas[0]!="CANVAS":
        raise ContractError("Baris pertama harus CANVAS lebar tinggi warna.")
    width,height=dimensions(*_integer(canvas[1:3],"CANVAS"))
    background=color(canvas[3])
    if background[3]!=255:
        raise ContractError("Latar canvas harus opak.")
    layers=[]
    cost=0
    for line,parts in commands[1:]:
        shape=_outline(parts[0],parts[1:],width,height)
        x0,y0,x1,y1=shape.bounds
        if x0==x1 or y0==y1:
            raise ContractError(f"Seluruh layer baris {line} berada di luar canvas.")
        cost+=(x1-x0)*(y1-y0)*(len(shape.geometry) if shape.type=="polygon" else 1)
        if cost>WORK_LIMIT:
            raise ContractError("Komposisi terlalu besar untuk anggaran render.")
        layers.append((line,shape))
    return blank(width,height,background[:3]),layers


def _blend(grid,offset,rgba,covered=4):
    red,green,blue,opacity=rgba
    alpha=(opacity*covered+2)//4
    if alpha==255:
        grid[offset:offset+3]=bytes((red,green,blue))
    elif alpha:
        for index,value in enumerate((red,green,blue),offset):
            grid[index]=(value*alpha+grid[index]*(255-alpha)+127)//255


def _ellipse(sx,sy,shape):
    x,y,w,h=shape
    a,b=sx-4*x-2*w,sy-4*y-2*h
    return a*a*h*h+b*b*w*w<=4*w*w*h*h


def _line(sx,sy,shape):
    x0,y0,x1,y1,thick=shape
    dx,dy=4*(x1-x0),4*(y1-y0)
    ax,ay=sx-4*x0,sy-4*y0
    squared=dx*dx+dy*dy
    reach=ax*dx+ay*dy
    radius_square=4*thick*thick
    if reach<0:
        return ax*ax+ay*ay<=radius_square
    if reach>squared:
        return (ax-dx)**2+(ay-dy)**2<=radius_square
    return (ax*dy-ay*dx)**2<=radius_square*squared


def _polygon(sx,sy,vertices):
    odd=False
    for (x0,y0),(x1,y1) in zip(vertices,vertices[1:]+vertices[:1],strict=True):
        ax,ay,bx,by=4*x0,4*y0,4*x1,4*y1
        if (ay>sy)==(by>sy):
            continue
        left=(sx-ax)*(by-ay)
        right=(bx-ax)*(sy-ay)
        if (left<right) if by>ay else (left>right):
            odd=not odd
    return odd


def _render_layer(grid,width,height,layer):
    left,top,right,bottom=layer.bounds
    front=layer.palette[0]
    if layer.type=="rect" and front[3]==255:
        scan=bytes(front[:3])*(right-left)
        for y in range(top,bottom):
            offset=(y*width+left)*3
            grid[offset:offset+len(scan)]=scan
        return
    mask={"ellipse":_ellipse,"line":_line,"polygon":_polygon}.get(layer.type)
    for y in range(top,bottom):
        for x in range(left,right):
            coverage=4 if mask is None else sum(mask(4*x+dx,4*y+dy,layer.geometry) for dx,dy in SAMPLES)
            rgba=front
            if layer.type=="gradient":
                along=layer.geometry[0]
                position,denominator=(x,max(1,width-1)) if along=="x" else (y,max(1,height-1))
                rgba=tuple((a*(denominator-position)+b*position+denominator//2)//denominator
                           for a,b in zip(front,layer.palette[1],strict=True))
            _blend(grid,(y*width+x)*3,rgba,coverage)


def render(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.media.image-plan.v1",("id","source_ref","instructions","format"))
    key=identifier(plan["id"],"ID gambar")
    source=text(plan["source_ref"],"Rujukan arahan")
    initial,layers=parse_instructions(plan["instructions"])
    format_name=plan["format"]
    if format_name not in ("png","ppm"):
        raise ContractError("Format hasil perlu png atau ppm.")
    raster=bytearray(initial.pixels)
    for _,layer in layers:
        _render_layer(raster,initial.width,initial.height,layer)
    final=Raster(initial.width,initial.height,bytes(raster))
    payload=png(final) if format_name=="png" else ppm(final)
    receipt={"schema":"ace.media.generated-image.v1","plan_sha256":expected,"source_ref":source,"image_id":key,
             "format":format_name,"bytes":len(payload),"image_sha256":sha256(payload).hexdigest(),**final.receipt(),
             "layers":[{"line":number,"type":rule.type,"visible_bounds":list(rule.bounds)} for number,rule in layers]}
    return payload,receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        payload,report=render(decode(read(args.plan)),args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
