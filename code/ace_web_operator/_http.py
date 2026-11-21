"""Transport eksplisit untuk fixture HTTP lokal, tanpa proxy atau redirect."""
from contextlib import closing
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException
from urllib.parse import urljoin, urlsplit

from ._contracts import ContractError, origin, web_path


@dataclass(frozen=True)
class Observation:
    status: int | None
    media_type: str | None
    body: bytes
    error: str | None


def fetch(base, path, *, cap=250_000, timeout=2):
    _,port=origin(base)
    path=web_path(path)
    if type(cap) is not int or not 1<=cap<=4_000_000 or type(timeout) not in (int,float) or not 0<timeout<=12:
        raise ContractError("Budget transport di luar batas.")
    try:
        with closing(HTTPConnection("127.0.0.1",port,timeout=timeout)) as client:
            client.request("GET",path,headers={"Accept-Encoding":"identity","Connection":"close",
                                              "User-Agent":"ACE-Local-Fixture/1"})
            row=client.getresponse()
            if 300<=row.status<400:
                return Observation(row.status,None,b"","redirect_refused")
            if row.headers.get("Content-Encoding","identity")!="identity":
                return Observation(row.status,None,b"","encoding_unsupported")
            received=row.read(cap+1)
            if len(received)>cap:
                return Observation(row.status,None,b"","body_limit")
            media=row.headers.get_content_type().casefold()
            return Observation(row.status,media,received,None)
    except TimeoutError:
        return Observation(None,None,b"","request_timeout")
    except (OSError,HTTPException):
        return Observation(None,None,b"","transport_failed")


def related(base, parent, href):
    if not isinstance(href,str) or not href or len(href)>1000 or any(not c.isprintable() for c in href):
        return None
    try:
        bound=urlsplit(urljoin(base+parent,href.strip()))
        if bound.scheme!="http" or f"{bound.scheme}://{bound.netloc}"!=base or bound.query:
            return None
        return web_path(bound.path or "/")
    except ValueError:
        return None
