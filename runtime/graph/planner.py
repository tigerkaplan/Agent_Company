"""Deterministic splitter for explicitly contracted task units.

Provider planner proposals pass the same constructor and parent admission checks;
neither a proposal nor this splitter authorizes any node.
"""
from copy import deepcopy
from runtime.graph.models import plan


class GraphPlanner:
    @staticmethod
    def build(nodes, *, edges=(), max_parallel=1, max_handoffs=0):
        return plan({"schema_version": 1, "nodes": deepcopy(list(nodes)),
                     "edges": deepcopy(list(edges)), "max_parallel": max_parallel,
                     "max_handoffs": max_handoffs})

    @staticmethod
    def split(units, *, merge=None, max_parallel=1):
        """Fan out explicit units and optionally fan in their accepted results."""
        nodes = deepcopy(list(units))
        if merge is not None:
            sink = deepcopy(merge)
            sink["depends_on"] = [node["node_id"] for node in nodes]
            nodes.append(sink)
        return GraphPlanner.build(nodes, max_parallel=max_parallel)
