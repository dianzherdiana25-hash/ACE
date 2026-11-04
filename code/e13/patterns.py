"""Compile bounded event patterns to typed machine ASTs."""


def pattern_ast(family, pattern):
    """Build a typed prefix automaton, with overlap on the symbolic side."""
    size = len(pattern)
    table = []
    for state in range(size):
        row = []
        for event in range(3):
            suffix = pattern[:state] + (event,)
            match = suffix == pattern
            candidates = range(min(len(suffix), size - 1), 0, -1)
            successor = next((n for n in candidates if suffix[-n:] == pattern[:n]), 0)
            row.append([successor, int(match)] if family == "S" else size if match else successor)
        table.append(row)
    if family == "S":
        return {"family": "S", "ast": {"op": "symbol_machine", "table": table}}
    return {"family": "G", "ast": {"op": "graph_machine", "table": table + [[size] * 3],
                                    "accept": [0] * size + [1]}}
