"""Design one weighted query to discriminate an existing four-word version space."""

import random
import resource
import sys
from collections import Counter
from itertools import combinations

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14p_worker import graph_features

MODES = ("chain", "packed", "random")
CAP = 8


def build_graph(words, prefix):
    """Share prefix edges, then give each distinct remaining path a distinct toll."""
    common_edges = prefix+1 if prefix else 0
    depth = 8
    tail = depth-common_edges
    start = common_edges
    goal = start+len(words)*(tail-1)+1
    edges = []
    if common_edges:
        color = 0
        for i in range(common_edges):
            if i:
                color ^= words[0][i-1] == 2
            edges.append([i,i+1,color,1])
    for branch,word in enumerate(words):
        colors = [0]
        for event in word:
            colors.append(colors[-1] ^ (event==2))
        via = [start,*range(start+1+branch*(tail-1),start+1+(branch+1)*(tail-1)),goal]
        for i,(a,b) in enumerate(zip(via,via[1:])):
            edges.append([a,b,colors[common_edges+i],1+4*branch if b==goal else 1])
    return {"nodes":goal+1,"start":0,"goal":goal,"edges":edges}


def propose(mode, words, seed):
    if mode == "chain":
        return [build_graph((word,),0) for word in words]
    if mode == "packed":
        triples = [build_graph(group,3) for group in combinations(words,3) if len({w[:3] for w in group})==1]
        pairs = [build_graph(group,0) for group in combinations(words,2)]
        return (triples+pairs)[:CAP]
    rng = random.Random(seed)
    result = []
    for _ in range(CAP):
        prefix = tuple(rng.choice((1,2)) for _ in range(3))
        word_set = [prefix+suffix for suffix in rng.sample(list(product_tails()),3)]
        result.append(build_graph(word_set,3))
    return result


def product_tails():
    for i in range(16):
        yield tuple(1+(i>>j & 1) for j in range(4))


def solve(raw):
    packet = read_json(raw,65_536)
    require_fields(packet,"words","mode","seed")
    mode = packet["mode"]
    if mode not in MODES:
        raise ContractError("invalid query strategy")
    seed = integer(packet["seed"],0,2**32-1)
    words = [tuple(integer(x,1,2) for x in array(w,7,7)) for w in array(packet["words"],4,4)]
    if len(set(words))!=4:
        raise ContractError("duplicate candidate word")
    offers = []
    for graph in propose(mode,words,seed):
        features = graph_features(graph)
        predicted = [features.get(w) for w in words]
        offers.append({"graph":graph,"predicted":predicted})
    counts = [Counter(o["predicted"]) for o in offers]
    i = min(range(len(offers)),key=lambda j:(-sum(n==1 for n in counts[j].values()),
                                           sum(n*n for n in counts[j].values()),j))
    return {"offers":offers,"choice":i if len(counts[i])>1 else None}


def main():
    result = solve(sys.stdin.buffer.read(65_537))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_us=round(1_000_000*(usage.ru_utime+usage.ru_stime)),rss_kib=usage.ru_maxrss)
    sys.stdout.buffer.write(canonical_json(result))
