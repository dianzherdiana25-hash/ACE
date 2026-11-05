"""Check every archived trial, decision and checksum against deterministic replay."""
from dataclasses import asdict
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import tempfile
from .benchmark import TASKS, bank
from .journal import _read, events
from .model import Grammar, Limits, IntegrityError, canonical, digest


def verify(root: Path) -> int:
    summary = json.loads((root/'summary.json').read_text())
    if summary['bank_sha256'] != digest({n:[[asdict(r) for r in split] for split in bank(n)] for n in TASKS}):
        raise IntegrityError('benchmark bank mismatch')
    if canonical(summary['grammar']) != canonical(asdict(Grammar())):
        raise IntegrityError('benchmark grammar mismatch')
    manifest = json.loads((root/'receipts_manifest.json').read_text())
    expected_paths = {budget+'/'+task+'/'+mode+'.jsonl'
                      for budget in ('standard','tight') for task in TASKS
                      for mode in ('fixed','fixed-list','enumerate','beam')}
    expected_archives = {task+'.json.gz' for task in TASKS}
    if len(manifest) != len(expected_archives) or {m['path'] for m in manifest} != expected_archives:
        raise IntegrityError('receipt archive manifest mismatch')
    records = {r['budget']+'/'+r['task']+'/'+r['mode']+'.jsonl':r for r in summary['results']}
    if set(records) != expected_paths or len(summary['results']) != len(records):
        raise IntegrityError('benchmark result set mismatch')
    seen = set()
    with tempfile.TemporaryDirectory() as directory:
        receipt = Path(directory)/'receipt'
        for item in manifest:
            packed = (root/item['path']).read_bytes()
            if len(packed) != item['bytes'] or hashlib.sha256(packed).hexdigest() != item['sha256']:
                raise IntegrityError('archive checksum mismatch')
            with gzip.open(root/item['path'],'rb') as stream:
                raw = stream.read(8*1024*1024+1)
            if len(raw) > 8*1024*1024:
                raise IntegrityError('oversized expanded archive')
            bundle = json.loads(raw)
            if len(bundle) != item['journals']:
                raise IntegrityError('archive entry count')
            for name, content in bundle.items():
                if name not in expected_paths or name in seen:
                    raise IntegrityError('unexpected or duplicate receipt')
                seen.add(name)
                budget, task, filename = name.split('/')
                receipt.write_text(content)
                rows = _read(receipt)
                limits = Limits(**summary['budgets'][budget])
                expected = list(events(Grammar(),limits,*bank(task),filename[:-6]))
                actual = [(r['kind'],r['payload']) for r in rows]
                if canonical(expected) != canonical(actual):
                    raise IntegrityError('archived semantic replay mismatch: '+name)
                record = records[name]
                if (rows[-1]['payload'] != record['result'] or rows[-1]['sha256'] != record['chain_head'] or
                        hashlib.sha256(receipt.read_bytes()).hexdigest() != record['journal_sha256']):
                    raise IntegrityError('summary receipt mismatch')
        if seen != expected_paths:
            raise IntegrityError('missing receipts')
    return len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=Path(__file__).parent/'results')
    args = parser.parse_args()
    print('PASS:',verify(args.results),'journals verified by checksum and semantic replay')


if __name__ == '__main__':
    main()
