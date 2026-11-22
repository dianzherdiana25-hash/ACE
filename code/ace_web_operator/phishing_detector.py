"""Tandai sinyal phishing pada HTML yang telah disimpan, tanpa mengikuti link.

Analisis hanya menemukan ketidakcocokan yang tampak seperti form dengan
kredensial di origin lain, link berlabel domain berbeda, atau skema
yang tidak dapat dibaca sebagai HTTP. Detail rahasia tidak diterbitkan.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys
from urllib.parse import urljoin,urlsplit

from ._contracts import ContractError,canonical,checked,decode,digest,entries,read,schema,text
from .page_extractor import MAX_HTML,Snapshot,_descendants
from .search_reader import address


SHOWN=re.compile(r"^https?://[^\s]+$",re.I)


def _target(base,raw):
    if not isinstance(raw,str) or "\\" in raw or len(raw)>1000 or any(not char.isprintable() for char in raw):
        return None,None,"address_invalid"
    try:
        target=urlsplit(urljoin(base,raw.strip()))
        if target.username is not None or target.password is not None:
            return target.hostname,None,"userinfo_in_link"
        if target.scheme not in ("http","https"):
            return None,target.scheme[:30],"unexpected_scheme"
        if not target.hostname:
            return None,target.scheme,"address_invalid"
        return target.hostname,target.scheme,None
    except ValueError:
        return None,None,"address_invalid"


def inspect(html,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.phishing-plan.v1",("source_ref","html_ref","page_url","html_sha256","trusted_hosts"))
    key=digest(plan["html_sha256"])
    page_url,site=address(plan["page_url"])
    pointer=text(plan["source_ref"],"Rujukan policy")
    html_ref=text(plan["html_ref"],"Rujukan halaman")
    if not isinstance(html,bytes) or len(html)>MAX_HTML or sha256(html).hexdigest()!=key:
        raise ContractError("Snapshot berbeda dari anchor.")
    trusted={site}
    for raw in entries(plan["trusted_hosts"],30):
        value=text(raw,"Host tepercaya",255)
        _,observed=address("https://"+value+"/")
        if observed!=value:
            raise ContractError("Host tepercaya bukan host kanonis.")
        trusted.add(value)
    marks=[]
    def add(code,node,target=None):
        marks.append({"rule":code,"tag":node.tag,"line":node.line,"host":target,"source_ref":html_ref})
    for node in Snapshot(html).elements:
        if node.tag=="a" and "href" in node.attrs:
            host,method,error=_target(page_url,node.attrs["href"])
            if error and method not in ("mailto","tel"):
                add(error,node,host)
                continue
            label=node.text()
            if host and SHOWN.fullmatch(label):
                try:
                    _,apparent=address(label)
                except ValueError:
                    continue
                if apparent!=host:
                    add("label_host_mismatch",node,host)
            if host and any(segment.startswith("xn--") for segment in host.split(".")) and host not in trusted:
                add("unregistered_punycode_host",node,host)
        elif node.tag=="form":
            controls=[child for child in _descendants(node) if child.tag=="input" and
                      (child.attrs.get("type") or "").casefold()=="password"]
            if not controls:
                continue
            host,method,error=_target(page_url,node.attrs.get("action") or "")
            if error or host not in trusted:
                add("password_form_untrusted_target",node,host)
            if method=="http":
                add("password_form_cleartext",node,host)
            if (node.attrs.get("method") or "get").casefold()!="post":
                add("password_form_query_submission",node,host)
    marks.sort(key=lambda row:(row["line"],row["rule"],row["host"] or ""))
    return {"schema":"ace.web.phishing-assessment.v1","plan_sha256":expected,"html_sha256":key,
            "source_ref":pointer,"host":site,"status":"review_required" if marks else "no_indicator_detected",
            "findings":marks}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=inspect(read(args.html,MAX_HTML),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="review_required")


if __name__=="__main__":
    raise SystemExit(main())
