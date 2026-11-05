"""Evidence-directed bounded research-budget reallocation across two tracks.

Runs a pilot on both in-grammar and mixed-grammar problems. Allocates the
remaining finite policy trials to the track with greater *validation* gain;
the other is explicitly suspended, with its checkpoint preserved. Heldout
results are not used for allocation or retuning. No background scheduling.
"""
from __future__ import annotations
import json
from pathlib import Path
from .engine import ResearchEngine,ResearchIntegrityError,Policy,canonical,digest
from .operators import OperatorAdapter

TRACKS=(('in_family',0),('mixed_grammar',2))


def run_portfolio(root,*,pilot_trials=8,total_trials=12):
    if type(pilot_trials) is not int or type(total_trials) is not int or not 1<=pilot_trials<total_trials<=12:
        raise ResearchIntegrityError('invalid portfolio budget')
    path=Path(root)
    if path.is_symlink():raise ResearchIntegrityError('unsafe portfolio root')
    path.mkdir(parents=True,exist_ok=True)
    engines={name:ResearchEngine(path/name,OperatorAdapter(outsiders_per_split=outsiders),
                                  max_cycles=total_trials,patience=total_trials)
             for name,outsiders in TRACKS}
    record_file=path/'allocation.json'
    if record_file.exists():
        raw=record_file.read_bytes()
        try:row=json.loads(raw)
        except ValueError as exc:raise ResearchIntegrityError('invalid allocation') from exc
        if canonical(row)+b'\n'!=raw or type(row) is not dict or set(row)!={'allocation','sha256'} or digest(row['allocation'])!=row['sha256']:
            raise ResearchIntegrityError('allocation corruption')
        allocation=row['allocation']
        if allocation['pilot_trials']!=pilot_trials or allocation['total_trials']!=total_trials:
            raise ResearchIntegrityError('portfolio policy changed')
        selected=allocation['selected']
        if selected is not None and selected not in engines:
            raise ResearchIntegrityError('unknown allocated track')
        if set(allocation['gains'])!=set(engines) or set(allocation['pilot_heads'])!=set(engines):
            raise ResearchIntegrityError('invalid allocation track set')
        gains={}
        for name,engine in engines.items():
            # Reconstruct the precise eight-trial pilot state even after the
            # selected research track has continued to completion.
            checkpoint_index=pilot_trials*2
            if len(engine.ledger.events)<=checkpoint_index or engine.ledger.events[checkpoint_index]['kind']!='decision':
                raise ResearchIntegrityError('pilot checkpoint absent')
            if engine.ledger.events[checkpoint_index]['sha256']!=allocation['pilot_heads'][name]:
                raise ResearchIntegrityError('pilot checkpoint changed')
            if name!=selected and len(engine.ledger.events)!=checkpoint_index+1:
                raise ResearchIntegrityError('suspended track mutated')
            champion=Policy(**engine.ledger.events[checkpoint_index]['payload']['champion'])
            base=engine.adapter.evaluate(Policy('fixed',1,1),'validation')['utility_units']
            gains[name]=engine.adapter.evaluate(champion,'validation')['utility_units']-base
        expected=max(gains,key=lambda n:(gains[n],-list(engines).index(n)))
        if gains[expected]<=0:expected=None
        if allocation['gains']!=gains or expected!=selected:
            raise ResearchIntegrityError('allocation not supported by evidence')
    else:
        gains={};heads={}
        for name,engine in engines.items():
            status=engine.run(stop_after_trials=pilot_trials)
            if status['status']!='PAUSED_CHECKPOINT':
                raise ResearchIntegrityError('pilot was not checkpointed')
            champion=Policy(**status['champion'])
            current=engine.adapter.evaluate(champion,'validation')
            baseline=engine.adapter.evaluate(Policy('fixed',1,1),'validation')
            gains[name]=current['utility_units']-baseline['utility_units']
            heads[name]=engine.ledger.events[-1]['sha256']
        # Explicit stop if *both* tracks are unproductive; no extra labels spent.
        selected=max(gains,key=lambda name:(gains[name],-list(engines).index(name)))
        if gains[selected]<=0:
            selected=None
        allocation={'pilot_trials':pilot_trials,'total_trials':total_trials,
                    'gains':gains,'pilot_heads':heads,'selected':selected,
                    'reason':'validation_gain_reallocation' if selected else 'all_tracks_paused_no_gain',
                    'holdout_used_for_allocation':False}
        data=canonical({'allocation':allocation,'sha256':digest(allocation)})+b'\n'
        with record_file.open('xb') as f:
            f.write(data);f.flush();__import__('os').fsync(f.fileno())
    if selected:
        final=engines[selected].run()
    else:final=None
    return {'allocation':allocation,'selected_result':final,
            'suspended_tracks':[n for n in engines if n!=selected],
            'scientific_decision':'NOT_ASSESSED'}
