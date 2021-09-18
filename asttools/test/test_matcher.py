from textwrap import dedent
import ast

from ..matcher import Matcher, is_any
from ..common import quick_parse

import pytest


class AM:
    def __init__(self, template, verbose=False):
        self.template = template

        self.verbose = verbose
        matcher = Matcher(template)
        self.matcher = matcher

    def assert_match(self, other):
        other = dedent(other)
        other_code = quick_parse(other)
        matcher = self.matcher
        template = self.template

        if matcher != other_code:
            msg = "AM({template}) != {other}".format(**locals())
            if self.verbose:
                log_lines = [
                    " ".join(map(str, log)) for log in self.matcher.logs
                ]
                print("\n".join(log_lines))
            raise AssertionError(msg)
        return self

    def __lshift__(self, other):
        return self.assert_match(other)


def test_with():
    matcher = AM("with(bob): _any_")
    test = """
    with(bob):
        print('hi')
        a = 1
    """
    matcher.assert_match(test)

    # test negative match
    with pytest.raises(AssertionError):
        matcher = AM("with(bob): not_wildcarded")
        matcher.assert_match(test)


def test_call():
    matcher = AM("test_call(_any_)")

    # just args
    matcher << "test_call(bob, whee)"

    # kwargs
    matcher << "test_call(bob, whee=1)"

    # kitch sink
    matcher << "test_call(bob, whee=1, *args, **kwargs)"

    # kitch sink
    matcher << "test_call(bob, whee=1, *args, **kwargs)"

    # test negative match
    with pytest.raises(AssertionError):
        matcher << "other_call(bob, whee)"

    AM("test_call(bob)") << "test_call(bob)"


def test_attribute():
    matcher = AM("test._any_")
    matcher << "test.anything"
    matcher << "test.hello"
    AM("test.specific_attribute") << "test.specific_attribute"
    with pytest.raises(AssertionError):
        AM("test.specific_attribute") << "test.other"

    # node value
    AM("_any_.frank") << "test.frank"
    with pytest.raises(AssertionError):
        AM("_any_.frank") << "test.bob"


def test_subscript():
    # as of 3.9 simple indices like _any_ are represented by their value.
    # Previously this was wrapped in a ast.Index instance.
    assert isinstance(Matcher("meta[_any_]").template.slice, ast.Name)

    AM("meta[_any_]") << "meta[bob, frank:1]"
    AM("meta[_any_]") << "meta[1]"
    AM("meta[dale]") << "meta[dale]"
    AM("print(meta[dale])") << "print(meta[dale])"
    with pytest.raises(AssertionError):
        AM("meta[1]") << "meta[bob, frank:1]"

    with pytest.raises(AssertionError):
        AM("print(meta[dale])") << "other(meta[dale])"

    with pytest.raises(AssertionError):
        AM("other[1]") << "test[1]"

    AM("_any_[_any_]") << "hi.frank()[dale]"
    AM("_any_[_any_]") << "bob[1]"

    with pytest.raises(AssertionError):
        AM("_any_[_any_]") << "hi.frank()[dale].bob"


def test_unary_op():
    AM("~_any_") << "~testme"
    AM("~testme") << "~testme"
    with pytest.raises(AssertionError):
        AM("~testme") << "~testme3333"


def test_binary_op():
    AM("dale | _any_") << "dale | 123"
    AM("_any_ | _any_") << "fooo | m[123]"
    # mismatched operand
    with pytest.raises(AssertionError):
        AM("_any_ | _any_") << "fooo + m[123]"

    # left off
    with pytest.raises(AssertionError):
        AM("dale | _any_") << "fooo | m[123]"

    # right off
    with pytest.raises(AssertionError):
        AM("_any_ | test") << "fooo | m[123]"


def test_constant():
    AM("'<any>'.capture()") << "'dale'.capture()"

    # note that there isn't a numeric any value. Since all constants are now
    # ast.Constant. Putting a '_any_' constant will also match numbers, named
    # constants, etc
    AM("1 + '_any_'") << "1 + 'dale'"
    AM("1 + '_any_'") << "1 + 1"
    AM("1 + '_any_'") << "1 + False"
    AM("1 + '_any_'") << "1 + None"

    # TODO should '_any_' only match other constants? currently it just short
    # circuits completely.
    AM("1 + '_any_'") << "1 + dale()"


def test_any_star():
    """
    The <any>/_any_ sentinels whitelist a lot of forms. I need to look at
    pattern matching libs to see if I want to support a more strict pattern
    match.

    In this test I'm just including example I'm not sure should match.
    """
    AM("'<any>'.capture()") << "dale.dale.capture()"
    AM("1 + '_any_'") << "1 + dale()"
    AM("1 + '_any_'") << "1 + (dale() + 1)"


def test_name():
    AM("[_any_]") << "[dale]"
    # currently a top level _any_ will whitelist any equal depth subtree in
    # other. Still not sure if this should require that `other` also be a Name.
    AM("_any_") << "[dale]"
    AM("_any_") << "frank()[dale]"

    with pytest.raises(AssertionError):
        AM("dale") << "fooo"

    with pytest.raises(AssertionError):
        AM("[_any_, 1]") << "[dale, 2]"


@pytest.mark.xfail
def test_granular_any():
    with pytest.raises():
        AM("meta[1, _any_]") << "meta[1, 1, 3]"

