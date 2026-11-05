"""Read-only R7.5 result audit. Does NOT load / execute evaluator code."""
import hashlib
import json
import sys

FAMILIES = ('stable','swap','reverse','new01','new23','all_null','correlated')
METHODS = ('full099','narrow099','narrow096','full096','random099','diag_abstain')
SEEDS = ('20261109','20261110','20261111')
CAPS = ('0','6','12','18','24')


def audit(data: bytes) -> dict:
    r = json.loads(data)
    checks = 0
    errors = []
    def ck(value, label):
        nonlocal checks
        checks += 1
        if not value:
            errors.append(label)
    ck(r.get('training_labels') == 1296, 'offline cost')
    ck(r.get('protocol') == 'R75_PROTOCOL.md', 'protocol')
    ck(tuple(r.get('seeds', [])) == tuple(map(int, SEEDS)), 'frozen seeds')
    ck(set(r['by_family_seed']) == set(FAMILIES), 'family inventory')
    ck(set(r['split_id_hashes']) == set(FAMILIES), 'hash family inventory')
    all_ids = []
    for family in FAMILIES:
        sdata = r['by_family_seed'][family]
        ck(set(sdata) == set(SEEDS), f'seed inventory {family}')
        for seed in SEEDS:
            h = r['split_id_hashes'][family][seed]
            ck(isinstance(h, str) and len(h) == 64, 'hash format')
            all_ids.append(h)
            data_by_cap = sdata[seed]
            ck(set(data_by_cap) == set(CAPS), 'cap inventory')
            ceiling = r['evaluator_only_oracle_ceiling'][family][seed]
            for cap in CAPS:
                rows = data_by_cap[cap]
                ck(set(rows) == set(METHODS), 'method inventory')
                for method, row in rows.items():
                    n = row['tasks']
                    ck(n == 24 and row['label_cap'] == int(cap), 'task/cap')
                    ck(0 <= row['purchases'] <= 24 * int(cap), 'budget')
                    ck(row['true_accepts'] + row['false_accepts'] + row['abstained'] == 6 * n, 'decision conservation')
                    ck(row['true_accepts'] <= ceiling, 'oracle ceiling')
                    ck(row['certified_tasks'] == row['true_accepts'] + row['false_accepts'], 'only one certificate')
                    ck(row['diagnostic_labels'] + row['certificate_labels'] == row['purchases'], 'purchase types accounted')
                    ck(sum(row['selected_groups'].values()) <= n, 'selected count')
                    ck(row['utility'] == 20*row['true_accepts'] -60*row['false_accepts'] -2*row['abstained']-row['purchases'], 'utility')
                    accepted = row['true_accepts'] + row['false_accepts']
                    ck(row['false_acceptance_rate'] is None if accepted == 0 else row['false_acceptance_rate'] == round(row['false_accepts']/accepted,6), 'ratio handling')
                    ck(0 <= row['ece'] <= 1 and 0 <= row['brier'] <= 1, 'calibration domains')
                    if method == 'diag_abstain':
                        ck(row['true_accepts'] == row['false_accepts'] == 0, 'negative control')
                        ck(row['purchases'] == n*min(12,int(cap)), 'negative control cost')
                    if method in ('full099','full096','random099'):
                        ck(row['diagnostic_labels'] == n*min(12,int(cap)), '6-group diag cap')
                    if method in ('narrow099','narrow096'):
                        ck(row['diagnostic_labels'] == n*min(6,int(cap)), '3-group diag cap')
                if cap == '0':
                    ck(all(v['purchases']==0 and v['true_accepts']==0 and v['false_accepts']==0 for v in rows.values()), 'zero cap')
    ck(len(set(all_ids)) == len(all_ids), 'unique seed/family manifests')
    def total(f, method, metric):
        return sum(r['by_family_seed'][f][seed]['24'][method][metric] for seed in SEEDS)
    ordinary = ('stable','swap','reverse','new01','new23')
    shifts = ordinary[1:]
    gate = {
        'new23_correct_better':total('new23','full099','true_accepts') > total('new23','narrow099','true_accepts'),
        'coverage_nondecrease_3_of_4':sum(total(f,'full099','true_accepts') >= total(f,'narrow099','true_accepts') for f in shifts)>=3,
        'all_null_wrong_nondecrease':total('all_null','full099','false_accepts')<=total('all_null','narrow099','false_accepts'),
        'five_family_utility_nondecrease':sum(total(f,'full099','utility') for f in ordinary) >= sum(total(f,'narrow099','utility') for f in ordinary),
        'online_caps_and_one_certificate':True,
    }
    ck(gate == r['locked_gate'], 'locked gate recomputation')
    ck(r['locked_gate_pass'] == all(gate.values()), 'locked pass bool')
    summary = {f: {m:{metric:total(f,m,metric) for metric in ('true_accepts','false_accepts','purchases','utility')} for m in ('full099','narrow099','narrow096','full096','random099','diag_abstain')} for f in FAMILIES}
    return {'status':'PASS' if not errors else 'FAIL', 'checks':checks,'errors':errors,
            'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data),
            'scoring_rerun':False, 'arms':len(FAMILIES)*len(SEEDS)*len(CAPS)*len(METHODS),
            'gate':gate,'per_family_at_24':summary,
            'utility_full_five_family':sum(total(f,'full099','utility') for f in ordinary),
            'utility_narrow_five_family':sum(total(f,'narrow099','utility') for f in ordinary)}


if __name__=='__main__':
    data=open(sys.argv[1],'rb').read()
    output=audit(data)
    print(json.dumps(output, indent=2, sort_keys=True))
    raise SystemExit(0 if output['status']=='PASS' else 2)
