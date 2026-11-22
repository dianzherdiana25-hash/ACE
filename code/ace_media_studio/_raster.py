"""Representasi RGB untuk render dan verifikasi PNG/PPM lintas alat lokal."""
from dataclasses import dataclass
from hashlib import sha256
import re
from struct import pack,unpack_from
from zlib import compress,crc32,decompressobj,error as ZlibError

from ._contracts import ContractError,integer


MAX_PIXELS=1_400_000
MAX_DIM=1800
MAX_BYTES=6_000_000
PNG=b"\x89PNG\r\n\x1a\n"
COLOR=re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?")
PPM_HEADER=re.compile(rb"P6\s+([0-9]{1,4})\s+([0-9]{1,4})\s+255(?:\r\n|[\x09\x0a\x0d\x20])")


def dimensions(width,height):
    integer(width,"Lebar",1,MAX_DIM)
    integer(height,"Tinggi",1,MAX_DIM)
    if width*height>MAX_PIXELS:
        raise ContractError("Jumlah piksel melampaui anggaran.")
    return width,height


def color(raw):
    if not isinstance(raw,str) or not COLOR.fullmatch(raw):
        raise ContractError("Warna perlu #RRGGBB atau #RRGGBBAA.")
    data=bytes.fromhex(raw[1:])
    return tuple(data) if len(data)==4 else (*data,255)


@dataclass(frozen=True)
class Raster:
    width:int
    height:int
    pixels:bytes

    def __post_init__(self):
        dimensions(self.width,self.height)
        if not isinstance(self.pixels,bytes) or len(self.pixels)!=self.width*self.height*3:
            raise ContractError("Raster RGB tidak lengkap.")

    def at(self,x,y):
        if not 0<=x<self.width or not 0<=y<self.height:
            raise IndexError("Piksel di luar raster")
        off=3*(self.width*y+x)
        return tuple(self.pixels[off:off+3])

    def receipt(self):
        return {"width":self.width,"height":self.height,"rgb_sha256":sha256(self.pixels).hexdigest()}


def blank(width,height,rgb):
    dimensions(width,height)
    return Raster(width,height,bytes(rgb)*(width*height))


def _chunk(kind,body):
    data=kind+body
    return pack(">I",len(body))+data+pack(">I",crc32(data))


def png(raster):
    stride=3*raster.width
    parts=b"".join(b"\0"+raster.pixels[index:index+stride] for index in range(0,len(raster.pixels),stride))
    header=pack(">IIBBBBB",raster.width,raster.height,8,2,0,0,0)
    return PNG+_chunk(b"IHDR",header)+_chunk(b"IDAT",compress(parts,9))+_chunk(b"IEND",b"")


def ppm(raster):
    return f"P6\n{raster.width} {raster.height}\n255\n".encode()+raster.pixels


def _paeth(left,above,corner):
    center=left+above-corner
    a,b,c=abs(center-left),abs(center-above),abs(center-corner)
    return left if a<=b and a<=c else above if b<=c else corner


def _scanlines(compressed,width,height,channels):
    stride=width*channels
    size=(stride+1)*height
    decoder=decompressobj()
    try:
        raw=decoder.decompress(compressed,size+1)
    except ZlibError as error:
        raise ContractError("Deflate raster tidak sah.") from error
    if len(raw)!=size or not decoder.eof or decoder.unused_data:
        raise ContractError("Data scanline tidak cocok dengan header.")
    previous=bytearray(stride)
    pixels=bytearray()
    for offset in range(0,size,stride+1):
        mode=raw[offset]
        line=bytearray(raw[offset+1:offset+1+stride])
        if mode not in (0,1,2,3,4):
            raise ContractError("Filter PNG belum didukung.")
        if mode:
            for index,value in enumerate(line):
                left=line[index-channels] if index>=channels else 0
                above=previous[index]
                upper_left=previous[index-channels] if index>=channels else 0
                add=left if mode==1 else above if mode==2 else (left+above)//2 if mode==3 else _paeth(left,above,upper_left)
                line[index]=(value+add)&255
        if channels==3:
            pixels.extend(line)
        elif channels==1:
            for value in line:
                pixels.extend((value,value,value))
        else:
            for index in range(0,stride,4):
                red,green,blue,opacity=line[index:index+4]
                pixels.extend((opacity*value+(255-opacity)*255+127)//255 for value in (red,green,blue))
        previous=line
    return bytes(pixels)


def _from_png(payload):
    point=len(PNG)
    parts=[]
    header=None
    closed=False
    for _ in range(1000):
        if point+12>len(payload):
            break
        length,kind=unpack_from(">I4s",payload,point)
        end=point+8+length
        if end+4>len(payload) or crc32(payload[point+4:end])!=unpack_from(">I",payload,end)[0]:
            raise ContractError("Ukuran atau CRC chunk PNG tidak sah.")
        if header is None:
            if kind!=b"IHDR" or length!=13:
                raise ContractError("IHDR belum ditemukan.")
            width,height,depth,color_type,method,filters,interlace=unpack_from(">IIBBBBB",payload,point+8)
            dimensions(width,height)
            channels={0:1,2:3,6:4}.get(color_type)
            if channels is None or depth!=8 or method or filters or interlace:
                raise ContractError("PNG hanya mendukung RGB, grayscale atau RGBA 8-bit noninterlace.")
            header=(width,height,channels)
        elif kind==b"IDAT" and not closed:
            parts.append(payload[point+8:end])
        elif kind==b"IEND" and length==0 and end+4==len(payload) and parts:
            return Raster(header[0],header[1],_scanlines(b"".join(parts),*header))
        elif kind[0]&0x20:
            closed=bool(parts)
        else:
            raise ContractError("Chunk kritis PNG belum didukung.")
        point=end+4
    raise ContractError("PNG tidak lengkap.")


def raster(payload):
    if not isinstance(payload,bytes) or len(payload)>MAX_BYTES:
        raise ContractError("Artefak raster melampaui batas.")
    if payload.startswith(PNG):
        return _from_png(payload)
    match=PPM_HEADER.match(payload)
    if match:
        width,height=map(int,match.groups())
        return Raster(width,height,payload[match.end():])
    raise ContractError("Input bukan PNG atau RGB PPM P6 yang didukung.")
