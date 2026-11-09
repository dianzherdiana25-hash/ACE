"""Execute a host candidate through the candidate-bound diagnostic gate."""
from __future__ import annotations
import hashlib
from pathlib import Path
import subprocess
from .contracts import verify_candidate
from ace_code_agent.patch_diagnostic import evaluate_patch


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
    if receipt['base_commit'] != head or receipt['patch_sha256'] != candidate['patch_sha256']:
        raise RuntimeError('BLOCKED: evaluated snapshot or patch differs from candidate')
    return {'schema':'ace.host-evaluation.v1','request_id':request['request_id'],
            'candidate_id':candidate['candidate_id'],'diagnostic':receipt,
            'status':'DIAGNOSTIC_ONLY','promotion_authorized':False}
