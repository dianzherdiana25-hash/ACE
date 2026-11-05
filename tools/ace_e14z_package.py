"""Archive precommitted E1.4z operator-drift source, exact score/replay and hashes."""
from __future__ import annotations
import gzip,hashlib,json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parent.parent
EVID=ROOT/'evidence/e14'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def package():
    from e14.e14y_bank import canonical
    from e14.e14z_drift import bank
    from tools.ace_e14y_verify_lock import verify
    assert verify(ROOT)['status']=='PRESCORE_LOCK_VALID'
    lock=json.loads((ROOT/'design/e1.4/E14Z_PRESCORE_LOCK_v0.json').read_text())
    if sha(canonical(bank()))!=lock['bank_sha256']:raise RuntimeError('E1.4z bank changed')
    for path,d in lock['files_sha256'].items():
        if sha((ROOT/path).read_bytes())!=d:raise RuntimeError('changed prescore file '+path)
    records=[]
    for begin in (0,5,10,15):
        stem=f'{begin:02d}-{begin+4:02d}'
        a=(ROOT/f'WORK/e14z-score-{stem}.json').read_bytes()
        b=(ROOT/f'WORK/e14z-replay-{stem}.json').read_bytes()
        if a!=b:raise RuntimeError('score/replay divergence: '+stem)
        payload=json.loads(a)
        canonical_score=payload.pop('sha256')
        if sha(canonical(payload))!=canonical_score:raise RuntimeError('score digest mismatch')
        name=f'evidence/e14/e14z_score_{stem}_v0.json.gz'
        (ROOT/name).write_bytes(gzip.compress(a,compresslevel=9,mtime=0))
        records.append({'batch':stem,'arms':payload['arm_count'],
                        'score_canonical_sha256':canonical_score,
                        'score_and_replay_byte_equal':True,
                        'raw_score_sha256':sha(a),
                        'raw_replay_sha256':sha(b),
                        'stored_path':name,'stored_gzip_sha256':sha((ROOT/name).read_bytes())})
    v={'version':1,'status':'400_400_FULL_REPLAY_IDENTICAL',
       'scientific_decision':'NOT_ASSESSED','prescore_bank_sha256':lock['bank_sha256'],
       'arms':sum(x['arms'] for x in records),'batches':records}
    (EVID/'e14z_replay_verification_v0.json').write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
    for src,dst in [
        ('WORK/e14z-audit-v0.json','evidence/e14/e14z_audit_v0.json'),
        ('WORK/e14z-witness-v0.json','evidence/e14/e14z_witness_v0.json.gz'),
        ('WORK/e14z-detection-limits-v0.json','evidence/e14/e14z_detection_limits_v0.json'),
        ('WORK/E14Y_REGRESSION/e14y-regression-summary.json','evidence/e14/e14z_regression_summary_v0.json'),
    ]:
        raw=(ROOT/src).read_bytes();output=ROOT/dst
        output.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if dst.endswith('.gz') else raw)
    verification={'e14y_previous_prescore_lock':verify(ROOT),
                  'e14z_lock_bank_sha256':lock['bank_sha256'],
                  'e14z_lock_file_checks':{name:sha((ROOT/name).read_bytes())==expected
                        for name,expected in lock['files_sha256'].items()},
                  'scientific_decision':'NOT_ASSESSED'}
    (EVID/'e14z_prescore_source_verification_v0.json').write_text(json.dumps(verification,indent=2,sort_keys=True)+'\n')
    paths=[
        'code/e14/e14z_drift.py','code/e14/e14z_audit.py','code/e14/e14z_witness.py',
        'code/e14/e14z_detection_limits.py','code/e14/test_e14z_drift.py',
        'code/e14/test_e14z_audit.py','code/e14/test_e14z_detection_limits.py',
        'tools/ace_e14z_package.py','tools/ace_e14y_regression.py',
        'design/e1.4/E14Z_SEMANTIC_DRIFT_PROTOCOL_DEV_v0.md',
        'design/e1.4/E14Z_SEMANTIC_DRIFT_RESULT_DEV_v0.md',
        'design/e1.4/E14Z_PRESCORE_LOCK_v0.json',
        'evidence/e14/e14z_prescore_drift_bank_v0.json',
        'evidence/e14/e14z_replay_verification_v0.json',
        'evidence/e14/e14z_audit_v0.json','evidence/e14/e14z_witness_v0.json.gz',
        'evidence/e14/e14z_detection_limits_v0.json',
        'evidence/e14/e14z_regression_summary_v0.json',
        'evidence/e14/e14z_prescore_source_verification_v0.json',
    ]
    paths.extend(x['stored_path'] for x in records)
    # Include all required source code from E1.4t-z, not private/hidden files.
    paths.extend(str(x.relative_to(ROOT)) for x in (ROOT/'code/e14').glob('*.py'))
    paths.extend(str(x.relative_to(ROOT)) for x in (ROOT/'code/e13').glob('*.py'))
    paths.extend(str(x.relative_to(ROOT)) for x in (ROOT/'WORK/E14Y_REGRESSION').glob('*.log'))
    paths.extend(str(x.relative_to(ROOT)) for x in (ROOT/'WORK/E14Y_REGRESSION').glob('*.json'))
    paths=sorted(set(paths))
    lines=[sha((ROOT/p).read_bytes())+'  '+p for p in paths]
    manifest=ROOT/'MANIFEST_E14Z_SHA256.txt'
    manifest.write_text('\n'.join(lines)+'\n')
    archive=Path('/mnt/data/ACE_E14Z_Semantic_Drift_20261105.zip')
    with ZipFile(archive,'w',compression=ZIP_DEFLATED,compresslevel=8) as z:
        for path in (*paths,'MANIFEST_E14Z_SHA256.txt'):
            z.write(ROOT/path,path)
    with ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('corrupt archive')
    result={'archive':str(archive),'zip_sha256':sha(archive.read_bytes()),
            'entries':len(paths)+1,'manifest_verified_files':len(paths),
            'manifest_sha256':sha(manifest.read_bytes()),
            'prescore_bank_sha256':lock['bank_sha256'],
            'score_arms':v['arms'],'prescore_files_unchanged':all(verification['e14z_lock_file_checks'].values())}
    print(json.dumps(result,sort_keys=True));return result

if __name__=='__main__':package()
