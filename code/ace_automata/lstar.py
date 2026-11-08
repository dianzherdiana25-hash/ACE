"""Angluin's L* Active Automata Learning Algorithm.

Learns the minimal Deterministic Finite Automaton (DFA) representing any regular
language using Membership Queries (MQ) and Equivalence Queries (EQ).

Converts discovered DFAs directly into:
1. Pure Python executable functions.
2. ACE R1 Automaton signatures for seamless integration into compositional.Program.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple


@dataclass
class DFA:
    states: List[int]
    alphabet: Tuple[str, ...]
    transitions: Dict[Tuple[int, str], int]
    initial_state: int
    accepting_states: Set[int]

    def run(self, word: str) -> bool:
        """Executes the DFA on a string word."""
        state = self.initial_state
        for char in word:
            if char not in self.alphabet:
                return False
            key = (state, char)
            if key not in self.transitions:
                return False
            state = self.transitions[key]
        return state in self.accepting_states

    def to_r1_signature(self) -> List[List[object]]:
        """Converts to ACE primitive_discovery.Automaton signature format:
        [[is_accepting, [[char, next_state], ...]], ...]
        """
        signature = []
        for s in self.states:
            is_acc = (s in self.accepting_states)
            edges = []
            for char in sorted(self.alphabet):
                if (s, char) in self.transitions:
                    edges.append([char, self.transitions[(s, char)]])
            signature.append([is_acc, edges])
        return signature

    def to_python_code(self, func_name: str = "dfa_predict") -> str:
        """Generates self-contained pure Python function."""
        lines = [
            f"def {func_name}(word: str) -> bool:",
            "    state = 0",
            f"    transitions = {repr(dict(self.transitions))}",
            f"    accepting = {repr(set(self.accepting_states))}",
            "    for char in word:",
            "        key = (state, char)",
            "        if key not in transitions:",
            "            return False",
            "        state = transitions[key]",
            "    return state in accepting",
        ]
        return "\n".join(lines) + "\n"


class ObservationTable:
    """Observation table (S, E, T) maintaining active experiment records."""

    def __init__(self, alphabet: Tuple[str, ...], teacher: Callable[[str], bool]):
        self.alphabet = alphabet
        self.teacher = teacher
        self.S: List[str] = [""]  # Initial state prefix (epsilon)
        self.E: List[str] = [""]  # Initial test suffix (epsilon)
        self.table: Dict[str, Dict[str, bool]] = {}
        self._update_table()

    def _update_table(self):
        """Ensures all s in S and s.a in S.Sigma have entries for all e in E."""
        keys = list(self.S)
        for s in self.S:
            for a in self.alphabet:
                sa = s + a
                if sa not in keys:
                    keys.append(sa)

        for k in keys:
            if k not in self.table:
                self.table[k] = {}
            for e in self.E:
                if e not in self.table[k]:
                    self.table[k][e] = self.teacher(k + e)

    def row(self, s: str) -> Tuple[bool, ...]:
        return tuple(self.table[s][e] for e in self.E)

    def is_closed(self) -> Tuple[bool, Optional[str]]:
        """A table is closed if for every t in S.Sigma, row(t) == row(s) for some s in S."""
        s_rows = {self.row(s) for s in self.S}
        for s in self.S:
            for a in self.alphabet:
                sa = s + a
                if self.row(sa) not in s_rows:
                    return False, sa
        return True, None

    def is_consistent(self) -> Tuple[bool, Optional[Tuple[str, str, str]]]:
        """A table is consistent if whenever row(s1) == row(s2), then for all a,
        row(s1.a) == row(s2.a).
        """
        for i, s1 in enumerate(self.S):
            for s2 in self.S[i + 1:]:
                if self.row(s1) == self.row(s2):
                    for a in self.alphabet:
                        for idx, e in enumerate(self.E):
                            if self.table[s1 + a][e] != self.table[s2 + a][e]:
                                return False, (a, e, s1, s2)
        return True, None

    def close(self):
        closed, sa = self.is_closed()
        if not closed and sa is not None:
            if sa not in self.S:
                self.S.append(sa)
                self._update_table()
                return True
        return False

    def make_consistent(self):
        consistent, witness = self.is_consistent()
        if not consistent and witness is not None:
            a, e, _, _ = witness
            new_e = a + e
            if new_e not in self.E:
                self.E.append(new_e)
                self._update_table()
                return True
        return False

    def build_dfa(self) -> DFA:
        """Constructs conjectured DFA from closed and consistent observation table."""
        # Map unique row vectors to states
        unique_rows: List[Tuple[bool, ...]] = []
        state_map: Dict[Tuple[bool, ...], int] = {}
        s_to_state: Dict[str, int] = {}

        for s in self.S:
            r = self.row(s)
            if r not in state_map:
                state_idx = len(unique_rows)
                unique_rows.append(r)
                state_map[r] = state_idx
            s_to_state[s] = state_map[r]

        states = list(range(len(unique_rows)))
        initial_state = s_to_state[""]
        accepting_states = set()

        for s in self.S:
            if self.table[s][""]:  # Empty suffix membership
                accepting_states.add(s_to_state[s])

        transitions: Dict[Tuple[int, str], int] = {}
        for s in self.S:
            s_idx = s_to_state[s]
            for a in self.alphabet:
                sa = s + a
                target_row = self.row(sa)
                if target_row in state_map:
                    target_idx = state_map[target_row]
                    transitions[(s_idx, a)] = target_idx

        return DFA(
            states=states,
            alphabet=self.alphabet,
            transitions=transitions,
            initial_state=initial_state,
            accepting_states=accepting_states,
        )


class LStarLearner:
    """Active Automata Learner managing the L* learning loop."""

    def __init__(self, alphabet: Tuple[str, ...] = ("a", "b")):
        self.alphabet = alphabet

    def learn(
        self,
        teacher: Callable[[str], bool],
        training_samples: Optional[List[Tuple[str, bool]]] = None,
        max_states: int = 16,
        max_iterations: int = 50,
    ) -> DFA:
        """Learns the minimal DFA using teacher queries and training samples."""
        table = ObservationTable(self.alphabet, teacher)

        for _ in range(max_iterations):
            # 1. Close and make consistent
            progress = True
            while progress:
                progress = False
                if table.close():
                    progress = True
                if table.make_consistent():
                    progress = True

            # 2. Build conjectured DFA
            conjectured_dfa = table.build_dfa()
            if len(conjectured_dfa.states) >= max_states:
                return conjectured_dfa

            # 3. Equivalence query: test against training samples
            counterexample = None
            if training_samples:
                for word, expected_label in training_samples:
                    if conjectured_dfa.run(word) != expected_label:
                        counterexample = word
                        break

            if counterexample is None:
                # All training samples correctly classified!
                return conjectured_dfa

            # 4. Process counterexample: add all prefixes to S or suffixes to E
            for i in range(1, len(counterexample) + 1):
                suffix = counterexample[i:]
                if suffix not in table.E:
                    table.E.append(suffix)
            prefix = ""
            for char in counterexample:
                prefix += char
                if prefix not in table.S:
                    table.S.append(prefix)
            table._update_table()

        return table.build_dfa()
