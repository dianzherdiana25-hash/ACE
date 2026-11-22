"""Terapkan instruksi edit yang terukur pada PNG atau PPM tertambat.

Kliping, koordinat crop, dan ukuran resampling diuji sebelum emisi.
Receipt mengikat hash sebelum/sesudah tiap langkah. Sumber tidak
ditimpa dan format keluaran selalu ditetapkan secara eksplisit.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,integer,obj,read,schema,text
from ._raster import MAX_BYTES,Raster,color,dimensions,png,ppm,raster


SCALE=256


def _box(raw,image):
    if not isinstance(raw,list) or len(raw)!=4:
        raise ContractError("Kotak perlu [x,y,w,h].")
    x=integer(raw[0],"X",0,image.width-1)
    y=integer(raw[1],"Y",0,image.height-1)
    w=integer(raw[2],"Lebar crop",1,image.width-x)
    h=integer(raw[3],"Tinggi crop",1,image.height-y)
    return x,y,w,h


def _crop(image,rule):
    obj(rule,("op","box"))
    x,y,w,h=_box(rule["box"],image)
    data=b"".join(image.pixels[(row*image.width+x)*3:(row*image.width+x+w)*3] for row in range(y,y+h))
    return Raster(w,h,data)


def _axis(size,output):
    for pos in range(output):
        ratio=max(0,min((size-1)*SCALE,((2*pos+1)*size*SCALE//output-SCALE)//2))
        first,fraction=divmod(ratio,SCALE)
        yield first,min(first+1,size-1),fraction


def _resize(image,rule):
    obj(rule,("op","width","height","filter"))
    width,height=dimensions(rule["width"],rule["height"])
    kind=rule["filter"]
    if kind not in ("nearest","bilinear"):
        raise ContractError("Filter resize belum didukung.")
    horizontal=list(_axis(image.width,width))
    result=bytearray()
    for y0,y1,fy in _axis(image.height,height):
        for x0,x1,fx in horizontal:
            if kind=="nearest":
                result.extend(image.at(x1 if fx>=SCALE//2 else x0,y1 if fy>=SCALE//2 else y0))
                continue
            neighbors=(image.at(x0,y0),image.at(x1,y0),image.at(x0,y1),image.at(x1,y1))
            for a,b,c,d in zip(*neighbors,strict=True):
                first=a*(SCALE-fx)+b*fx
                second=c*(SCALE-fx)+d*fx
                result.append((first*(SCALE-fy)+second*fy+SCALE*SCALE//2)//(SCALE*SCALE))
    return Raster(width,height,bytes(result))


def _rotate(image,rule):
    obj(rule,("op","quarter_turns"))
    turns=integer(rule["quarter_turns"],"Putaran",0,3)
    if not turns:
        return image
    width,height=(image.height,image.width) if turns%2 else (image.width,image.height)
    result=bytearray()
    for y in range(height):
        for x in range(width):
            origin=(y,image.height-1-x) if turns==1 else (
                (image.width-1-x,image.height-1-y) if turns==2 else (image.width-1-y,x))
            result.extend(image.at(*origin))
    return Raster(width,height,bytes(result))


def _exposure(image,rule):
    obj(rule,("op","gain_milli","offset"))
    gain=integer(rule["gain_milli"],"Gain",100,4000)
    offset=integer(rule["offset"],"Offset",-200,200)
    lookup=bytes(max(0,min(255,(value*gain+500)//1000+offset)) for value in range(256))
    return Raster(image.width,image.height,image.pixels.translate(lookup))


def _patch(image,rule):
    obj(rule,("op","box","color"))
    x,y,w,h=_box(rule["box"],image)
    shade=color(rule["color"])
    if rule["op"]=="cover" and shade[3]!=255:
        raise ContractError("Cover membutuhkan warna opak.")
    canvas=bytearray(image.pixels)
    for row in range(y,y+h):
        for col in range(x,x+w):
            offset=3*(row*image.width+col)
            for channel in range(3):
                canvas[offset+channel]=(canvas[offset+channel]*(255-shade[3])+shade[channel]*shade[3]+127)//255
    return Raster(image.width,image.height,bytes(canvas))


def _blur_axis(data,width,height,radius,horizontal):
    result=bytearray(len(data))
    count,length=(height,width) if horizontal else (width,height)
    stride=3 if horizontal else width*3
    for lane in range(count):
        base=lane*width*3 if horizontal else lane*3
        for channel in range(3):
            start=base+channel
            sums=[0]
            for pos in range(length):
                sums.append(sums[-1]+data[start+pos*stride])
            for pos in range(length):
                low=max(0,pos-radius)
                high=min(length,pos+radius+1)
                window=high-low
                result[start+pos*stride]=(sums[high]-sums[low]+window//2)//window
    return result


def _blur(image,rule):
    obj(rule,("op","radius"))
    radius=integer(rule["radius"],"Radius blur",1,30)
    rows=_blur_axis(image.pixels,image.width,image.height,radius,True)
    columns=_blur_axis(rows,image.width,image.height,radius,False)
    return Raster(image.width,image.height,bytes(columns))


OPS={"crop":_crop,"resize":_resize,"rotate":_rotate,"exposure":_exposure,"cover":_patch,"tint":_patch,"box_blur":_blur}


def edit(payload,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.media.image-edit-plan.v1",("source_ref","input_sha256","format","operations"))
    source=text(plan["source_ref"],"Sumber edit")
    anchor=digest(plan["input_sha256"])
    if not isinstance(payload,bytes) or len(payload)>MAX_BYTES or sha256(payload).hexdigest()!=anchor:
        raise ContractError("Input edit tidak cocok dengan anchor.")
    image=raster(payload)
    log=[]
    budget=0
    for step,element in enumerate(entries(plan["operations"],24,1),1):
        name=element.get("op") if isinstance(element,dict) else None
        if not isinstance(name,str) or name not in OPS:
            raise ContractError("Operasi edit belum didukung.")
        before=image.receipt()
        budget+=image.width*image.height
        if budget>8_000_000:
            raise ContractError("Rantai edit melebihi anggaran piksel.")
        image=OPS[name](image,element)
        log.append({"step":step,"operation":name,"before":before,"after":image.receipt()})
    format_name=plan["format"]
    if format_name not in ("png","ppm"):
        raise ContractError("Format edit belum didukung.")
    result=png(image) if format_name=="png" else ppm(image)
    report={"schema":"ace.media.image-edit-receipt.v1","source_ref":source,"plan_sha256":expected,
            "input_sha256":anchor,"image_sha256":sha256(result).hexdigest(),"bytes":len(result),
            "format":format_name,"steps":log,**image.receipt()}
    return result,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("image","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        payload,proof=edit(read(args.image,MAX_BYTES),decode(read(args.plan)),args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(proof)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
