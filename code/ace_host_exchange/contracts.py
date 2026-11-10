"""Versioned host exchange envelopes. They do not execute or approve code."""
from __future__ import annotations
import hashlib
import json
import re

TARGET = 'code/ace_self_dev/strategy_repair.py'
MAX_SNIPPET = 16384

def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()

def _digest(data):
    return hashlib.sha256(_canonical(data)).hexdigest()

def _text(value, name, maximum):
    if type(value) is not str or not value.strip() or len(value.encode('utf-8')) > maximum:
        raise ValueError('invalid ' + name)
    return value

def make_request(base_commit, problem, evidence, success_criteria):
    if type(base_commit) is not str or not re.fullmatch(r'[0-9a-f]{40}', base_commit):
        raise ValueError('base_commit must be a full Git SHA-1')
    request = {'schema':'ace.host-request.v1','base_commit':base_commit,'target':TARGET,
               'problem':_text(problem,'problem',2048),'evidence':_text(evidence,'evidence',8192),
               'success_criteria':_text(success_criteria,'success_criteria',2048),
               'constraints':{'patch_mode':'append_only','max_patch_bytes':MAX_SNIPPET,
                              'evaluator_changes_allowed':False,'promotion_authorized':False}}
    request['request_id'] = _digest(request)
    return request

def verify_request(request):
    if type(request) is not dict: return False
    try:
        return _canonical(request) == _canonical(make_request(request['base_commit'],request['problem'],request['evidence'],request['success_criteria']))
    except (KeyError, TypeError, ValueError, UnicodeError): return False

def make_candidate(request, hypothesis, patch, host, model):
    if not verify_request(request): raise ValueError('invalid request or request hash')
    candidate = {'schema':'ace.host-candidate.v1','request_id':request['request_id'],
                 'base_commit':request['base_commit'],'target':TARGET,
                 'hypothesis':_text(hypothesis,'hypothesis',4096),
                 'patch':_text(patch,'patch',MAX_SNIPPET),
                 'host':_text(host,'host',100),'model':_text(model,'model',100),
                 'status':'UNVALIDATED','promotion_authorized':False}
    candidate['patch_sha256'] = hashlib.sha256(patch.encode('utf-8')).hexdigest()
    candidate['candidate_id'] = _digest(candidate)
    return candidate

def verify_candidate(request, candidate):
    if type(candidate) is not dict: return False
    try:
        return _canonical(candidate) == _canonical(make_candidate(request,candidate['hypothesis'],candidate['patch'],candidate['host'],candidate['model']))
    except (KeyError, TypeError, ValueError, UnicodeError): return False
