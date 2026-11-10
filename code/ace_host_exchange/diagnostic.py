"""Execute a host candidate through the candidate-bound diagnostic gate."""
from __future__ import annotations
import hashlib
from pathlib import Path
import subprocess
from .contracts import verify_candidate
from ace_code_agent.patch_diagnostic import evaluate_patch, verify_receipt


def evaluate_host_candidate(repo, request, candidate):
    if not verify_candidate(request, candidate):
        raise ValueError('invalid or mismatched host candidate')
    repo=Path(repo).resolve()
    try:
        head=subprocess.check_output(['git','rev-parse','--verify','HEAD^{commit}'],cwd=repo,text=True,timeout=10).strip()
    except (OSError,subprocess.SubprocessError) as exc:
        raise RuntimeError('BLOCKED: cannot inspect base commit') from exc
    if head != request['base_commit']:
        raise ValueError('candidate base commit does not match current HEAD')
    try:
        receipt=evaluate_patch(repo,candidate['target'],candidate['patch'])
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError('BLOCKED: cannot construct committed snapshot') from exc
    if (not verify_receipt(receipt) or receipt.get('base_commit') != head or
            receipt.get('target') != candidate['target'] or
            receipt.get('patch_sha256') != candidate['patch_sha256'] or
            receipt.get('promotion_authorized') is not False):
        raise RuntimeError('BLOCKED: evaluated snapshot or patch differs from candidate')
    try:
        baseline = subprocess.check_output(
            ['git', 'show', head + ':' + candidate['target']], cwd=repo, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError('BLOCKED: cannot read committed target') from exc
    if (receipt.get('base_file_sha256') != hashlib.sha256(baseline).hexdigest() or
            receipt.get('candidate_file_sha256') != hashlib.sha256(
                baseline + b'\n' + candidate['patch'].encode('utf-8')).hexdigest()):
        raise RuntimeError('BLOCKED: evaluated target bytes differ from candidate')
    return {'schema':'ace.host-evaluation.v1','request_id':request['request_id'],
            'candidate_id':candidate['candidate_id'],'diagnostic':receipt,
            'provenance_authentication':'SELF_REPORTED',
            'receipt_authentication':'NONE_CHECKSUM_ONLY',
            'status':'DIAGNOSTIC_ONLY','promotion_authorized':False}
