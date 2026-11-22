"""Kelola sesi login sementara melalui antarmuka vault yang opak.

Vault memegang seluruh urusan credential dan memberikan handle browser.
Pemanggil hanya mendapat receipt dengan ID sesi, waktu dan status.
Sesi tidak dipakai lagi setelah kedaluwarsa atau pemeriksaan gagal.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
from secrets import token_hex
import sys
from threading import RLock
from typing import Protocol

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,integer,obj,origin,read,schema,text


class BrowserSession(Protocol):
    def authenticated(self) -> bool: ...
    def close(self) -> None: ...


class Vault(Protocol):
    def open_session(self, account_ref: str, origin: str) -> BrowserSession: ...


@dataclass(frozen=True)
class _Lease:
    session_id: str
    origin: str
    expires_at: int
    session: BrowserSession


def policy(raw,expected):
    checked(raw,expected)
    schema(raw,"ace.web.session-policy.v1",("source_ref","accounts","ttl_seconds","max_active"))
    source=text(raw["source_ref"],"Sumber daftar akun")
    accounts={}
    for row in entries(raw["accounts"],50,1):
        obj(row,("ref","origin","source_ref"))
        key=identifier(row["ref"],"Rujukan vault")
        site,_=origin(row["origin"])
        if key in accounts:
            raise ContractError("Rujukan vault ganda.")
        accounts[key]=(site,text(row["source_ref"],"Sumber izin"))
    cap=integer(raw["max_active"],"Sesi aktif",1,20)
    ttl=integer(raw["ttl_seconds"],"Usia sesi",10,3600)
    return source,accounts,ttl,cap


class SessionManager:
    """Pisahkan rujukan vault dari sesi browser dan hasil verifikasi."""

    def __init__(self,raw,expected,vault,clock):
        self._source,self._accounts,self._ttl,self._cap=policy(raw,expected)
        self._expect=expected
        self._vault=vault
        self._clock=clock
        self._sessions={}
        self._lock=RLock()

    def _release(self,key):
        item=self._sessions[key]
        try:
            item.session.close()
        except Exception:
            return False
        del self._sessions[key]
        return True

    def _receipt(self,account,status,reason=None,item=None):
        return {"schema":"ace.web.session-receipt.v1","policy_sha256":self._expect,"account_ref":account,
                "source_ref":self._accounts.get(account,(None,self._source))[1],"status":status,"reason":reason,
                "session_id":item.session_id if item else None,"expires_at":item.expires_at if item else None}

    def start(self,key,base):
        key=identifier(key,"Rujukan vault")
        site,_=origin(base)
        if key not in self._accounts or self._accounts[key][0]!=site:
            return self._receipt(key,"held","account_or_origin_unregistered")
        with self._lock:
            now=integer(self._clock(),"Jam",0,2**40)
            for account in list(self._sessions):
                if self._sessions[account].expires_at<=now and not self._release(account):
                    return self._receipt(key,"held","cleanup_failed")
            active=self._sessions.get(key)
            if active is not None:
                try:
                    if active.session.authenticated() is True:
                        return self._receipt(key,"active_reused",item=active)
                except Exception:
                    pass
                if not self._release(key):
                    return self._receipt(key,"held","cleanup_failed")
            if len(self._sessions)>=self._cap:
                return self._receipt(key,"held","session_capacity")
            session=None
            try:
                session=self._vault.open_session(key,site)
                if session.authenticated() is not True:
                    raise ContractError("Login belum terverifikasi.")
                latest=integer(self._clock(),"Jam",now,2**40)
            except Exception:
                if session is not None:
                    try:
                        session.close()
                    except Exception:
                        self._sessions[key]=_Lease(token_hex(16),site,now,session)
                        return self._receipt(key,"held","cleanup_failed")
                return self._receipt(key,"held","vault_session_failed")
            lease=_Lease(token_hex(16),site,latest+self._ttl,session)
            self._sessions[key]=lease
            return self._receipt(key,"active_new",item=lease)

    def stop(self,key):
        key=identifier(key,"Rujukan vault")
        with self._lock:
            if key not in self._sessions:
                return self._receipt(key,"held","session_missing")
            closed=self._release(key)
            return self._receipt(key,"closed" if closed else "held",None if closed else "cleanup_failed")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        source,accounts,ttl,cap=policy(decode(read(args.policy)),args.expect_sha256)
        report={"schema":"ace.web.session-plan-report.v1","policy_sha256":args.expect_sha256,
                "source_ref":source,"accounts":[{"ref":key,"origin":site,"source_ref":ref}
                                              for key,(site,ref) in sorted(accounts.items())],
                "ttl_seconds":ttl,"max_active":cap}
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
