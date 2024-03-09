import ast
import pytest


def test_constant():
    """
    Changed in version 3.8: Class ast.Constant is now used for all constants.

    These used to be ast.Num, ast.Str, etc
    """
    constant = ast.parse("123").body[0].value
    assert isinstance(constant, ast.Constant)

    constant = ast.parse("'dale'").body[0].value
    assert isinstance(constant, ast.Constant)


def test_module():
    """
    type_ignores was added and ast.Module will fail to compile without it.
    """
    expr = ast.parse("d = 123").body[0]
    module = ast.Module([expr], type_ignores=[])

    # bad_module = ast.Module([expr])
    # I guess this was fixed in 3.12
    # with pytest.raises(TypeError):
    #     compile(bad_module, 'hi', 'exec')

    code = compile(module, 'hi', 'exec')
    ns = {}
    exec(code, ns)
    assert ns['d'] == 123


def test_subscript():
    """
    Changed in version 3.9: Simple indices are represented by their value,
    extended slices are represented as tuples.
    """
    # var as index
    expr = ast.parse("dale[k]").body[0]
    subscript = expr.value
    assert isinstance(subscript, ast.Subscript)
    assert isinstance(expr.value.slice, ast.Name)
    assert expr.value.slice.id == 'k'

    # constant
    expr = ast.parse("dale[3]").body[0]
    subscript = expr.value
    assert isinstance(subscript, ast.Subscript)
    assert isinstance(expr.value.slice, ast.Constant)
    assert expr.value.slice.value == 3

    # extended
    expr = ast.parse("dale[3:, 10]").body[0]
    subscript = expr.value
    assert isinstance(subscript, ast.Subscript)
    assert isinstance(expr.value.slice, ast.Tuple)
    assert isinstance(expr.value.slice.elts[0], ast.Slice)
    assert isinstance(expr.value.slice.elts[1], ast.Constant)
