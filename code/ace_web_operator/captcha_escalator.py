"""Kenali tanda challenge pada snapshot dan siapkan permintaan operator.

Deteksi tidak membuka link challenge, menyalin sitekey, atau mencoba
menyelesaikan challenge. Bukti berupa sumber, posisi HTML, dan
keluarga penanda. Handoff ditulis sebagai data lokal.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from urllib.parse import urlsplit

from ._contracts import ContractError,canonical,checked,decode,digest,identifier,read,schema,text
from .page_extractor import MAX_HTML,Snapshot


MARKERS={"g-recaptcha":"recaptcha","h-captcha":"hcaptcha","cf-turnstile":"turnstile"}


def _identify(node):
    labels=(node.attrs.get("class") or "").split()
    hits={family for marker,family in MARKERS.items() if marker in labels}
    if node.attrs.get("data-challenge") in ("captcha","human_check"):
        hits.add("declared_challenge")
    if node.tag=="iframe" and node.attrs.get("src"):
        try:
            target=urlsplit(node.attrs["src"])
            host=target.hostname or ""
        except ValueError:
            return hits
        if host in ("www.google.com","www.recaptcha.net") and target.path.startswith("/recaptcha/"):
            hits.add("recaptcha")
        if host=="hcaptcha.com" or host.endswith(".hcaptcha.com"):
            hits.add("hcaptcha")
        if host=="challenges.cloudflare.com" and "/turnstile/" in target.path:
            hits.add("turnstile")
    if "data-sitekey" in node.attrs and not hits:
        hits.add("unknown_sitekey_widget")
    return hits


def observe(html,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.challenge-assessment-plan.v1",("task","source_ref","html_ref","html_sha256"))
    key=identifier(plan["task"],"Tugas")
    pointer=text(plan["source_ref"],"Aturan challenge")
    source=text(plan["html_ref"],"Asal snapshot")
    anchor=digest(plan["html_sha256"])
    if not isinstance(html,bytes) or len(html)>MAX_HTML or sha256(html).hexdigest()!=anchor:
        raise ContractError("Snapshot challenge berbeda dari anchor.")
    matched=[]
    for row in Snapshot(html).elements:
        if row.tag not in ("iframe","div","section","input","form","span"):
            continue
        for name in sorted(_identify(row)):
            matched.append({"family":name,"tag":row.tag,"line":row.line,"source_ref":source})
    handoff=None if not matched else {"task":key,"action":"operator_review","reason":"human_verification_detected",
                                      "families":sorted({row["family"] for row in matched})}
    return {"schema":"ace.web.challenge-escalation.v1","plan_sha256":expected,"source_ref":pointer,
            "html_sha256":anchor,"status":"operator_required" if matched else "not_detected",
            "markers":matched,"handoff":handoff}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=observe(read(args.html,MAX_HTML),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="operator_required")


if __name__=="__main__":
    raise SystemExit(main())
