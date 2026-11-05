"""Public postdevelopment source-only query design comparison (NOT blinded)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from .e14w_source import learn
from .e14w_audit import validate_receipts
from .e14u_primitive import PAIR_SPACE


def study(indices=range(28)):
    rows=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14w-source-study-') as home:
        journal=Path(home)/'source.sqlite'
        for i in indices:
            for mode in ('original','expanded'):
                record=learn(i,journal,mode=mode)
                independent=validate_receipts(record['source_journal'],PAIR_SPACE[i],'source-max')
                if independent!=record['labels']:
                    raise RuntimeError('source replay mismatch')
                rows.append(record)
    summary={mode:{'solved':sum(r['correct'] for r in rows if r['mode']==mode),
                   'labels':sum(r['labels'] for r in rows if r['mode']==mode),
                   'full_cap_failures':[r['world'] for r in rows
                                        if r['mode']==mode and not r['correct']],
                   'arms':sum(r['mode']==mode for r in rows)}
             for mode in ('original','expanded')}
    return {'status':'POSTSCORE_SOURCE_POLICY_COMPARISON','scientific_decision':'NOT_ASSESSED',
            'source_worlds':len(set(r['world'] for r in rows)),
            'arms':len(rows),'summary':summary,'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    result=study()
    raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    h=hashlib.sha256(raw).hexdigest()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({**result,'sha256':h},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'source_worlds':result['source_worlds'],
                      'arms':result['arms'],'summary':result['summary'],'sha256':h},sort_keys=True))

if __name__=='__main__':main()
