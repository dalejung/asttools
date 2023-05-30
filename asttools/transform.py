import ast
from ast import AST
from textwrap import dedent
from .graph import graph_walk, NodeLocation

_missing = object()

class NodeTransformer:
    def visit(self, node, meta):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        node_item = visitor(node, meta)
        return node_item

    def generic_visit(self, node, meta):
        return node

class coroutine:
    """
    @coroutine.wrap
    def handle():
        node, meta = yield
        while True:
            node, meta = yield node
        return node
    """
    def __init__(self, func, *args, **kwargs):
        self.coro = func(*args, **kwargs)
        next(self.coro) # prime coroutine

    @classmethod
    def wrap(cls, func):
        def _factory(*args, **kwargs):
            return cls(func, *args, **kwargs)
        return _factory

    def __call__(self, node, meta):
        return self.coro.send((node, meta))

def transform(root, visitor):
    """
    Largely taken from the ast source. Works a bit differently because
    it depends on the graph_walk which returns items leaf first and then to
    root.

    Note that if we come across an unknown node (_missing), we assume that
    the fields were mutated in the node visitor and we leave them alone.

    This would occur if you changed the ast.Assign.value when handling the
    ast.Assign node.
    """
    gen = graph_walk(root)
    done = {}

    if isinstance(visitor, NodeTransformer):
        visitor = visitor.visit

    for item in gen:
        node = item['node']
        new_node = visitor(node, item)

        for field_name, old_value in ast.iter_fields(node):
            old_value = getattr(node, field_name, None)

            if isinstance(old_value, list):
                new_values = []
                for field_index, value in enumerate(old_value):
                    done_node = done.get(value, _missing)
                    if done_node is _missing: # fields were mutated in visitor
                        new_values.append(value)
                    elif done_node:
                        new_values.append(done_node)
                old_value[:] = new_values

            elif isinstance(old_value, ast.AST):

                done_node = done.get(old_value, _missing)
                if done_node is _missing: # fields were mutated in visitor
                    continue

                if done_node is None:
                    delattr(node, field_name)
                else:
                    setattr(node, field_name, done_node)

        done[node] = new_node
    return root
