"""Verifier paging Chromium, dedup dan penghentian yang tidak diklaim tuntas."""
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest

from ace_web_operator import scroll_handler,web_ops_bench
from ace_web_operator._contracts import identity
from ace_web_operator.test_browser_engine import browser_available


HTML=b'''<ol data-testid="items"><li data-item-id="first">One</li></ol>
<button data-testid="next" onclick="setTimeout(go,60)">Next</button><span hidden data-testid="end">Selesai</span>
<script>
let page=0;
function go() {
 const list=document.querySelector('ol');
 page+=1;
 const added=document.createElement('li');added.dataset.itemId=page===1?'second':'third';added.textContent='Item';
 list.append(added);
 if(page===2)document.querySelector('[data-testid=end]').hidden=false;
}
</script>'''


class ScrollTests(unittest.TestCase):
    def setUp(self):
        self.host=self.enterContext(ThreadingHTTPServer(("127.0.0.1",0),web_ops_bench.FixtureHandler))
        self.host.pages={"/list":("text/html",HTML),"/favicon.ico":("text/plain",b"icon")}
        self.host.requests=[]
        runner=Thread(target=self.host.serve_forever,daemon=True)
        runner.start()
        self.addCleanup(runner.join,3)
        self.addCleanup(self.host.shutdown)
        self.plan={"schema":"ace.web.scroll-plan.v1","source_ref":"fixture/pagination","path":"/list","list_test_id":"items",
                   "end_test_id":"end","next_test_id":"next","max_turns":2,"minimum_items":3,
                   "browser":{"origin":f"http://127.0.0.1:{self.host.server_port}","allow_paths":["/list","/favicon.ico"],
                              "timeout_ms":1200,"request_limit":10}}

    def test_real_pagination_accumulates_three_unique_items_and_stops_at_guard(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        report=scroll_handler.collect(self.plan,identity(self.plan))
        self.assertEqual((report["status"],report["unique"],report["end_reached"]),("complete",3,True),report)
        self.assertEqual([row["unique"] for row in report["observed"]],[1,2,3])
        self.plan["max_turns"]=1
        partial=scroll_handler.collect(self.plan,identity(self.plan))
        self.assertEqual((partial["status"],partial["reason"],partial["unique"]),("partial","turn_limit",2))
