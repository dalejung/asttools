import ast
import inspect
import nose.tools as nt

from .common import get_source, quick_parse

def create_function(code, func=None,
                    globals=None,
                    filename=None):
    """
    Creates a function object without touching any existing namespaces. Using
    something like types.FunctionType doesn't work because you cannot compile
    a code obj with a return statement.

    This function is meant for creating functions to replace existing functions
    via decorators.

    code : ast.AST, str
        code or source string that includes only a function definition
    func : Function
        will be used as a template for filename and globals if they are not
        passed in
    globals : dict
        env function will be executed in
    filename : str
        filename attached to code object and used for debug statements
    """
    if func:
        filename = inspect.getfile(func)
        globals = globals or func.__globals__

    if filename is None:
        filename = '<asttools.function.create_function>'

    if isinstance(code, str):
        code = ast.parse(code)

    module = code
    if isinstance(code, ast.FunctionDef):
        module = ast.Module()
        module.body = [code]

    if not isinstance(module, ast.Module):
        raise TypeError("Expected ast.Module by this point.")

    func_def = module.body[0]
    func_name = func_def.name
    module_obj = compile(module, filename, 'exec')

    ns = {}
    exec(module_obj, globals, ns)
    new_func = ns[func_name]
    return new_func

def func_rewrite(transform, post_wrap=None):
    def _wrapper(func):
        code = ast.parse(get_source(func))
        transform(code)
        new_func = create_function(code, func=func)
        if post_wrap:
            post_wrap(new_func, func)
        return new_func
    return _wrapper

def get_invoked_args(func, *args, **kwargs):
    """
    Based on a functions argspec, figure out what the resultant function
    scope would be based on variables passed in
    """
    # handle functools.wraps functions
    if hasattr(func, '__wrapped__'):
        argspec = inspect.getargspec(func.__wrapped__)
    else:
        argspec = inspect.getargspec(func)

    # we're assuming self is not in *args for method calls
    args_names = argspec.args
    if argspec.args[0] == 'self':
        args_names = args_names[1:]

    realized_args = dict(zip(args_names, args))
    assert not set(realized_args).intersection(kwargs)
    res = kwargs.copy()
    res.update(realized_args)
    return res

def func_args_realizer(func_def):
    """
    Using an ast.FunctionDef node, create a items list node that
    will give us the passed in args by name.
    def whee(bob, frank=1):
        pass

    whee(1, 3) => [('bob', 1), ('frank', 3)]
    whee(1) => [('bob', 1), ('frank', 1)]
    """
    args = [arg.arg for arg in func_def.args.args]
    kw_only = [arg.arg for arg in func_def.args.kwonlyargs]
    args = args + kw_only
    if args[0] == 'self':
        args.pop(0)

    items = map("('{0}', {0})".format, args)
    items_list = "[ {0} ]".format(', '.join(items))
    return items_list
