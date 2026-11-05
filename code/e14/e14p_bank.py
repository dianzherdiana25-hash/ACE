"""Fresh cross-family source tasks and paired branching-DAG successors."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_bank import _fresh, sha, windows
from .e14m_bank import draw
from .e14o_bank import inventory as earlier_inventory
from .e14o_run import frozen
from .e14p_graph import minimum, paths

SEEDS = (143201,143202,143203,143204)


def inventory():
    used = earlier_inventory()
    bank,_,_ = frozen()
    for b in bank["blocks"]:
        for role in ("demos","probes"):
            used[b["family"]].update(sha(canonical_json(x)) for x in b[role])
    return used


def graph(rng, depth, forced=None, uniform_edges=False):
    layers, nodes = [], 0
    for i in range(depth+1):
        size = 2 if i in (3,6) else 1
        layers.append(range(nodes,nodes+size))
        nodes += size
    events = list(draw((1,2),depth-1,rng))
    if forced:
        start = rng.randrange(depth-len(forced))
        events[start:start+len(forced)] = forced
    colors = [rng.randrange(2)]
    for e in events:
        colors.append(colors[-1] ^ (e == 2))
    edges = [[a,b,colors[i] if uniform_edges or a == left.start and b == right.start else rng.randrange(2),
              rng.randint(1,15)] for i,(left,right) in enumerate(zip(layers,layers[1:])) for a in left for b in right]
    return {"nodes":nodes,"start":0,"goal":nodes-1,"edges":edges}


def render_graph(rng, used, hit=None, exclude=(), multiple=False, depth_range=(10,12)):
    for _ in range(1024):
        raw = graph(rng,rng.randint(*depth_range),hit,multiple)
        digest = sha(canonical_json(raw))
        routes = paths(raw)
        if digest in used or any(minimum(routes,w) is not None for w in exclude):
            continue
        if hit is not None:
            costs = {cost for events,cost in routes if hit in windows(events,len(hit))}
            if not costs or multiple and len(costs) < 2:
                continue
        used.add(digest)
        return raw
    raise ValueError("could not render fresh branching graph")


def build():
    used = inventory()
    motifs,source,target = map(random.Random,SEEDS[:3])
    blocks = []
    for length in (7,8,9):
        options = [w for w in product((0,2),repeat=length) if len(set(w))>1]
        for slot,word in enumerate(motifs.sample(options,4)):
            motif = tuple(1 if x == 0 else 2 for x in word)
            shift = tuple(3-x for x in motif)
            witness = draw((0,1,2),2,source) + word + draw((0,1,2),10-length,source)
            negative = sorted(windows(witness,6))
            negative += [draw((0,1,2),5,source) for _ in range(32-len(negative))]
            evidence = list(dict.fromkeys(x for x in (witness,word,word[:-1],word[1:]) if x not in negative))
            demos = [render_graph(target,used["G"],exclude=(motif,shift)) for _ in range(4)]
            calibration = render_graph(target,used["G"],hit=motif,exclude=(shift,))
            neutral = render_graph(target,used["G"],exclude=(motif,shift)) if slot < 2 else None
            probes = [render_graph(target,used["G"],hit=w,exclude=(other,),multiple=i==0)
                      for w,other in ((motif,shift),(shift,motif)) for i in range(4)]
            target.shuffle(probes)
            blocks.append({"slot":slot,"source_word":word,
                           "source_demos":[_fresh("S",x,source,used["S"]) for x in negative],
                           "source_observations":[_fresh("S",x,source,used["S"]) for x in evidence],
                           "target_demos":demos,"calibration":calibration,"neutral":neutral,"probes":probes})
    return {"version":1,"seeds":SEEDS,"blocks":blocks}
