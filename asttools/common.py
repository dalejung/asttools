"""
Nothing here can import asttools modules.
"""
import ast
import inspect
import types
from textwrap import dedent

def _convert_to_expression(node):
    """ convert ast node to ast.Expression if possible, None if not """
    node = ast.fix_missing_locations(node)

    if isinstance(node, ast.Module):
        if len(node.body) != 1:
            return None
        if isinstance(node.body[0], ast.Expr):
            expr = node.body[0]
            # an expression that was compiled with mode='exec'
            return ast.Expression(lineno=0, col_offset=0, body=expr.value)

    if isinstance(node, ast.Expression):
        return node

    if isinstance(node, ast.expr):
        return ast.Expression(lineno=0, col_offset=0, body=node)

    if isinstance(node, ast.Expr):
        return ast.Expression(lineno=0, col_offset=0, body=node.value)

def iter_fields(node):
    """
    Returns child_node, field_name, field_index tuple.

    field_index will be None when field is singular.
    """
    for field_name, field in ast.iter_fields(node):
        if isinstance(field, list):
            for i, item in enumerate(field):
                yield item, field_name, i
        else:
            yield field, field_name, None

def get_source(obj):

    source = obj
    if isinstance(obj, types.ModuleType):
        source = inspect.getsource(obj)
    elif isinstance(obj, types.FunctionType):
        # try source generated from create_function first
        source = getattr(obj, '__asttools_source__', None)
        if source is None:
            source = inspect.unwrap(obj)
            source = dedent(inspect.getsource(source))
            source_lines = source.split('\n')
            # remove decorators
            not_decorator = lambda line: not line.startswith('@')
            source = '\n'.join(filter(not_decorator, source_lines))
    elif isinstance(obj, types.LambdaType):
        source = inspect.getsource(obj)

    if isinstance(source, (str)):
        source = dedent(source)
    else:
        raise NotImplementedError("{0}".format(str(source)))
    return source

def quick_parse(line, *args, **kwargs):
    """ quick way to generate nodes """
    if args or kwargs:
        line = line.format(*args, **kwargs)
    body = ast.parse(line).body
    if len(body) > 1:
        raise Exception("quick_parse only works with single lines of code")
    code = body[0]
    return code

def unwrap(node):
    """
    It a node cleanly translates to a python literal, return it instead.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Num):
        return node.n
    raise TypeError("Only handle primitive like nodes")

