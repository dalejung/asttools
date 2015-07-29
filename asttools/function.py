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

def func_code(func):
    """
    return the ast.FunctionDef node of a function
    """
    code = ast.parse(get_source(func))
    func_def = code.body[0]
    assert len(code.body) == 1
    assert isinstance(func_def, ast.FunctionDef)
    return func_def

def get_invoked_args(argspec, *args, **kwargs):
    """
    Based on a functions argspec, figure out what the resultant function
    scope would be based on variables passed in
    """
    if not isinstance(argspec, inspect.ArgSpec):
        # handle functools.wraps functions
        if hasattr(func, '__wrapped__'):
            argspec = inspect.getargspec(argspec.__wrapped__)
        else:
            argspec = inspect.getargspec(argspec)

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

def arg_name(arg):
    if isinstance(arg, str):
        return arg
    if isinstance(arg, ast.Name):
        return arg.id
    if isinstance(arg, (ast.arg, ast.keyword)):
        return arg.arg
    raise TypeError("Only accepts str, Name and arg")

def arglist(node):
    try:
        return node.args.args
    except AttributeError:
        return node.args

def ast_argspec(node):
    """
    Get the argspec equivalent from ast.Call and ast.FunctionDef.

    Both:

    def func(arg1, arg2, *args, **kwargs):
        pass

    func(arg1, arg2, *args, **kwargs)

    will return the same argspec.

    Note: The defaults will ast.Node since we don't know the values of
    variables till runtime.
    """
    if isinstance(node, ast.Call):
        ret = _ast_argspec_call(node)
    elif isinstance(node, ast.FunctionDef):
        ret = _ast_argspec_def(node)
    else:
        raise TypeError()

    return ret

def _ast_argspec_call(node):
    args = [arg_name(arg) for arg in node.args]
    kw = [(kw.arg, kw.value) for kw in node.keywords]
    kw_args, kw_defaults = [], []
    if kw:
        kw_args, kw_defaults = zip(*kw)
    args = args + list(kw_args)

    varargs = node.starargs and node.starargs.id
    keywords = node.kwargs and node.kwargs.id
    argspec = inspect.ArgSpec(args, varargs, keywords, kw_defaults)
    return argspec

def _ast_argspec_def(node):
    args = [arg_name(arg) for arg in node.args.args]
    kw_defaults = node.args.defaults

    varargs = node.args.vararg and node.args.vararg.arg
    keywords = node.args.kwarg and node.args.kwarg.arg
    argspec = inspect.ArgSpec(args, varargs, keywords, kw_defaults)
    return argspec
