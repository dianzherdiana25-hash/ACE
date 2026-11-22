"""Uji mutu visual yang dapat diukur dari raster dan anotasi.

Census clipping, rentang luminans, perubahan tepi dan kontras pada
wilayah teks dibaca langsung dari piksel. Anotasi yang hilang tidak
menjadi bukti keterbacaan. QA tidak memutuskan selera visual.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,integer,obj,read,schema,text
from ._raster import MAX_BYTES,raster


SRGB=tuple(round((value/255/12.92 if value<=10 else ((value/255+0.055)/1.055)**2.4)*10000) for value in range(256))


def _luma(rgb):
    red,green,blue=(SRGB[channel] for channel in rgb)
    return (2126*red+7152*green+722*blue+5000)//10000


def _percentile(histogram,count,p):
    threshold=(count*p+99)//100
    total=0
    for value,seen in enumerate(histogram):
        total+=seen
        if total>=threshold:
            return value
    return 0


def _bounds(raw,image):
    if not isinstance(raw,list) or len(raw)!=4:
        raise ContractError("Kotak QA perlu empat integer.")
    x=integer(raw[0],"X",0,image.width-1)
    y=integer(raw[1],"Y",0,image.height-1)
    return x,y,integer(raw[2],"Lebar",1,image.width-x),integer(raw[3],"Tinggi",1,image.height-y)


def _region(values,width,box):
    x,y,w,h=box
    histogram=[0]*10001
    for index in range(y,y+h):
        for value in values[index*width+x:index*width+x+w]:
            histogram[value]+=1
    return _percentile(histogram,w*h,50)


def evaluate(payload,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.media.image-qa-plan.v1",("source_ref","image_sha256","minimum_width","minimum_height",
            "max_clipped_bp","min_range","min_edge_delta","require_text_regions","text_regions"))
    source=text(plan["source_ref"],"Sumber QA")
    anchor=digest(plan["image_sha256"])
    if not isinstance(payload,bytes) or sha256(payload).hexdigest()!=anchor:
        raise ContractError("Hash gambar tidak sama dengan rencana.")
    image=raster(payload)
    minimum_width=integer(plan["minimum_width"],"Lebar minimum",1,1800)
    minimum_height=integer(plan["minimum_height"],"Tinggi minimum",1,1800)
    cap=integer(plan["max_clipped_bp"],"Maksimum clipping",0,10000)
    breadth=integer(plan["min_range"],"Rentang luminans",0,10000)
    sharp=integer(plan["min_edge_delta"],"Ambang perubahan tepi",0,10000)
    if type(plan["require_text_regions"]) is not bool:
        raise ContractError("require_text_regions perlu boolean.")
    luminosity=[]
    histogram=[0]*10001
    for start in range(0,len(image.pixels),3):
        value=_luma(image.pixels[start:start+3])
        luminosity.append(value)
        histogram[value]+=1
    count=image.width*image.height
    clipped=(sum(histogram[:4])+sum(histogram[-4:]))*10000//count
    p5,p95=(_percentile(histogram,count,p) for p in (5,95))
    horizontal=sum(abs(a-b) for row in range(image.height)
                   for a,b in zip(luminosity[row*image.width:(row+1)*image.width-1],
                                  luminosity[row*image.width+1:(row+1)*image.width],strict=True))
    vertical=sum(abs(a-b) for a,b in zip(luminosity[:-image.width],luminosity[image.width:],strict=True))
    edges=(image.width-1)*image.height+(image.height-1)*image.width
    mean=(horizontal+vertical)//edges if edges else 0
    checklist=[{"rule":name,"pass":passed} for name,passed in
               (("size",image.width>=minimum_width and image.height>=minimum_height),
                ("clipping",clipped<=cap),("luminance_range",p95-p5>=breadth),("edge_change",mean>=sharp))]
    regions={}
    work=0
    for raw in entries(plan["text_regions"],50):
        obj(raw,("id","ink","background","minimum_ratio_milli","source_ref"))
        key=identifier(raw["id"],"ID area teks")
        if key in regions:
            raise ContractError("Area teks ganda.")
        fore,back=(_bounds(raw[key],image) for key in ("ink","background"))
        work+=fore[2]*fore[3]+back[2]*back[3]
        if work>3_000_000:
            raise ContractError("Sampel area QA terlalu besar.")
        values=sorted(_region(luminosity,image.width,bounds) for bounds in (fore,back))
        measured=(values[1]+500)*1000//(values[0]+500)
        required=integer(raw["minimum_ratio_milli"],"Rasio kontras",1000,21000)
        regions[key]={"id":key,"ink":list(fore),"background":list(back),"contrast_milli":measured,
                      "minimum_ratio_milli":required,"pass":measured>=required,"source_ref":text(raw["source_ref"],"Rujukan area")}
    if plan["require_text_regions"]:
        checklist.append({"rule":"text_annotations","pass":bool(regions)})
    checks=[*checklist,*regions.values()]
    success=sum(row["pass"] for row in checks)
    return {"schema":"ace.media.image-qa-receipt.v1","plan_sha256":expected,"source_ref":source,"image_sha256":anchor,
            **image.receipt(),"metrics":{"pixels":count,"clipped_bp":clipped,"luminance_p5":p5,"luminance_p95":p95,
                                        "mean_edge_delta":mean},
            "checks":checklist,"text_regions":[regions[key] for key in sorted(regions)],
            "score_bp":success*10000//len(checks),"status":"pass" if success==len(checks) else "hold"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        answer=evaluate(read(args.image,MAX_BYTES),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(answer)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(answer["status"]!="pass")


if __name__=="__main__":
    raise SystemExit(main())
