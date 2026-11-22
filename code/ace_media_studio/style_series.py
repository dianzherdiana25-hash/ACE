"""Render seri gambar dari palet, susunan, dan motif yang konsisten.

Setiap panel memakai warna yang sama dan menempatkan motif lewat
seed serta ID panel. Strip palet menjadi bukti yang dicek ulang di
raster. Variasi di bawah batas geometri tidak mengubah identitas seri.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import image_generator
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text
from ._raster import color,dimensions,raster


RULES={"rectangle","ellipse","diamond"}


def _palette(raw):
    obj(raw,("background","shadow","accent","highlight"))
    shades={key:color(value) for key,value in raw.items()}
    if any(channel[3]!=255 for channel in shades.values()) or len(set(shades.values()))!=len(shades):
        raise ContractError("Palet seri perlu empat warna opak berbeda.")
    encoded={key:"#"+bytes(value[:3]).hex() for key,value in shades.items()}
    return encoded,shades


def _layout(width,height,margin,motif,shades,seed,key,rows,columns):
    step_x=(width-margin*2)//columns
    step_y=(height-margin*2)//rows
    if min(step_x,step_y)<10:
        raise ContractError("Margin dan grid menyisakan ruang motif terlalu kecil.")
    commands=[f"CANVAS {width} {height} {shades['background']}",
              f"GRADIENT y {shades['background']} {shades['shadow']}"]
    ribbon=max(2,margin//2)
    commands.extend(f"RECT {index*(width//4)} 0 {width//4 if index<3 else width-index*(width//4)} "
                    f"{ribbon} {shades[name]}" for index,name in
                    enumerate(("background","shadow","accent","highlight")))
    witnesses=[]
    for row in range(rows):
        for col in range(columns):
            hash_value=sha256(canonical([seed,key,row,col])).digest()
            palette=shades["accent" if hash_value[0]%2==0 else "highlight"]
            shade_height=max(3,step_y*(55+hash_value[1]%27)//100)
            shade_width=max(3,step_x*(53+hash_value[2]%32)//100)
            x=margin+col*step_x+(step_x-shade_width)//2
            y=margin+row*step_y+(step_y-shade_height)//2
            witnesses.append({"row":row,"column":col,"bounds":[x,y,shade_width,shade_height],"color":palette})
            if motif=="rectangle":
                command=f"RECT {x} {y} {shade_width} {shade_height} {palette}"
            elif motif=="ellipse":
                command=f"ELLIPSE {x} {y} {shade_width} {shade_height} {palette}"
            else:
                command=f"POLYGON {palette} {x+shade_width//2},{y} {x+shade_width},{y+shade_height//2} "
                command+=f"{x+shade_width//2},{y+shade_height} {x},{y+shade_height//2}"
            commands.append(command)
    return "\n".join(commands),witnesses


def build(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.media.style-series-plan.v1",("id","source_ref","width","height","margin","palette","motif","seed","panels",
                                                   "rows","columns"))
    key=identifier(plan["id"],"ID seri")
    source=text(plan["source_ref"],"Sumber desain")
    width,height=dimensions(plan["width"],plan["height"])
    if min(width,height)<24 or width*height>450_000:
        raise ContractError("Ukuran satu panel di luar budget seri.")
    margin=integer(plan["margin"],"Margin",4,min(width,height)//3)
    shades,rgba=_palette(plan["palette"])
    motif=plan["motif"]
    if not isinstance(motif,str) or motif not in RULES:
        raise ContractError("Motif seri tidak dikenal.")
    seed=integer(plan["seed"],"Seed",0,2**63-1)
    height_cells=integer(plan["rows"],"Baris grid",1,7)
    width_cells=integer(plan["columns"],"Kolom grid",1,7)
    panels=entries(plan["panels"],16,2)
    if len(panels)*width*height>2_000_000:
        raise ContractError("Total piksel seri melampaui budget.")
    signature={"canvas":[width,height],"margin":margin,"palette":shades,"motif":motif,
               "grid":[height_cells,width_cells],"palette_ribbon_px":max(2,margin//2)}
    stamp=identity(signature)
    files={}
    index={}
    for raw in panels:
        obj(raw,("id","source_ref"))
        name=identifier(raw["id"],"ID panel")
        if name in index:
            raise ContractError("Panel seri ganda.")
        pointer=text(raw["source_ref"],"Rujukan panel")
        recipe,motifs=_layout(width,height,margin,motif,shades,seed,name,height_cells,width_cells)
        config={"schema":"ace.media.image-plan.v1","id":name,"source_ref":pointer,"instructions":recipe,"format":"png"}
        data,receipt=image_generator.render(config,identity(config))
        actual=raster(data)
        for position,color_name in enumerate(("background","shadow","accent","highlight")):
            if actual.at(position*(width//4),0)!=rgba[color_name][:3]:
                raise ContractError("Strip palet hasil tidak sesuai style.")
        for shape in motifs:
            x,y,w,h=shape["bounds"]
            if actual.at(x+w//2,y+h//2)!=color(shape["color"])[:3]:
                raise ContractError("Warna motif pusat berbeda dari rencana.")
        dest=f"{name}.png"
        files[dest]=data
        index[name]={"id":name,"path":dest,"source_ref":pointer,"style_sha256":stamp,
                     "image_sha256":receipt["image_sha256"],"rgb_sha256":receipt["rgb_sha256"],
                     "motifs":motifs}
    distinct=len({row["rgb_sha256"] for row in index.values()})
    report={"schema":"ace.media.style-series-receipt.v1","plan_sha256":expected,"source_ref":source,"series":key,
            "style":signature,"style_sha256":stamp,"panels":[index[name] for name in sorted(index)],
            "distinct_panels":distinct,"status":"verified_style" if distinct==len(panels) else "held_duplicate"}
    files["style_series_receipt.json"]=canonical(report)+b"\n"
    return files,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(decode(read(args.plan)),args.expect_sha256)
        if report["status"]=="verified_style":
            args.output.mkdir(mode=0o700)
            for name,content in sorted(files.items()):
                with (args.output/name).open("xb") as stream:
                    stream.write(content)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="verified_style")


if __name__=="__main__":
    raise SystemExit(main())
