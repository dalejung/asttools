import ast
import logging

from .common import _convert_to_expression
from .repr import ast_repr

def _exec(node, ns):
    """
    A kind of catch all exec/eval. It will try to do an eval if possible.

    Fall back to exec
    """
    code = _compile(node)
    res = eval(code, ns)
    return res

def _eval(node, ns):
    """
    Will eval an ast Node within a namespace.
    """
    expr = _convert_to_expression(node)
    if expr is None:
        raise Exception("{0} cannot be evaled".format(repr(node)))
    return _exec(node, ns)

def _compile(node, force_eval=False):
    node = ast.fix_missing_locations(node)

    mode = 'exec'
    if not isinstance(node, ast.Module):
        module = ast.Module()
        module.body = [node]

    # try expression eval
    expr = _convert_to_expression(node)
    if expr:
        module = expr
        mode = 'eval'

    code = compile(module, '<dale>', mode)
    return code
