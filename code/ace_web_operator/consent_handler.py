"""Tangani banner consent lewat kontrol yang disediakan dan disetujui.

Kebijakan hanya mengenali dialog consent berpenanda eksplisit.
Ketika pilihan tidak tersedia atau bukti persetujuan kurang, hasilnya
menunggu operator. Tool menghasilkan rencana klik untuk fixture lokal.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,identifier,origin,read,schema,text,web_path
from .page_extractor import MAX_HTML,Snapshot,_descendants


CHOICES={"deny_optional","allow_declared","close_if_optional"}


def plan_action(html,settings,expected):
    checked(settings,expected)
    schema(settings,"ace.web.consent-plan.v1",("source_ref","snapshot_sha256","snapshot_ref","origin","path",
                                               "dialog_id","decision","approval_ref"))
    reference=text(settings["source_ref"],"Rujukan consent")
    snapshot=text(settings["snapshot_ref"],"Rujukan snapshot")
    anchor=digest(settings["snapshot_sha256"])
    if not isinstance(html,bytes) or len(html)>MAX_HTML or sha256(html).hexdigest()!=anchor:
        raise ContractError("Snapshot consent tidak cocok dengan anchor.")
    base,_=origin(settings["origin"])
    path=web_path(settings["path"])
    tag=identifier(settings["dialog_id"],"ID banner")
    decision=settings["decision"]
    if not isinstance(decision,str) or decision not in CHOICES:
        raise ContractError("Pilihan consent tidak didukung.")
    authorization=settings["approval_ref"]
    if authorization is not None:
        authorization=text(authorization,"Rujukan persetujuan",250)
    output={"schema":"ace.web.consent-receipt.v1","plan_sha256":expected,"snapshot_sha256":anchor,
            "source_ref":reference,"snapshot_ref":snapshot,"origin":base,"path":path,"decision":decision,
            "approval_ref":authorization,"dialog_line":None,"steps":[],"status":"operator_required","reason":None}
    nodes=Snapshot(html).elements
    candidates=[node for node in nodes if node.attrs.get("data-consent")==tag
              and (node.tag=="dialog" or node.attrs.get("role")=="dialog") and "hidden" not in node.attrs]
    if not candidates:
        return {**output,"status":"absent","reason":"known_banner_absent"}
    if len(candidates)!=1:
        return {**output,"reason":"ambiguous_banner"}
    panel=candidates[0]
    output["dialog_line"]=panel.line
    if not authorization:
        return {**output,"reason":"decision_without_approval"}
    if panel.attrs.get("data-kind")!="cookie_preferences":
        return {**output,"reason":"not_optional_cookie_banner"}
    if decision=="close_if_optional" and panel.attrs.get("data-dismissible")!="true":
        return {**output,"reason":"banner_not_dismissible"}
    matches=[node for node in _descendants(panel) if node.tag=="button" and node.attrs.get("type")=="button" and (
        node.attrs.get("data-consent-choice")==decision and "disabled" not in node.attrs
        and node.attrs.get("aria-disabled")!="true"
    )]
    if len(matches)!=1 or not matches[0].attrs.get("data-testid"):
        return {**output,"reason":"approved_control_unavailable"}
    locator=identifier(matches[0].attrs["data-testid"],"Selector aksi consent")
    if sum(node.attrs.get("data-testid")==locator for node in nodes)!=1:
        return {**output,"reason":"ambiguous_control"}
    return {**output,"status":"action_planned","steps":[{"id":"open_consent","op":"navigate","path":path},
            {"id":"approved_consent","op":"click","test_id":locator}]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=plan_action(read(args.html,MAX_HTML),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="operator_required")


if __name__=="__main__":
    raise SystemExit(main())
