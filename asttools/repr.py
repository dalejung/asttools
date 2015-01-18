import ast

import astor

def ast_repr(obj):
    if isinstance(obj, ast.AST):
        obj_class = obj.__class__.__name__
        source =  ast_source(obj)
        return('ast.{obj_class}: {source}'.format(**locals()))
    if isinstance(obj, list):
        return([ast_repr(o) for o in obj])
    return obj

def ast_print(*objs):
    print(*list(ast_repr(obj) for obj in objs))

def ast_source(obj):
    # astor doens't support ast.Expression atm
    if isinstance(obj, ast.Expression):
        obj = obj.body
    source =  astor.to_source(obj)
    return source
