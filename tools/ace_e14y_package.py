"""Package exact frozen ACE E1.4y public results with all source/hashes/logs."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent.parent
WORK=ROOT/'WORK'
EVIDENCE=ROOT/'evidence/e14'
EVIDENCE.mkdir(parents=True,exist_ok=True)


def sha(b):return hashlib.sha256(b).hexdigest()


def package():
    from e14.e14y_bank import canonical
    from tools.ace_e14y_verify_lock import verify
    assert verify(ROOT)['status']=='PRESCORE_LOCK_VALID'
    sources=[]
    for start in (0,10,20,30):
        tag=f'{start:02d}-{start+9:02d}'
        a=(WORK/f'e14y-score-{tag}.json').read_bytes()
        b=(WORK/f'e14y-replay-{tag}.json').read_bytes()
        assert a==b
        scores=json.loads(a)
        digest=scores.pop('sha256')
        assert sha(canonical(scores))==digest
        target=f'evidence/e14/e14y_score_{tag}_v0.json.gz'
        (ROOT/target).write_bytes(gzip.compress(a,compresslevel=9,mtime=0))
        sources.append({'batch':tag,'arms':scores['arms'],'score_canonical_sha256':digest,
                        'score_raw_sha256':sha(a),'replay_raw_sha256':sha(b),
                        'score_and_fresh_replay_byte_equal':True,'stored_gzip_sha256':sha((ROOT/target).read_bytes()),
                        'stored_path':target})
    report={'version':1,'status':'ALL_400_ARMS_FRESH_REPLAY_BYTE_IDENTICAL',
            'scientific_decision':'NOT_ASSESSED','arm_count':sum(x['arms'] for x in sources),
            'score_batches':sources}
    manifest=EVIDENCE/'e14y_replay_verification_v0.json'
    manifest.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    for infile,outfile in [('WORK/e14y-audit-v0.json','evidence/e14/e14y_audit_v0.json'),
                           ('WORK/e14y-witness-v0.json','evidence/e14/e14y_witness_v0.json.gz'),
                           ('WORK/E14Y_REGRESSION/e14y-regression-summary.json','evidence/e14/e14y_regression_summary_v0.json')]:
        raw=(ROOT/infile).read_bytes()
        out=ROOT/outfile
        out.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if outfile.endswith('.gz') else raw)
    check=EVIDENCE/'e14y_prescore_source_verification_v0.json'
    check.write_text(json.dumps(verify(ROOT),indent=2,sort_keys=True)+'\n')
    files=[
      'code/e14/e14y_induction.py','code/e14/e14y_bank.py','code/e14/e14y_study.py',
      'code/e14/e14y_audit.py','code/e14/e14y_witness.py',
      'code/e14/test_e14y_induction.py','code/e14/test_e14y_audit.py','code/e14/test_e14y_witness.py',
      'tools/ace_e14y_verify_lock.py','tools/ace_e14y_regression.py','tools/ace_e14y_package.py',
      'design/e1.4/E14Y_TRANSFER_DEVELOPMENT_PROTOCOL_v0.md','design/e1.4/E14Y_PRESCORE_LOCK_v0.json',
      'design/e1.4/E14Y_TRANSFER_RESULT_DEV_v0.md',
      'evidence/e14/e14y_prescore_bank_v0.json','evidence/e14/e14y_replay_verification_v0.json',
      'evidence/e14/e14y_audit_v0.json','evidence/e14/e14y_witness_v0.json.gz',
      'evidence/e14/e14y_regression_summary_v0.json',
      'evidence/e14/e14y_prescore_source_verification_v0.json',
    ]
    files.extend(x['stored_path'] for x in sources)
    files.extend(str(p.relative_to(ROOT)) for p in sorted((ROOT/'WORK/E14Y_REGRESSION').glob('e14y-regression-*.log')))
    files.extend(str(p.relative_to(ROOT)) for p in sorted((ROOT/'WORK/E14Y_REGRESSION').glob('e14y-regression-*.json')))
    files=sorted(set(files))
    manifest_lines=[f'{sha((ROOT/p).read_bytes())}  {p}' for p in files]
    (ROOT/'MANIFEST_E14Y_SHA256.txt').write_text('\n'.join(manifest_lines)+'\n')
    archive=Path('/mnt/data/ACE_E14Y_Transfer_Experiment_20261105.zip')
    with ZipFile(archive,'w',compression=ZIP_DEFLATED,compresslevel=8) as z:
        for path in files+['MANIFEST_E14Y_SHA256.txt']:
            z.write(ROOT/path,path)
    assert ZipFile(archive).testzip() is None
    print(json.dumps({'zip':str(archive),'zip_sha256':sha(archive.read_bytes()),
                      'entries':len(files)+1,'manifest_files_verified':len(files),
                      'manifest_sha256':sha((ROOT/'MANIFEST_E14Y_SHA256.txt').read_bytes()),
                      'score_batches':len(sources),'score_arms':report['arm_count']},sort_keys=True))
    return files

if __name__=='__main__':package()
