"""Verify that E1.4y's public prescore source and bank are exactly unchanged."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    root=Path(root).resolve()
    lock=json.loads((root/'design/e1.4/E14Y_PRESCORE_LOCK_v0.json').read_text())
    from e14.e14y_bank import build,canonical
    bank=json.loads((root/'evidence/e14/e14y_prescore_bank_v0.json').read_text())
    actual={path:hashlib.sha256((root/path).read_bytes()).hexdigest()
            for path in lock['source_sha256']}
    checks={path:(sha==lock['source_sha256'][path]) for path,sha in actual.items()}
    bank_ok=hashlib.sha256(canonical(bank)).hexdigest()==lock['prescore_bank_sha256']
    source_ok=all(checks.values())
    return {'status':'PRESCORE_LOCK_VALID' if bank_ok and source_ok else 'FAIL_CHANGED_SOURCE',
            'source_checks':checks,'bank_sha256':lock['prescore_bank_sha256'],
            'bank_hash_valid':bank_ok,'source_byte_identity':source_ok,
            'scientific_decision':'NOT_ASSESSED'}

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    result=verify(root)
    print(json.dumps(result,sort_keys=True))
    sys.exit(0 if result['status']=='PRESCORE_LOCK_VALID' else 2)
