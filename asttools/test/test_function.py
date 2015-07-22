import ast

import nose.tools as nt

from .. import get_source, quick_parse, Matcher
from ..function import create_function, func_rewrite
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
