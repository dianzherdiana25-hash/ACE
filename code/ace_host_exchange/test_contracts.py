import unittest
from ace_host_exchange.contracts import make_request,make_candidate,verify_request,verify_candidate,TARGET

class HostContractsTests(unittest.TestCase):
    def setUp(self):
        self.request=make_request('a'*40,'Improve a failing case','trace evidence','baseline passes; candidate improves')
    def test_deterministic_request_and_candidate_binding(self):
        self.assertEqual(self.request,make_request('a'*40,'Improve a failing case','trace evidence','baseline passes; candidate improves'))
        c=make_candidate(self.request,'Handle case','# candidate','Codex','host-selected')
        self.assertTrue(verify_candidate(self.request,c));self.assertEqual(c['target'],TARGET)
        self.assertFalse(c['promotion_authorized']);self.assertEqual(c['status'],'UNVALIDATED')
    def test_tampering_and_mismatched_request_rejected(self):
        c=make_candidate(self.request,'Hypothesis','# candidate','Codex','model')
        c['patch'] += ' changed';self.assertFalse(verify_candidate(self.request,c))
        self.request['constraints']['promotion_authorized']=True
        self.assertFalse(verify_request(self.request))
        with self.assertRaises(ValueError):make_candidate(self.request,'x','y','host','model')
    def test_boolean_cannot_be_replaced_by_integer(self):
        candidate=make_candidate(self.request,'hypothesis','# patch','Codex','model')
        candidate['promotion_authorized']=0
        self.assertFalse(verify_candidate(self.request,candidate))
    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):make_request('main','x','y','z')
        with self.assertRaises(ValueError):make_candidate(self.request,'x','x'*16385,'host','model')
        self.assertFalse(verify_candidate(self.request,{}))
if __name__=='__main__':unittest.main()

class HostDiagnosticTests(unittest.TestCase):
    def test_candidate_is_bound_to_base_and_patch(self):
        from unittest.mock import patch
        from ace_host_exchange.diagnostic import evaluate_host_candidate
        request=make_request('a'*40,'problem','evidence','criteria')
        candidate=make_candidate(request,'hypothesis','# patch','Codex','model')
        receipt={'base_commit':'a'*40,'patch_sha256':candidate['patch_sha256'],'promotion_authorized':False}
        with patch('ace_host_exchange.diagnostic.subprocess.check_output',return_value='a'*40+'\n'), patch('ace_host_exchange.diagnostic.evaluate_patch',return_value=receipt):
            result=evaluate_host_candidate('.',request,candidate)
            self.assertFalse(result['promotion_authorized']);self.assertEqual(result['candidate_id'],candidate['candidate_id'])
        with patch('ace_host_exchange.diagnostic.subprocess.check_output',return_value='b'*40+'\n'):
            with self.assertRaises(ValueError):evaluate_host_candidate('.',request,candidate)
        receipt['patch_sha256']='0'*64
        with patch('ace_host_exchange.diagnostic.subprocess.check_output',return_value='a'*40+'\n'), patch('ace_host_exchange.diagnostic.evaluate_patch',return_value=receipt):
            with self.assertRaises(RuntimeError):evaluate_host_candidate('.',request,candidate)
