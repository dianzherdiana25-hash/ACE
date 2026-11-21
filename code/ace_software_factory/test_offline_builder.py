"""Verifier cache, tampering dan navigasi service worker di runtime JS."""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import offline_builder
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


NODE = '''
const assert=require("node:assert/strict");
const vm=require("node:vm");
const fs=require("node:fs");
const {webcrypto}=require("node:crypto");
const origin="http://127.0.0.1:9000";
const services=new Map();
const listeners=new Map();
let connected=true,tamper=false;
const context={
    URL,Response,crypto:webcrypto,
    self:{registration:{scope:origin+"/"},clients:{claim:async()=>{}},addEventListener:(id,fn)=>listeners.set(id,fn)},
    caches:{
        open:async name=>{
            if(!services.has(name))services.set(name,new Map());
            const state=services.get(name);
            return {put:async(url,payload)=>state.set(url,payload),match:async url=>state.get(url)?.clone()};
        },
        keys:async()=>[...services.keys()],
        delete:async name=>services.delete(name),
    },
    fetch:async url=>{
        if(!connected)throw Error("offline");
        if(tamper)return new Response("wrong");
        return new Response(fs.readFileSync(new URL(url).pathname.slice(1)));
    }
};
vm.runInNewContext(fs.readFileSync("ace-offline-worker.js","utf8"),context);
const tick=event=>new Promise((resolve,reject)=>listeners.get(event)({waitUntil:p=>p.then(resolve,reject)}));
const response=(url,method,mode)=>{let result; listeners.get("fetch")({request:{url,method,mode},respondWith:r=>{result=r}});return result;};
(async () => {
    tamper=true;
    await assert.rejects(tick("install"),/asset_sha256_mismatch/);
    assert.equal(services.size,0);
    tamper=false;
    await tick("install");
    services.set("unrelated",new Map());
    services.set("ace-offline:fixture_app:old",new Map());
    await tick("activate");
    assert.ok(services.has("unrelated"));
    assert.equal(services.has("ace-offline:fixture_app:old"),false);
    connected=false;
    assert.equal(await (await response(origin+"/offline.html","GET","same-origin")).text(),"Offline details");
    assert.equal(await (await response(origin+"/manual","GET","navigate")).text(),"Offline details");
    assert.equal(response(origin+"/manual","POST","navigate"),undefined);
    assert.equal(response("http://fixture.invalid/secret","GET","navigate"),undefined);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.folder=Path(self.enterContext(TemporaryDirectory()))
        self.root=self.folder/"source"
        self.source={"offline.html":b"Offline details","screen.css":b"body {}"}
        materialize(self.root,self.source)
        self.plan={"schema":"ace.factory-offline-plan.v1","id":"fixture_app","source_ref":"fixture/app",
                   "assets":[{"path":key,"sha256":sha256(data).hexdigest()} for key,data in self.source.items()],
                   "fallback":"offline.html"}

    def build(self):
        return offline_builder.build(self.root,self.plan,identity(self.plan))

    def test_byte_identity_and_refuses_tampered_input(self):
        first,report=self.build()
        self.assertEqual(first,self.build()[0])
        self.assertEqual(report["assets"][0]["path"],"offline.html")
        (self.root/"screen.css").write_bytes(b"body {margin:0}")
        with self.assertRaisesRegex(ContractError,"SHA-256"):
            self.build()

    def test_generated_service_worker_runtime_honors_origin_and_integrity(self):
        node=shutil.which("node")
        if node is None:
            self.skipTest("Node lokal tidak tersedia")
        files,_=self.build()
        output=self.folder/"output"
        materialize(output,{**files,"fixture.cjs":NODE.encode()})
        done=subprocess.run([node,"fixture.cjs"],cwd=output,capture_output=True,timeout=8)
        self.assertEqual(done.returncode,0,done.stderr)
