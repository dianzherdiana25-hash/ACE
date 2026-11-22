"""Ubah teks Indonesia berbatas menjadi suara sintetis lewat aturan formant.

Aturan grafem memakai inventaris eksplisit, kepanjangan bilangan,
durasi dan jeda. Eksitasi harmonik serta noise berseed menghasilkan
WAV yang dapat direproduksi. Keterpahaman narasi memerlukan eval ucapan.
"""
import argparse
from hashlib import sha256
from math import exp,pi,sin
from pathlib import Path
from random import Random
import re
import sys
from unicodedata import normalize

from ._audio import Audio,clamp,sample_rate,wav
from ._contracts import ContractError,canonical,checked,decode,integer,read,schema,text


VOWELS={"a":((790,1250,2700),125),"i":((305,2220,2980),115),"u":((360,900,2350),122),
        "e":((480,1960,2600),102),"o":((520,900,2500),120)}
NASALS={"m":(270,1350,2300),"n":(300,1650,2480),"ng":(285,1080,2470),"ny":(335,2100,2750)}
LIQUIDS={"l":(410,1430,2600),"r":(430,1540,2380),"w":(360,830,2350),"y":(330,2180,2800)}
STOPS={"p":False,"b":True,"t":False,"d":True,"k":False,"g":True,"c":False,"j":True}
FRICATIVES={"f":False,"v":True,"s":False,"z":True,"h":False,"kh":False,"sy":False}
PAUSES={",":145,";":190,":":190,".":280,"!":280,"?":310,"/":120,"-":40}
DIGRAPHS={"ng","ny","kh","sy"}
WORD=re.compile(r"[a-z]+|[0-9]+|[.,;:!?/\-]")
NUMBERS=("nol","satu","dua","tiga","empat","lima","enam","tujuh","delapan","sembilan")


def _number(value):
    if value<10:
        return NUMBERS[value]
    if value==10:
        return "sepuluh"
    if value==11:
        return "sebelas"
    if value<20:
        return NUMBERS[value-10]+" belas"
    if value<100:
        head,tail=divmod(value,10)
        prefix=NUMBERS[head]+" puluh"
    elif value<1000:
        head,tail=divmod(value,100)
        prefix="seratus" if head==1 else NUMBERS[head]+" ratus"
    else:
        head,tail=divmod(value,1000)
        prefix="seribu" if head==1 else NUMBERS[head]+" ribu"
    return prefix+(" "+_number(tail) if tail else "")


def _word(orthography):
    result=[]
    offset=0
    while offset<len(orthography):
        pair=orthography[offset:offset+2]
        if pair in DIGRAPHS:
            result.append(pair)
            offset+=2
        else:
            unit=orthography[offset]
            if unit=="x":
                result.extend(("k","s"))
            else:
                result.append("k" if unit=="q" else unit)
            offset+=1
    return result


def phonemes(sentence):
    raw=text(sentence,"Narasi",720)
    supplied="".join(char for char in normalize("NFKD",raw).casefold() if not (
        0x0300<=ord(char)<=0x036F))
    if any(not (c.isascii() and (c.isalpha() or c.isdigit() or c.isspace() or c in PAUSES)) for c in supplied):
        raise ContractError("Grafem narasi di luar inventaris.")
    tokens=WORD.findall(supplied)
    output=[]
    for token in tokens:
        if token in PAUSES:
            if output and output[-1][0]=="gap":
                output.pop()
            output.append(("gap",PAUSES[token]))
            continue
        if len(token)>48 or token.isdigit() and len(token)>4:
            raise ContractError("Kata atau bilangan terlalu panjang.")
        chunks=_number(int(token)).split() if token.isdigit() else [token]
        for chunk in chunks:
            for unit in _word(chunk):
                if unit in VOWELS:
                    span=VOWELS[unit][1]
                elif unit in NASALS or unit in LIQUIDS:
                    span=76
                elif unit in STOPS:
                    span=57
                elif unit in FRICATIVES:
                    span=89
                else:
                    raise ContractError("Grafem tidak dapat dilafalkan.")
                output.append((unit,span))
            output.append(("gap",36))
    if output and output[-1]==("gap",36):
        output.pop()
    if not 1<=len(output)<=440 or all(unit=="gap" for unit,_ in output):
        raise ContractError("Narasi kosong atau terlalu banyak fonem.")
    return output


def _harmonics(pitch,formants,spreads,rate):
    result=[]
    for harmonic in range(1,min(25,int((rate/2-50)/pitch))+1):
        hz=harmonic*pitch
        gain=sum(weight*exp(-((hz-center)/width)**2/2) for center,width,weight in
                 zip(formants,spreads,(1.0,0.45,0.19),strict=True))
        result.append((2*pi*hz/rate,gain/harmonic**0.65))
    total=sum(weight for _,weight in result) or 1.0
    return [(frequency,weight/total) for frequency,weight in result]


def _envelope(index,length,rate):
    attack=max(1,rate//115)
    tail=max(1,rate//85)
    return min(1,(index+1)/attack,(length-index)/tail)


def _articulate(unit,frames,rate,pitch,gain,seed):
    if unit=="gap":
        return (0,)*frames
    voice=[]
    volume=1.0
    if unit in VOWELS:
        voice=_harmonics(pitch,VOWELS[unit][0],(139,205,260),rate)
    elif unit in NASALS:
        voice=_harmonics(pitch,NASALS[unit],(100,190,220),rate)
        volume=0.64
    elif unit in LIQUIDS:
        voice=_harmonics(pitch,LIQUIDS[unit],(150,230,275),rate)
        volume=0.77
    elif STOPS.get(unit) or FRICATIVES.get(unit):
        voice=_harmonics(pitch,(320,1200,2300),(108,230,280),rate)
        volume=0.45
    noise=Random(seed)
    previous=0.0
    result=[]
    for index in range(frames):
        periodic=sum(weight*sin(frequency*index) for frequency,weight in voice)
        if unit in STOPS or unit in FRICATIVES:
            raw=noise.uniform(-1,1)
            filtered=(raw-previous)*0.5
            previous=raw
            if unit in STOPS:
                start=frames*42//100
                amplitude=max(0,1-(index-start)/max(1,frames//4)) if index>=start else 0
            else:
                amplitude=0.42 if unit in ("s","sy","z") else 0.30
            periodic=periodic*0.42+filtered*amplitude
        elif unit=="r":
            periodic*=(0.7+0.3*sin(2*pi*23*index/rate))
        envelope=_envelope(index,frames,rate)
        result.append(clamp(round(periodic*gain*volume*envelope)))
    return tuple(result)


def synthesize(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.media.voice-plan.v1",("source_ref","text","language","rate","pitch_hz","speed_milli","peak","seed"))
    source=text(plan["source_ref"],"Rujukan naskah")
    if plan["language"]!="id":
        raise ContractError("Aturan narasi hanya mencakup bahasa Indonesia.")
    rate=sample_rate(plan["rate"])
    pitch=integer(plan["pitch_hz"],"Pitch",85,260)
    speed=integer(plan["speed_milli"],"Laju",650,1650)
    gain=integer(plan["peak"],"Amplitudo",100,28000)
    seed=integer(plan["seed"],"Seed",0,2**63-1)
    sequence=phonemes(plan["text"])
    lengths=[max(1,(rate*span+speed//2)//speed) for _,span in sequence]
    if sum(lengths)>rate*45:
        raise ContractError("Durasi sintesis melebihi 45 detik.")
    narration=[]
    steps=[]
    for index,((unit,_),span) in enumerate(zip(sequence,lengths,strict=True)):
        offset=len(narration)
        variable=max(80,min(265,pitch+3-(index%9)))
        narration.extend(_articulate(unit,span,rate,variable,gain,seed+index))
        steps.append({"phoneme":unit,"first_frame":offset,"last_frame_exclusive":offset+span})
    audio=Audio(rate,1,tuple(narration))
    output=wav(audio)
    return output,{"schema":"ace.media.voice-receipt.v1","plan_sha256":expected,"source_ref":source,"language":"id",
                   "renderer":"rule_based_formants","source_text_sha256":sha256(plan["text"].encode()).hexdigest(),
                   "wav_sha256":sha256(output).hexdigest(),"phonemes":steps,**audio.receipt()}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        audio,report=synthesize(decode(read(args.plan)),args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(audio)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
