from textwrap import dedent

from ..matcher import Matcher
from ..common import quick_parse

import pytest

class AM:
    def __init__(self, template):
        self.template = template

        matcher = Matcher(template)
        self.matcher = matcher

    def assert_match(self, other):
        other = dedent(other)
        other_code = quick_parse(other)
        matcher = self.matcher
        template = self.template

        if matcher != other_code:
            msg = "AM({template}) != {other}".format(**locals())
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
