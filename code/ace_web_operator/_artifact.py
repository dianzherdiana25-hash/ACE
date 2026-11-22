"""Buka artefak relatif melalui descriptor dan terbitkan hanya berkas baru."""
from hashlib import sha256
import os
import stat

from ._contracts import ContractError, relative_path


DIR=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
FILE=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK


def read_relative(root,path,limit,expected=None):
    parts=relative_path(path).split("/")
    directory=os.open(root,DIR)
    try:
        for segment in parts[:-1]:
            child=os.open(segment,DIR,dir_fd=directory)
            os.close(directory)
            directory=child
        descriptor=os.open(parts[-1],FILE,dir_fd=directory)
        with os.fdopen(descriptor,"rb") as stream:
            first=os.fstat(stream.fileno())
            if not stat.S_ISREG(first.st_mode) or first.st_size>limit:
                raise ContractError("Artefak bukan berkas reguler dalam batas.")
            payload=stream.read(limit+1)
            last=os.fstat(stream.fileno())
            if (len(payload)>limit or len(payload)!=first.st_size or
                    (first.st_mtime_ns,first.st_ctime_ns)!=(last.st_mtime_ns,last.st_ctime_ns)):
                raise ContractError("Artefak berubah saat dibaca.")
        if expected is not None and sha256(payload).hexdigest()!=expected:
            raise ContractError("SHA-256 artefak tidak cocok.")
        return payload
    finally:
        os.close(directory)


def write_new(root,files):
    paths={}
    for key,value in files.items():
        name=relative_path(key)
        if not isinstance(value,bytes):
            raise ContractError("Artefak keluaran perlu byte.")
        paths[name]=value
    for name in paths:
        parts=name.split("/")
        if any("/".join(parts[:offset]) in paths for offset in range(1,len(parts))):
            raise ContractError("Nama berkas keluaran menimpa direktori.")
    root.mkdir(mode=0o700)
    for path,payload in sorted(paths.items()):
        target=root/path
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
