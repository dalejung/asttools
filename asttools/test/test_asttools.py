import ast
from textwrap import dedent

# TODO
# the pandas/numpy tests were written since that what was I originally
# testing on. They should optional so tests don't depend on them
import pandas as pd
import numpy as np

import collections
import pytest

from asttools import (
    _eval,
    _exec,
    _convert_to_expression,
    ast_source,
    ast_equal,
    ast_contains,
    code_context_subset,
    generate_getter_var,
    generate_getter_lazy,
    graph_walk
)

from ..graph import NodeLocation


class TestEval:
    def test_exec(self):
        source = """
        d = 123
        """
        code = ast.parse(dedent(source))
        ns = {}
        out = _exec(code.body[0], ns)
        assert ns['d'] == 123
        assert out is None

        # eval versio of exec
        source = """
        123
        """
        code = ast.parse(dedent(source))
        ns = {}
        out = _exec(code.body[0], ns)
        assert out == 123

    def test_eval(self):
        """
        _eval should only run on expressions
        """
        source = """
        d = 123
        """
        code = ast.parse(dedent(source))
        ns = {}
        with pytest.raises(Exception):
            out = _eval(code.body[0], ns)


def test_ast_source_expression():
    """ expressions were having a problem in astor """
    source = """np.random.randn(10, 10)"""
    code = ast.parse(dedent(source))

    expr = _convert_to_expression(code)
    assert source == ast_source(expr)


def test_ast_equal():
    source = """test(np.random.randn(10, 10))"""
    code1 = ast.parse(source, mode='eval')

    source2 = """test(np.random.randn(10, 10))"""
    code2 = ast.parse(source2, mode='eval')

    assert ast_equal(code1, code2)

    source3 = """test(np.random.randn(10, 11))"""
    code3 = ast.parse(source3, mode='eval')
    assert not ast_equal(code1, code3)

    # try subset
    source4 = """np.random.randn(10, 11)"""
    code4 = ast.parse(source4, mode='eval')

    assert ast_equal(code3.body.args[0], code4.body)


def test_ast_contains():
    source1 = """test(np.random.randn(10, 11)) + test2 / 99"""
    code1 = ast.parse(source1, mode='eval').body

    source2 = """np.random.randn(10, 11)"""
    test = ast.parse(source2, mode='eval').body
    assert list(ast_contains(code1, test))[0]

    test = ast.parse("10", mode='eval').body
    assert list(ast_contains(code1, test))[0]

    test = ast.parse("test2", mode='eval').body
    assert list(ast_contains(code1, test))[0]

    test = ast.parse("np.random.randn", mode='eval').body
    assert list(ast_contains(code1, test))[0]

    test = ast.parse("test2/99", mode='eval').body
    assert list(ast_contains(code1, test))[0]

    # False. Not that this isn't about a textual subset.
    # random.randn means nothing without np. it implies a 
    # top level random module
    test = ast.parse("random.randn", mode='eval').body
    assert not list(ast_contains(code1, test))

    # test against a module.
    source = """
    first_line() + 100
    bob = test(np.random.randn(10, 11)) + test2 / 99
    """
    mod = ast.parse(dedent(source))

    source2 = """np.random.randn(10, 11)"""
    test = ast.parse(source2, mode='eval').body
    assert list(ast_contains(mod, test))[0]

def test_ast_contains_expression():
    """
    Test that the fragment must be an expression.
    """
    # test against a module.
    source = """
    first_line() + 100
    bob = test(np.random.randn(10, 11)) + test2 / 99
    """
    mod = ast.parse(dedent(source))

    # expression compiled as module work sfine
    source2 = """np.random.randn(10, 11)"""
    test = ast.parse(source2)
    assert list(ast_contains(mod, test))[0]

    # assignment is a nono
    with pytest.raises(Exception, match="Fragment must be an expression"):
        source2 = """a = np.random.randn(10, 11)"""
        test = ast.parse(source2)
        list(ast_contains(mod, test))

def test_ast_contains_ignore_names():
    # test against a module.
    source = """
    test(np.random.randn(10, 11))
    """
    mod = ast.parse(dedent(source))

    # rename np to test
    source2 = """test.random.randn(10, 11)"""
    test = ast.parse(source2)
    assert list(ast_contains(mod, test, ignore_var_names=True))[0]

    # note that only Load(ctx.Load) ids will be ignored
    source2 = """test.text"""
    test = ast.parse(source2)
    assert not list(ast_contains(mod, test, ignore_var_names=True))

    # dumb example. single Name will always match
    source2 = """anything"""
    test = ast.parse(source2)
    assert list(ast_contains(mod, test, ignore_var_names=True))[0]

def test_ast_contains_ignore_names_multi():
    """
    Note that we can actually match multiple times, especially if we ignore
    names. ast_contains need to be changed to yield a generator.
    """
    source = """
    (a + b) + (c + d) + (e + f)
    """
    mod = ast.parse(dedent(source))

    source2 = """(x + y)"""
    test = ast.parse(source2)
    matches = list(ast_contains(mod, test, ignore_var_names=True))
    assert len(matches) == 3


def test_ast_graph_walk():
    source = """
    test(np.random.randn(10, 11))
    """
    mod = ast.parse(dedent(source))

    items = list(graph_walk(mod))
    graph_nodes = [item['node'] for item in items]

    walk_nodes = list(ast.walk(mod))
    # remove module node which the graph_walk won't have
    assert isinstance(walk_nodes.pop(0), ast.Module)

    # we should have reached the same nodes, not in same order
    assert collections.Counter(graph_nodes) == collections.Counter(walk_nodes)

    graph_types = [
        ast.Load,
        ast.Name,
        ast.Load,
        ast.Name,
        ast.Load,
        ast.Attribute,
        ast.Load,
        ast.Attribute,
        ast.Constant,
        ast.Constant,
        ast.Call,
        ast.Call,
        ast.Expr,
    ]

    # using type order to check that the type ordering is stable..
    assert list(map(type, graph_nodes)) == graph_types

def test_code_context_subset():
    df = pd.DataFrame(np.random.randn(30, 3), columns=['a', 'bob', 'c'])
    ns = {
        'df': df,
        'c': 1,
        'pd': pd,
        'np': np
    }
    source = """pd.rolling_sum(np.log(df + 10), 5, min_periods=c)"""
    code = ast.parse(dedent(source), mode='eval')

    # use blah instead of df. same code.
    child_ns = ns.copy()
    child_ns['blah'] = ns['df']
    child_code = ast.parse("np.log(blah+10)") # note that df was renamed blah

    assert not list(code_context_subset(code, ns, child_code, child_ns,
                                        ignore_var_names=False))

    # ignoring the var names should get us our match
    items = code_context_subset(code, ns, child_code, child_ns,
                            ignore_var_names=True)
    items = list(items)
    item = items[0]
    assert len(items) == 1
    assert item is not None

    field_name = 'args'
    field_index = 0
    correct = getattr(code.body, field_name)[field_index]
    assert item['node'] is correct
    assert item['parent'] is code.body
    assert item['field_name'] == field_name
    assert item['field_index'] == field_index

def test_code_context_subset_by_value():
    """
    test that when we have multiple ast matches,
    we properly test by value.
    previously ast_contains only returned first match, and so 
    code_context_subset wouldn't always return if the value match was
    on the second match
    """
    ns = {
        'a': 1,
        'b': 2,
        'c': 3,
        'd': 4
    }

    source = "(a + b) + (c + d)"
    code = ast.parse(dedent(source), mode='eval')

    # use blah instead of df. same code.
    child_ns = {
        'x': 1,
        'y': 2
    }

    child_code = ast.parse("x + y") # note that df was renamed blah
    res = list(code_context_subset(code, ns, child_code, child_ns,
                                        ignore_var_names=True))

    # matches first group by value
    assert ast_source(res[0]['node']) == '(a + b)'

    # try to match second group
    child_ns = {
        'x': 3,
        'y': 4
    }
    res = list(code_context_subset(code, ns, child_code, child_ns,
                                        ignore_var_names=True))
    # matched the second group
    assert ast_source(res[0]['node']) == '(c + d)'

def test_code_context_subset_match_multi():
    # try to match multiple groups
    ns = {
        'a': 1,
        'b': 2,
        'c': 1,
        'd': 2
    }

    source = "(a + b) + (c + d)"
    code = ast.parse(dedent(source), mode='eval')

    child_ns = {
        'x': 1,
        'y': 2
    }

    child_code = ast.parse("x + y") # note that df was renamed blah
    res = list(code_context_subset(code, ns, child_code, child_ns,
                                        ignore_var_names=True))

    test = list(map(lambda x: ast_source(x['node']), res))
    correct = ['(a + b)', '(c + d)']
    assert collections.Counter(test) == collections.Counter(correct)

def test_generate_getter_var():
    key = object()
    correct = 10
    node, ns = generate_getter_var(key, correct)
    val = _eval(node, ns)
    assert val == correct

def test_generate_getter_lazy():
    class FakeManifest:
        def __init__(self, value):
            self.value = value

        def get_obj(self):
            return self.value

    correct = "TEST"
    manifest = FakeManifest(correct)
    node, ns = generate_getter_lazy(manifest)
    val = _eval(node, ns)
    assert val == correct

def test_node_location():
    loc = NodeLocation(object(), 1, 2)
    assert collections.Counter(loc.keys()) == collections.Counter(['parent', 'field_name', 'field_index'])
    assert collections.Counter(list(dict(loc))) == collections.Counter(['parent', 'field_name', 'field_index'])

source = """
test(np.random.randn(10, 11))
"""
mod = ast.parse(dedent(source))

items = list(graph_walk(mod))
nodes = [item['node'] for item in items]
walk_nodes = list(ast.walk(ast.parse(source)))
gen = graph_walk(mod)

for item in items:
    node = item['node']
    break
