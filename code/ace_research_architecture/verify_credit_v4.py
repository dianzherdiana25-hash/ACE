"""R3-v4 local exact record replay of all banks; same source, not independent CI."""
from __future__ import annotations
import argparse, json,hashlib
from pathlib import Path
from . import credit_v4 as v4

FILES={
  'development':'credit_v4b_dev.json',
  'fresh':'credit_v4b_fork.json',
  'chain':'credit_v4b_chain.json',
}
ORIGINAL={'development':'credit_v4_dev.json','fresh':'credit_v4_fresh.json'}


def verify(root:Path):
    total=0
    for bank,f in FILES.items():
        obj=json.loads((root/f).read_text())
        saved=obj[bank]
        tasks=v4.DEVELOPMENT if bank=='development' else (v4.NEW_TASKS if bank=='fresh' else v4.CHAIN_TASKS)
        replay=v4.run_bank(tasks,range(2))
        assert saved['summary']==replay['summary'],f'{bank}: summary differs'
        assert saved['records']==replay['records'],f'{bank}: replay differs'
        assert len(saved['records'])==72
        for row in saved['records']:
            assert row['gate_work']<=v4.WORK_CAP
            assert row['candidate_count']<=v4.CANDIDATE_CAP
            assert row['proposals']<=v4.PROPOSAL_CAP
        total+=len(saved['records'])
        if bank in ORIGINAL:
            original=json.loads((root/ORIGINAL[bank]).read_text())[bank]
            unchanged=[r for r in saved['records'] if r['arm']!='credit_novelty']
            assert unchanged==original['records'],f'{bank}: v4 regression'
        print(bank,'REPLAY PASS',len(saved['records']),'SHA256',hashlib.sha256((root/f).read_bytes()).hexdigest())
    print('PASS v4b',total,'records replayed; 120/120 frozen v4 rows unchanged')
    return total

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=Path(__file__).parent)
    args=parser.parse_args()
    verify(args.directory)
