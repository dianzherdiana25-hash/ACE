"""Bangun repository Python awal yang dapat dijalankan dari blueprint.

Jejak spesifikasi dan arsitektur ditanam pada metadata produk.
Scaffold memberi CLI verifikasi metadata, batas paket, dan smoke
test yang membaca sumber hasil. Folder tujuan harus baru dan
artefak dibuat tanpa mengubah direktori sumber.
"""
import argparse
from hashlib import sha256
import keyword
from pathlib import Path, PurePosixPath
import sys

from ._contracts import ContractError, canonical, checked, decode, identifier, read, schema, text


PACKAGE = """# Package generated for {{name}}.
"""
APP = '''"""Jalur verifikasi metadata untuk scaffold yang dapat dijalankan."""
import argparse
import json
from pathlib import Path


def load(root):
    metadata = json.loads((root / "product.json").read_text(encoding="utf-8"))
    if metadata["schema"] != "ace.factory-scaffold-product.v1":
        raise ValueError("Metadata produk tidak sesuai.")
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    print(json.dumps(load(args.workspace), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
TEST = '''"""Cek metadata scaffold pada direktori produk."""
from pathlib import Path
import unittest

from {package}.app import load


class ScaffoldTests(unittest.TestCase):
    def test_load_demonstrates_bound_product_information(self):
        root = Path(__file__).resolve().parents[1]
        metadata = load(root)
        self.assertEqual(metadata["product_id"], {package!r})
        self.assertEqual(metadata["architecture_sha256"], {architecture!r})
        self.assertGreater(metadata["interface_count"], 0)
'''


def _relative(value):
    if not isinstance(value,str) or "\\" in value or not value:
        raise ContractError("Path artefak tidak sah.")
    parts=value.split("/")
    if any(part in ("",".","..") for part in parts) or PurePosixPath(value).is_absolute():
        raise ContractError("Path artefak di luar root.")
    return parts


def materialize(root, files):
    for name, payload in files.items():
        _relative(name)
        if not isinstance(payload,bytes):
            raise ContractError("Artefak perlu byte.")
    root.mkdir(mode=0o700)
    for name, payload in sorted(files.items()):
        target=root.joinpath(*_relative(name))
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)


def build(spec, architecture, expected):
    checked(architecture,expected)
    schema(architecture,"ace.factory-architecture.v1",("product_id","surface","spec_sha256","decision_sha256",
           "components","data_policy","interfaces","trace","unmapped_requirements","status"))
    checked(spec,architecture["spec_sha256"])
    name=identifier(spec["product_id"],"ID paket")
    if keyword.iskeyword(name) or name in sys.stdlib_module_names:
        raise ContractError("ID paket bertabrakan dengan Python.")
    if architecture["product_id"] != name or architecture["status"] != "ready" or not architecture["interfaces"]:
        raise ContractError("Arsitektur belum cocok untuk scaffold.")
    title=text(spec["name"],"Judul",120)
    metadata={"schema":"ace.factory-scaffold-product.v1","product_id":name,"name":title,
              "surface":architecture["surface"],"spec_sha256":architecture["spec_sha256"],
              "architecture_sha256":expected,"interface_count":len(architecture["interfaces"])}
    files={
        "product.json":canonical(metadata)+b"\n",
        f"{name}/__init__.py":PACKAGE.replace("{{name}}",name).encode(),
        f"{name}/app.py":APP.encode(),
        "tests/test_scaffold.py":TEST.format(package=name,architecture=expected).encode(),
        "README.md":(f"# {title}\n\n" + f"`python3 -m {name}.app` menampilkan metadata produk.\n\n" +
                     "`python3 -m unittest discover -s tests` menjalankan smoke test scaffold.\n").encode(),
    }
    report={"schema":"ace.factory-repo-scaffold.v1","product_id":name,"architecture_sha256":expected,
            "files":[{"path":key,"sha256":sha256(value).hexdigest(),"bytes":len(value)} for key,value in sorted(files.items())]}
    files["scaffold_manifest.json"]=canonical(report)+b"\n"
    return files,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec",type=Path)
    parser.add_argument("architecture",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,product=build(decode(read(args.spec)),decode(read(args.architecture)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(product)+b"\n")
    except (OSError,OverflowError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
