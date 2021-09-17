import ast

from textwrap import dedent
from itertools import zip_longest, starmap

import pytest

from .. import get_source, quick_parse, Matcher
from ..function import (
    create_function,
    func_rewrite,
    ast_argspec,
    func_def_args,
    func_args_realizer,
    add_call_kwargs,
    add_call_starargs,
    get_call_starargs,
    get_call_kwargs
)
from ..transform import coroutine, transform
from ..graph import iter_fields

from .util import run_in_place, preamble
preamble()

def test_create_function():
    # grab ast.walk
    new_func = create_function("def walk(): return 10", ast.walk)
    assert new_func.__module__ == 'ast' # module is retained
    assert new_func() == 10


    def some_func(bob):
        return bob
    # modify function to add 5
    code = ast.parse(get_source(some_func))
    code.body[0].body.insert(0, quick_parse("bob += 5"))
    add_5 = create_function(code, func=some_func)

    assert some_func(10) == 10
    assert add_5(10) == 15

def test_create_function_globals():
    new_func = create_function("def walk(): return AST", ast.walk)
    # should grab AST form the ast.walk global namespace
    assert new_func() is ast.AST

    new_func2 = create_function("def walk(): return AST", ast.walk,
                                globals={'AST':1})
    assert new_func2() == 1

def test_create_function_source():
    source = "def walk(): return AST"
    new_func = create_function(source, ast.walk)
    correct = ast.parse(source)
    test = ast.parse(new_func.__asttools_source__)
    assert ast.dump(test) == ast.dump(correct)
    # should grab AST form the ast.walk global namespace

def test_wrap():
    def capture_transform(code):
        @coroutine.wrap
        def _transform():
            node, meta = yield
            matcher = Matcher("'<any>'.capture()")
            while True:
                if matcher.match(node):
                    add_call_kwargs(node, quick_parse("locals()").value)
                    node.func.attr = 'format'

                node, meta = yield node
            return node
        return transform(code, _transform())

    @func_rewrite(capture_transform)
    def hello(obj):
        end = 'goodbye'
        return "hello {obj}... {end}".capture()

    assert hello('bob') == 'hello bob... goodbye'


def test_matcher_with():
    matcher = Matcher("with capture(): _any_")
    test_code = ast.parse("with capture(): pass")
    assert matcher.match(test_code.body[0])

    # remove any sentinel
    matcher = Matcher("with capture(): 1")
    test_code = ast.parse("with capture(): pass")
    assert not matcher.match(test_code.body[0])

def ast_argspec_case(source):
    code = ast.parse(dedent(source))
    func_def = code.body[0]
    call = code.body[1].value
    assert isinstance(func_def, ast.FunctionDef)
    assert isinstance(call, ast.Call)

    func_argspec = ast_argspec(func_def)
    call_argspec = ast_argspec(call)
    same, failures = ast_argspec_equal(func_argspec, call_argspec)
    if not same:
        raise AssertionError(str(failures))

def _equal(left, right):
    if isinstance(left, (list, tuple)):
        return starmap(_equal, zip_longest(left, right))

    if isinstance(left, ast.AST):
        left = ast.dump(left)
        right = ast.dump(right)
    return (left == right, left, right)

listify = lambda x: not isinstance(x, (list, tuple)) and [x] or x

def ast_argspec_equal(left, right):
    attrs = ['args', 'varargs', 'keywords', 'defaults']
    lefts = [getattr(left, attr) for attr in attrs]
    rights = [getattr(right, attr) for attr in attrs]
    for lval, rval in zip(lefts, rights):
        lval, rval = listify(lval), listify(rval)
        ret = _equal(lval, rval)
        failures = list(filter(lambda x: not x[0], ret))
        if any(failures):
            return False, failures
    return True, []

def test_argsepc_equal():
    source = """
    def func(arg1, arg2, *args, **kwargs):
        pass

    func(arg1, arg2, *args, **kwargs)
    """
    ast_argspec_case(source)

    source = """
    def func(arg1, arg2=1):
        pass

    func(arg1, arg2=1)
    """
    ast_argspec_case(source)

    source = """
    def func(arg1, arg2='different'):
        pass

    func(arg1, arg2=1)
    """
    with pytest.raises(AssertionError):
        ast_argspec_case(source)

def test_create_function_method_super():
    """
    The only caveat with creating functions is when you have to deal with
    closures. super() is one such instance.
    """
    class Obj:
        def __init__(self):
            super().__init__()
    Obj.old_init = Obj.__init__

    def _init(self):
        super().__init__()
        self.new_init = True

    Obj.__init__ = _init
    with pytest.raises(RuntimeError):
        # bah, we didn't account for the super() cell
        Obj()
    source = get_source(_init)

    new_init = create_function(source, Obj.old_init)
    Obj.__init__ = new_init
    assert Obj().new_init # yay

def test_create_function_ignore_closure():
    """
    Sometimes the original function has a closure, but you don't need it
    after transform.
    """
    class Obj:
        def __init__(self):
            super().__init__()
    Obj.old_init = Obj.__init__

    def _init(self):
        self.new_init = True

    source = get_source(_init)
    with pytest.raises(ValueError, match="requires closure of length 0"):
        new_init = create_function(source, Obj.old_init)
        # fails

    new_init = create_function(source, Obj.old_init, ignore_closure=True)
    Obj.__init__ = new_init

    assert Obj().new_init # yay

def test_func_def_args():
    func_text = """
    def bob(arg1, arg2, kw1=None, k2=1, *args, **kwargs):
        pass
    """
    code = ast.parse(dedent(func_text))
    func_def = code.body[0]

    args = func_def_args(func_def)
    assert args == ['arg1', 'arg2', 'kw1', 'k2', 'args', 'kwargs']

def test_func_def_args_realizer():
    """
    Test func_def_args and func_def_realizer
    """
    func_text = """
    def bob(arg1, arg2, kw1=None, k2=1, *args, **kwargs):
        pass
    """
    code = ast.parse(dedent(func_text))
    func_def = code.body[0]

    args = func_def_args(func_def)
    assert args == ['arg1', 'arg2', 'kw1', 'k2', 'args', 'kwargs']

    func_text = """
    def bob(arg1, arg2, kw1=None, kw2=1, **dale):
        return realizer
    """
    code = ast.parse(dedent(func_text))
    func_def = code.body[0]

    args = func_def_args(func_def)
    print(args)
    assert args == ['arg1', 'arg2', 'kw1', 'kw2', 'dale']

    # create a realizer and create a func that returns it
    realizer = func_args_realizer(args)
    func = create_function(dedent(func_text.replace('realizer', realizer)))
    result = func(1, 2, extra1=1, extra2=2)
    assert result[0] == ('arg1', 1)
    assert result[1] == ('arg2', 2)
    assert result[2] == ('kw1', None)
    assert result[3] == ('kw2', 1)
    assert result[4] == ('dale', {'extra1': 1, 'extra2': 2})

def test_add_call_args():
    """
    Adding starargs and kwargs to Call nodes.

    Python 3.4 and 3.5 have different structures
    """
    call_text = """
    bob(1, 2, kw3=3)
    """
    code = ast.parse(dedent(call_text))
    call_node = code.body[0].value
    add_call_starargs(call_node, 'stardale')
    add_call_kwargs(call_node, 'dale')

    assert isinstance(call_node.args[2], ast.Starred)
    assert call_node.args[2].value.id == 'stardale'

    assert isinstance(call_node.keywords[1], ast.keyword)
    assert call_node.keywords[1].arg is None

def test_get_call_starargs():
    call_text = """
    bob(*bob, l=1, m=2, kw3=3, *args)
    """
    call_node = quick_parse(dedent(call_text)).value

    with pytest.raises(NotImplementedError):
        starargs = get_call_starargs(call_node)

    call_text = """
    bob(l=1, m=2, kw3=3, *args)
    """
    call_node = quick_parse(dedent(call_text)).value
    starargs = get_call_starargs(call_node)
    assert starargs == 'args'

    call_text = """
    bob(l=1, m=2, kw3=3, *locals())
    """
    call_node = quick_parse(dedent(call_text)).value
    with pytest.raises(ValueError):
        starargs = get_call_starargs(call_node)

def test_get_call_kwargs():
    call_text = """
    bob(l=1, m=2, kw3=3, *args, **dct)
    """
    call_node = quick_parse(dedent(call_text)).value

    kw = get_call_kwargs(call_node)
    assert kw == 'dct'

    call_text = """
    bob(l=1, m=2, kw3=3, *args)
    """
    call_node = quick_parse(dedent(call_text)).value

    kw = get_call_kwargs(call_node)
    assert kw is None

    call_text = """
    bob(l=1, m=2, kw3=3, **locals())
    """
    call_node = quick_parse(dedent(call_text)).value
    with pytest.raises(ValueError):
        starargs = get_call_kwargs(call_node)
