"""E1.4t independent-from-worker auditor: raw journals, labels, costs and replay."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, audit_journal, graph_oracle
from .e14t_bank import STRATA, audit_bank, sha
from .e14t_run import MODES, load_locked, report_from_rows


def open_report(path):
    report=json.loads(gzip.decompress(Path(path).read_bytes()))
    if report.get('status')!='COMPLETE' or type(report.get('rows')) is not list:
        raise ValueError('invalid scored report')
    return report


def audit(repo,bank_path,lock_path,sqlite_path,report_path):
    bank,lock=load_locked(repo,lock_path,bank_path)
    report=open_report(report_path)
    if report.get('bank_sha256')!=lock['bank_sha256']:
        raise ValueError('report bank digest mismatch')
    if report.get('summary')!=report_from_rows(report['rows']):
        raise ValueError('summary mismatches raw rows')
    if len(report['rows'])!=len(bank['worlds'])*len(MODES):
        raise ValueError('report truncated')
    lookup={w['id']:w for w in bank['worlds']}
    seen=set();label_calls=0;probe_calls=0;demonstration_calls=0
    for row in report['rows']:
        arm=row['arm']
        if arm in seen:
            raise ValueError('duplicate arm')
        seen.add(arm)
        world_id=arm.rsplit(':',1)[0];mode=arm.rsplit(':',1)[-1]
        if mode not in MODES or world_id not in lookup:
            raise ValueError('unknown arm')
        w=lookup[world_id]
        journal=DurableGraphBudget(sqlite_path,arm)
        snap=journal.snapshot()
        if snap['purchased']>4 or snap['remaining']!=4-snap['purchased']:
            raise ValueError('overspent label budget')
        oracle=lambda g, truth=tuple(w['target']):graph_oracle(g,truth)
        audit_result=audit_journal(snap,oracle)
        if row['receipt_sha256']!=sha(snap):
            raise ValueError('receipt digest mismatch')
        if row['purchased']!=audit_result['purchased'] or row['auditor_calls']!=audit_result['auditor_oracle_calls']:
            raise ValueError('receipt count mismatch')
        if row['resource_costs']!=audit_result['resource_totals']:
            raise ValueError('resource cost mismatch')
        if row['probe_labels']!=len(w['probes']) or row['demo_labels']!=len(w['demos']):
            raise ValueError('evaluation count mismatch')
        label_calls+=audit_result['auditor_oracle_calls']
        demonstration_calls+=len(w['demos'])
        probe_calls+=len(w['probes'])
        if row['covered']!=0 and row['covered']!=len(w['probes']):
            raise ValueError('partial arbitrary acceptance')
        if row['final_action'] not in ('accept','abstain'):
            raise ValueError('unterminated decision')
        if row['correct']+row['errors']!=row['covered']:
            raise ValueError('prediction tally mismatch')
    all_expected={w['id']+':'+m for w in bank['worlds'] for m in MODES}
    if seen!=all_expected:
        raise ValueError('incomplete world×arm matrix')
    return {'status':'AUDIT_PASS','arms':len(seen), 'bank_sha256':lock['bank_sha256'],
            'fresh_oracle_audit_calls':label_calls, 'source_demo_labels':demonstration_calls,
            'held_out_probe_labels':probe_calls,
            'all_label_caps_valid':True, 'all_receipt_digests_valid':True,
            'all_resource_costs_valid':True}


def compare_replay(original,replayed):
    first=open_report(original);second=open_report(replayed)
    if first['bank_sha256']!=second['bank_sha256']:
        raise ValueError('replay bank mismatch')
    a=first['rows'];b=second['rows']
    if len(a)!=len(b):
        raise ValueError('replay arm count differs')
    fields=('arm','stratum','mode','truth_sha256','final_action','word_correct','covered',
            'correct','errors','false_accept','purchased','auditor_calls','demo_labels',
            'probe_labels','resource_costs','receipt_sha256','source_origin')
    for row,r in zip(a,b):
        if any(row[k]!=r[k] for k in fields):
            raise ValueError('replay deterministic fields mismatch in '+row.get('arm','UNKNOWN'))
    if first['summary']['cells']:
        for group in first['summary']['cells']:
            for mode in MODES:
                metric_keys=('purchased','auditor_calls','demo_labels','probe_labels',
                    'word_correct','covered','correct','errors','false_accept','worlds')
                if any(first['summary']['cells'][group][mode][k]!=second['summary']['cells'][group][mode][k]
                       for k in metric_keys):
                    raise ValueError('replay summary mismatch')
    return {'status':'REPLAY_PASS','matched_arms':len(a),'deterministic_fields':len(fields),
            'elapsed_time_fields_excluded':True,'bank_sha256':first['bank_sha256']}
