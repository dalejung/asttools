import ast

from textwrap import dedent
from itertools import zip_longest, starmap

import nose.tools as nt

from .. import get_source, quick_parse, Matcher
from ..function import create_function, func_rewrite, ast_argspec
from ..transform import coroutine, transform
from ..graph import iter_fields

def test_create_function():
    # grab ast.walk
    new_func = create_function("def walk(): return 10", ast.walk)
    nt.assert_equals(new_func.__module__, 'ast') # module is retained
    nt.assert_equals(new_func(), 10)


    def some_func(bob):
        return bob
    # modify function to add 5
    code = ast.parse(get_source(some_func))
    code.body[0].body.insert(0, quick_parse("bob += 5"))
    add_5 = create_function(code, func=some_func)

    nt.assert_equals(some_func(10), 10)
    nt.assert_equals(add_5(10), 15)

def test_create_function_globals():
    new_func = create_function("def walk(): return AST", ast.walk)
    # should grab AST form the ast.walk global namespace
    nt.assert_is(new_func(), ast.AST)

    new_func2 = create_function("def walk(): return AST", ast.walk,
                                globals={'AST':1})
    nt.assert_equal(new_func2(), 1)

def test_create_function_source():
    source = "def walk(): return AST"
    new_func = create_function(source, ast.walk)
    correct = ast.parse(source)
    test = ast.parse(new_func.__asttools_source__)
    nt.assert_equal(ast.dump(test), ast.dump(correct))
    # should grab AST form the ast.walk global namespace

def test_wrap():
    def capture_transform(code):
        @coroutine.wrap
        def _transform():
            node, meta = yield
            matcher = Matcher("'<any>'.capture()")
            while True:
                if matcher.match(node):
                    node.kwargs = quick_parse("locals()").value
                    node.func.attr = 'format'

                node, meta = yield node
            return node
        return transform(code, _transform())

    @func_rewrite(capture_transform)
    def hello(obj):
        end = 'goodbye'
        return "hello {obj}... {end}".capture()

    nt.assert_equal(hello('bob'), 'hello bob... goodbye')


def test_matcher_with():
    matcher = Matcher("with capture(): _any_")
    test_code = ast.parse("with capture(): pass")
    nt.assert_true(matcher.match(test_code.body[0]))

    # remove any sentinel
    matcher = Matcher("with capture(): 1")
    test_code = ast.parse("with capture(): pass")
    nt.assert_false(matcher.match(test_code.body[0]))

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
    with nt.assert_raises(AssertionError):
        ast_argspec_case(source)
