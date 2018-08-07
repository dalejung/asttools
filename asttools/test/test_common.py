import ast

from nose.tools import *
from ..common import get_source
from ..function import create_function

def test_get_source_create_function():
    # normally get source type logic barfs on dynamically created
    # functions. Make sure we use the source we stored.
    code = """def bob(self): return 1"""
    func = create_function(code)
    test = ast.parse(get_source(func))
    correct = ast.parse(code)

    assert ast.dump(test) == ast.dump(correct)
