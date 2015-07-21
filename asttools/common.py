"""
Nothing here can import asttools modules.
"""
import ast

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

