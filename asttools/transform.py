import ast
import astor
from ast import AST
from textwrap import dedent
from .graph import graph_walk, NodeLocation


class NodeTransformer:
    def visit(self, node, meta):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        node_item = visitor(node, meta)
        return node_item

    def generic_visit(self, node, meta):
        return node


def transform(root, visitor):
    """
    Largely taken from the ast source. Works a bit differently because
    it depends on the graph_walk which returns items leaf first and then to
    root.
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
                    done_node = done.get(value)
                    if done_node:
                        new_values.append(done_node)
                old_value[:] = new_values

            elif isinstance(old_value, ast.AST):
                done_node = done.get(old_value)
                if done_node is None:
                    delattr(node, field_name)
                else:
                    setattr(node, field_name, done_node)

        done[node] = new_node
    return root
