import ast
import astor
from unittest import TestCase
from textwrap import dedent

import nose.tools as nt

from ..transform import (
    transform,
    NodeTransformer
)

def test_name_rename():
    """
    Test a simple transformer to rename
    """
    class Renamer(NodeTransformer):
        def visit_Name(self, node, meta):
            node.id = node.id + '_visited'
            return node

    renamer = Renamer()
    mod = ast.parse("bob = frank")
    transform(mod, renamer)
    bob_node = mod.body[0].targets[0]
    frank_node = mod.body[0].value

    nt.assert_equals(bob_node.id, "bob_visited")
    nt.assert_equals(frank_node.id, "frank_visited")

def test_data_renamer():
    class DataRenamer(NodeTransformer):
        """
        Rewrite `bob = frank` to `data['bob'] = data['frank']`
        """
        def visit_Name(self, node, meta):
            return ast.copy_location(ast.Subscript(
                        value=ast.Name(id='data', ctx=ast.Load()),
                        slice=ast.Index(value=ast.Str(s=node.id)),
                        ctx=node.ctx
                    ), node)

    renamer = DataRenamer()
    mod = ast.parse("bob = frank")
    transform(mod, renamer)
    new_source = astor.to_source(mod)
    nt.assert_equals(new_source, "data['bob'] = data['frank']")

def test_func_renamer():
    """
    Test passing in just a function for visitor.
    """
    def visitor(node, meta):
        # like DataRenamer except just a function
        if not isinstance(node, ast.Name):
            return node

        return ast.copy_location(ast.Subscript(
                    value=ast.Name(id='data', ctx=ast.Load()),
                    slice=ast.Index(value=ast.Str(s=node.id)),
                    ctx=node.ctx
                ), node)

    mod = ast.parse("bob = frank")
    transform(mod, visitor)
    new_source = astor.to_source(mod)
    nt.assert_equals(new_source, "data['bob'] = data['frank']")
