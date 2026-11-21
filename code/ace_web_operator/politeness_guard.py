"""Putuskan request lokal dengan robots.txt yang di-anchor dan history kuota.

User-agent terpanjang dipilih, path aturan terpanjang menang, dan Allow
menang seri. Batas minimum, Crawl-delay dan Retry-After mengikat sebelum
transport dipanggil. Tidak ada request saat putusan ditahan.
"""
import argparse
from fnmatch import translate
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,integer,obj,origin,read,schema,text,web_path
from ._http import fetch
from .web_scheduler import iso,time_value


LIMIT=160_000


def _rule(raw):
    if not raw.startswith("/") or len(raw)>250 or not raw.isascii() or not raw.isprintable() or " " in raw:
        raise ContractError("Pola robots tak didukung.")
    stop=raw.endswith("$")
    value=raw[:-1] if stop else raw
    if "$" in value or value.count("*")>8 or "**" in value:
        raise ContractError("Pola robots terlalu kompleks.")
    literal=value.replace("[","[[]").replace("?","[?]")
    pattern=translate(literal if stop else literal+"*")
    return len(value.replace("*","")),re.compile(pattern)


def robots_policy(data,user_agent,path):
    if not isinstance(data,bytes) or len(data)>LIMIT:
        raise ContractError("robots.txt melampaui batas.")
    source=data.decode("utf-8-sig")
    groups=[]
    agents,rules,delays=[],[],[]
    live=False
    for line,raw in enumerate(source.splitlines(),1):
        fragment=raw.split("#",1)[0].strip()
        option,separator,value=fragment.partition(":")
        if not separator:
            continue
        key=option.strip().casefold()
        value=value.strip()
        if key=="user-agent":
            if live:
                groups.append((agents,rules,delays))
                agents,rules,delays=[],[],[]
                live=False
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}|\*",value):
                raise ContractError("Sintaks agen robots tidak dikenal.")
            agents.append(value.casefold())
        elif agents and key in ("allow","disallow","crawl-delay"):
            live=True
            if key=="crawl-delay":
                if len(value)>3 or not value.isascii() or not value.isdigit() or int(value)>120:
                    raise ContractError("Crawl-delay perlu detik integer dalam batas.")
                delays.append(int(value))
            elif value:
                score,pattern=_rule(value)
                rules.append((score,key=="allow",line,pattern))
        if len(agents)>100 or len(rules)>2000 or len(groups)>250:
            raise ContractError("robots.txt terlalu kompleks.")
    if agents:
        groups.append((agents,rules,delays))
    ranked=[]
    agent=user_agent.casefold().split("/",1)[0]
    for aliases,clauses,spacing in groups:
        priorities=[0 if key=="*" else len(key) for key in aliases if key=="*" or agent.startswith(key)]
        if priorities:
            ranked.append((max(priorities),clauses,spacing))
    if not ranked:
        return {"allowed":True,"rule_line":None,"crawl_delay":0}
    priority=max(row[0] for row in ranked)
    applicable=[entry for score,clauses,_ in ranked if score==priority for entry in clauses if entry[3].match(path)]
    spacing=max((delay for score,_,delays in ranked if score==priority for delay in delays),default=0)
    if not applicable:
        return {"allowed":True,"rule_line":None,"crawl_delay":spacing}
    _,allowed,line,_=max(applicable,key=lambda entry:(entry[0],entry[1],-entry[2]))
    return {"allowed":allowed,"rule_line":line,"crawl_delay":spacing}


def evaluate(plan,expected,robots,history):
    checked(plan,expected)
    schema(plan,"ace.web.politeness-plan.v1",("source_ref","origin","path","agent","now","robots_sha256",
                                            "history_sha256","interval_seconds","hourly_cap"))
    checked(history,plan["history_sha256"])
    schema(history,"ace.web.politeness-history.v1",("requests",))
    pointer=text(plan["source_ref"],"Sumber kebijakan")
    base,_=origin(plan["origin"])
    path=web_path(plan["path"])
    agent=text(plan["agent"],"User agent",120)
    if not isinstance(robots,bytes) or sha256(robots).hexdigest()!=digest(plan["robots_sha256"]):
        raise ContractError("Byte robots.txt berbeda dari anchor.")
    policy=robots_policy(robots,agent,path)
    now=time_value(plan["now"])
    interval=max(policy["crawl_delay"],integer(plan["interval_seconds"],"Jeda minimum",1,600))
    cap=integer(plan["hourly_cap"],"Kuota per jam",1,150)
    seen=[]
    active_backoffs=[]
    for row in entries(history["requests"],3000):
        obj(row,("origin","at","status","retry_after_seconds","source_ref"))
        site,_=origin(row["origin"])
        at=time_value(row["at"])
        status=integer(row["status"],"HTTP status",100,599)
        delay=integer(row["retry_after_seconds"],"Retry-After",0,86_400) if row["retry_after_seconds"] is not None else 0
        text(row["source_ref"],"Sumber request")
        if at>now or delay and status not in (429,503):
            raise ContractError("Riwayat mencatat waktu atau Retry-After yang tidak cocok.")
        if site==base:
            seen.append(at)
            if delay and at+delay>now:
                active_backoffs.append(at+delay)
    recent=sorted(at for at in seen if at>now-3600)
    deadlines=[]
    if seen:
        deadlines.append((max(seen)+interval,"crawl_delay"))
    if len(recent)>=cap:
        deadlines.append((recent[-cap]+3600,"hourly_cap"))
    if active_backoffs:
        deadlines.append((max(active_backoffs),"retry_after"))
    next_time,reason=max(deadlines,default=(now,None))
    allowed=policy["allowed"] and next_time<=now
    return {"schema":"ace.web.politeness-receipt.v1","plan_sha256":expected,"source_ref":pointer,
            "status":"allowed" if allowed else "held","reason":None if allowed else (
                "robots_denied" if not policy["allowed"] else reason),
            "robots":policy,"next_allowed_at":iso(next_time) if policy["allowed"] and not allowed else None,
            "requests_last_hour":len(recent),"origin":base,"path":path}


def fetch_if_allowed(plan,expected,robots,history,*,transport=fetch):
    report=evaluate(plan,expected,robots,history)
    if report["status"]!="allowed":
        return None,report
    return transport(report["origin"],report["path"]),report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","robots","history"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=evaluate(decode(read(args.plan)),args.expect_sha256,read(args.robots,LIMIT),decode(read(args.history)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="allowed")


if __name__=="__main__":
    raise SystemExit(main())
