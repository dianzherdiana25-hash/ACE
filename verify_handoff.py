#!/usr/bin/env python3
import hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parent
m=json.loads((root/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
errors=[]
for x in m['files']:
 p=root/x['path']
 if not p.is_file(): errors.append('MISSING: '+x['path']);continue
 data=p.read_bytes()
 if hashlib.sha256(data).hexdigest()!=x['sha256'] or len(data)!=x['size_bytes']: errors.append('MISMATCH: '+x['path'])
print('PASS' if not errors else 'FAIL',f"{len(m['files'])-len(errors)}/{len(m['files'])} files verified")
for error in errors: print(error)
sys.exit(bool(errors))
