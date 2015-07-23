import ast
import inspect
import types
import ctypes
from itertools import zip_longest
from collections import OrderedDict
from textwrap import dedent

import pandas as pd
import numpy as np

from .repr import ast_source, ast_repr, ast_print, indented
from .eval import _exec, _eval
from .common import _convert_to_expression, iter_fields, quick_parse, get_source
from .graph import graph_walk
from .transform import NodeTransformer, transform, coroutine
from .function import func_rewrite, create_function

def reload_locals(frame):
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(1))

def replace_node(parent, field_name, field_index, node):
    if field_index is None:
        setattr(parent, field_name, node)
    else:
        getattr(parent, field_name)[field_index] = node

def delete_node(parent, field_name, field_index, node):
    if field_index is None:
        old_node = getattr(parent, field_name)
        delattr(parent, field_name)
    else:
        old_node = getattr(parent, field_name).pop(field_index)
    assert node is old_node, "Existing node is not node we're trying to delete"

def is_load_name(node):
    """ is node a Name(ctx=Load()) variable? """
    if not isinstance(node, ast.Name):
        return False

    if isinstance(node.ctx, ast.Load):
        return True

def load_names(code):
    names = (n.id for n in filter(is_load_name, ast.walk(code)))
    return list(OrderedDict.fromkeys(names))

def field_iter(node):
    """ yield field, field_name, field_index """
    for field_name, field in ast.iter_fields(node):
        if isinstance(field, list):
            for i, item in enumerate(field):
                yield item, field_name, i
            continue

        item = field
        yield item, field_name, None


def ast_field_equal(node1, node2):
    """
    Check that fields are equal.

    Note: If the value of the field is an ast.AST and are of equal type,
    we don't check any deeper.
    """
    # check fields
    field_gen1 = field_iter(node1)
    field_gen2 = field_iter(node2)

    for field_item1, field_item2 in zip_longest(field_gen1, field_gen2):
        # unequal length
        if field_item1 is None or field_item2 is None:
            return False

        field_value1 = field_item1[0]
        field_value2 = field_item2[0]

        field_name1 = field_item1[1]
        field_name2 = field_item2[1]

        field_index1 = field_item1[2]
        field_index2 = field_item2[2]

        if type(field_value1) != type(field_value2):
            return False

        if field_name1 != field_name2:
            return False

        if field_index1 != field_index2:
            return False

        # note, we don't do equality check on AST nodes since ast.walk
        # will hit it.
        if isinstance(field_value1, ast.AST):
            continue

        # this should largely be strings and numerics, afaik
        assert isinstance(field_value1, (str, int, float, type(None)))
        if field_value1 != field_value2:
            return False

    return True

def ast_equal(code1, code2, check_line_col=False, ignore_var_names=False):
    """
    Checks whether ast nodes are equivalent recursively.

    By default does not check line number or col offset
    """
    gen1 = ast.walk(code1)
    gen2 = ast.walk(code2)

    for node1, node2 in zip_longest(gen1, gen2):
        # unequal length
        if node1 is None or node2 is None:
            return False

        if type(node1) != type(node2):
            return False

        # ignore the names of load name variables.
        if ignore_var_names and is_load_name(node1) and is_load_name(node2):
            continue

        if not ast_field_equal(node1, node2):
            return False

        if check_line_col and hasattr(node1, 'lineno'):
            if node1.lineno != node2.lineno:
                return False
            if node1.col_offset != node2.col_offset:
                return False

    return True

def ast_contains(code, fragment, ignore_var_names=False):
    """ tests whether fragment is a child within code. """
    expr = _convert_to_expression(fragment)

    if expr is None:
        raise Exception("Fragment must be an expression")

    # unwrap 
    fragment = expr.body

    for item in graph_walk(code):
        node = item['node']
        if ast_equal(node, fragment, ignore_var_names=ignore_var_names):
            yield item

    return False

def _value_equal(left, right):
    # TODO move this, make it use dispatch? not sure if there is a general value
    # equality function out there
    if isinstance(left, pd.core.generic.NDFrame):
        return left.equals(right)

    if isinstance(left, np.ndarray):
        return np.all(left == right)

    try:
        return left == right
    except:
        return False

def code_context_subset(code, context, key_code, key_context,
                    ignore_var_names=False):
    """
    Try to find subset match and returns a node context dict as returned
    by ast_contains.

    Returns: dict from ast_contains
        {
            node : ast.AST,
            parent : ast.AST,
            field_name : str,
            field_index : int or None,
            current_depth : int
        }
    """
    # check expresion
    matches = ast_contains(code, key_code,
                                    ignore_var_names=ignore_var_names)
    for matched_item in matches:
        matched = matched_item['node']
        if code_context_match(matched, context, key_code, key_context):
            yield matched_item

def code_context_match(matched, matched_context, key_code, key_context):

    # at this point the load names should be equal for each code
    # fragment. they are equal by position. load_names does not
    # have a set order, but a stable order per same tree structure.
    key_load_names = load_names(key_code)
    matched_load_names = load_names(matched)
    if len(key_load_names) != len(matched_load_names):
        return

    # check context.
    for pk, fk in zip(matched_load_names, key_load_names):
        pv = matched_context[pk]
        fv = key_context[fk]
        if not _value_equal(pv, fv):
            return

    return True

def generate_getter_var(manifest, value, prefix="_AST"):
    """
    Generate a Name node that has an obscure name to prevent collisions
    and points to the value
    """
    var_name = '_{prefix}_{id}'.format(prefix=prefix, id=abs(hash(manifest)))
    getter = ast.Name(id=var_name, ctx=ast.Load())
    ns_update = {var_name: value}
    return ast.fix_missing_locations(getter), ns_update

def generate_getter_lazy(manifest, prefix="_AST"):
    """
    Generates a manifest.get_obj() call. Uses obscure variable naming
    """
    var_name = '_{prefix}_{id}'.format(prefix=prefix, id=abs(hash(manifest)))
    func = ast.Attribute(
        value=ast.Name(id=var_name, ctx=ast.Load()),
        attr="get_obj", ctx=ast.Load()
    )
    args = []
    keywords = []

    getter = ast.Call(func=func, args=args, keywords=keywords,
                        starargs=None, kwargs=None)
    ns_update = {var_name: manifest}
    return ast.fix_missing_locations(getter), ns_update


"""
Structural matching on ast with sentinels for wildcard matching.

template = '<any>'._any_()"
test = ast.parse('"hello {bob}".capture()')
for node in ast.walk(test):
    if matcher.match(node):
        node.kwargs = quick_parse("locals()").value
        node.func.attr = 'format'
"""
_missing = object()
class Matcher:
    def __init__(self, template):
        if isinstance(template, str):
            template = quick_parse(template)
            if isinstance(template, ast.Expr):
                template = template.value
        self.template = template

    def match(self, other, node=_missing):
        if node is _missing:
            node = self.template

        method = 'match_' + node.__class__.__name__
        matcher = getattr(self, method, self.generic_match)
        node_item = matcher(other, node)
        return node_item

    def generic_match(self, other, node):
        if type(node) != type(other):
            return False

        # match scalars via equality
        if not isinstance(node, ast.AST):
            return node == other

        return self.match_children(other, node)

    def match_children(self, other, node, skip=()):
        if not isinstance(node, ast.AST):
            return True

        for item, field_name, field_index in iter_fields(node):
            # we still try to grab other's child to make sure we have the same
            # structure.
            try:
                if field_index is None:
                    other_child = getattr(other, field_name)
                else:
                    other_child = getattr(other, field_name)[field_index]
            except (AttributeError, KeyError):
                return False

            if field_name in skip:
                continue

            # children did not match, short circuit out of here
            if not self.match(other_child, item):
                return False
        return True

    def match_Str(self, other, node):
        if node.s == '<any>':
            return True
        return node.s == other.s

    def match_Attribute(self, other, node):
        skip = ()
        if node.attr == '_any_':
            skip = ('attr')

        return self.match_children(other, node, skip=skip)

    def match_With(self, other, node):
        skip = ()
        body = node.body
        line = body[0]
        if len(body) == 1 and isinstance(line, ast.Expr) \
        and isinstance(line.value, ast.Name) and line.value.id == '_any_':
            skip = ('body')

        return self.match_children(other, node, skip=skip)
