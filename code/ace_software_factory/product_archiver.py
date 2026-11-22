"""Arsipkan produk beserta resep replay yang terikat pada byte sumber.

Verifikasi archive memeriksa manifest, roster dan resep sebelum membuka
namespace unittest. Replay selalu menggunakan direktori baru dan sumber
read-only. Ringkasan menautkan versi serta bukti keberhasilan atau gagal.
"""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from . import release_packager
from ._contracts import ContractError,canonical,checked,decode,digest,identifier,identity,integer,read,schema,text
from .build_loop import _description,_read_tree,_runner
from .repo_scaffolder import materialize


RECIPE="build_recipe.json"
COMMAND=["python3","-m","unittest","discover","-s","tests","-v"]


def archive(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-archive-plan.v1",("product_id","version","source_ref","files","test_count","timeout_seconds"))
    product=identifier(plan["product_id"],"ID produk")
    source=text(plan["source_ref"],"Sumber arsip")
    count=integer(plan["test_count"],"Jumlah tes",1,5000)
    timeout=integer(plan["timeout_seconds"],"Batas waktu",1,30)
    files=_read_tree(root,plan["files"])
    if RECIPE in files or release_packager.MANIFEST in files:
        raise ContractError("Snapshot sumber menggunakan nama yang dicadangkan.")
    roster=_description(files)
    recipe={"schema":"ace.factory-archive-recipe.v1","plan_sha256":expected,"product_id":product,
            "version":plan["version"],"source_ref":source,"command":COMMAND,"test_count":count,"timeout_seconds":timeout,
            "source_tree_sha256":identity(roster),"files":roster}
    bundle={**files,RECIPE:canonical(recipe)+b"\n"}
    release={"schema":"ace.factory-release-plan.v1","product_id":product,"version":plan["version"],
             "source_ref":source,"files":_description(bundle)}
    with TemporaryDirectory(prefix="ace-factory-product-archive-") as folder:
        staging=Path(folder)/"package"
        materialize(staging,bundle)
        data,report=release_packager.build(staging,release,identity(release))
    result={"schema":"ace.factory-archive-report.v1","plan_sha256":expected,
            "product_id":product,"version":plan["version"],"archive_sha256":report["zip_sha256"],
            "manifest_sha256":report["manifest_sha256"],"recipe_sha256":sha256(bundle[RECIPE]).hexdigest(),
            "source_tree_sha256":recipe["source_tree_sha256"],"files":len(roster)}
    return data,result


def replay(data,archive_anchor,manifest_anchor,recipe_anchor,*,runner=_runner):
    if sha256(data).hexdigest()!=digest(archive_anchor):
        raise ContractError("SHA-256 archive berbeda.")
    digest(recipe_anchor)
    verified=release_packager.verify(data,manifest_anchor)
    with ZipFile(BytesIO(data)) as package:
        encoded=package.read(RECIPE) if RECIPE in package.namelist() else b""
        if sha256(encoded).hexdigest()!=recipe_anchor:
            raise ContractError("Resep archive absen atau SHA-256 berbeda.")
        recipe=decode(encoded)
        schema(recipe,"ace.factory-archive-recipe.v1",("plan_sha256","product_id","version","source_ref",
               "command","test_count","timeout_seconds","source_tree_sha256","files"))
        digest(recipe["plan_sha256"])
        product=identifier(recipe["product_id"],"ID produk")
        source=text(recipe["source_ref"],"Sumber archive")
        if recipe["command"]!=COMMAND:
            raise ContractError("Resep perlu command unittest kanonis.")
        count=integer(recipe["test_count"],"Jumlah tes",1,5000)
        timeout=integer(recipe["timeout_seconds"],"Batas waktu",1,30)
        files={name:package.read(name) for name in package.namelist() if name not in (RECIPE,release_packager.MANIFEST)}
        roster=_description(files)
        if recipe["files"]!=roster or recipe["source_tree_sha256"]!=identity(roster):
            raise ContractError("Roster archive dan resep berbeda.")
    with TemporaryDirectory(prefix="ace-factory-product-replay-") as folder:
        root=Path(folder)/"replay"
        materialize(root,files)
        _read_tree(root,roster)
        outcome=runner(root,timeout)
    status="verified_replay" if outcome["status"]=="passed" and outcome["tests"]==count and outcome["skipped"]==0 else "held"
    return {"schema":"ace.factory-archive-replay.v1","archive_sha256":verified["zip_sha256"],"recipe_sha256":recipe_anchor,
            "source_tree_sha256":recipe["source_tree_sha256"],"product_id":product,"source_ref":source,
            "verification":outcome,"status":status}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_subparsers(dest="mode",required=True)
    pack=modes.add_parser("archive")
    for key in ("root","plan","output"):
        pack.add_argument(key,type=Path)
    pack.add_argument("--expect-sha256",required=True)
    run=modes.add_parser("replay")
    run.add_argument("archive",type=Path)
    for key in ("archive-sha256","manifest-sha256","recipe-sha256"):
        run.add_argument(f"--{key}",required=True)
    args=parser.parse_args(argv)
    try:
        if args.mode=="archive":
            data,report=archive(args.root,decode(read(args.plan)),args.expect_sha256)
            with args.output.open("xb") as stream:
                stream.write(data)
        else:
            report=replay(read(args.archive,release_packager.ZIP_MAX),args.archive_sha256,args.manifest_sha256,args.recipe_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,KeyError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report.get("status")=="held")


if __name__=="__main__":
    raise SystemExit(main())
