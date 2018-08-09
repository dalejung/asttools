import ast
import inspect
import types
from typing import List

from earthdragon.typecheck import typecheck

from .common import get_source, quick_parse
from .repr import ast_source

def create_function(code, func=None,
                    globals=None,
                    filename=None,
                    ignore_closure=False):
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

    grabber = lambda ns, func_name: ns[func_name]

    uses_super = False
    if func and func.__closure__ and not ignore_closure:
        if func.__code__.co_freevars == ('__class__',):
            uses_super = True
        else:
            raise Exception("Current can't handle closures other than super()")

    if uses_super:
        class_def = wrap_func_def_in_class(func_def)
        module.body = [class_def]
        grabber = lambda ns, func_name: getattr(ns['klass'], func_name)

    module = ast.fix_missing_locations(module)
    module_obj = compile(module, filename, 'exec')

    ns = {}
    exec(module_obj, globals, ns)
    new_func = grabber(ns, func_name)

    if uses_super:
        new_func = types.FunctionType(new_func.__code__, new_func.__globals__,
                                    closure=func.__closure__)

    new_func.__asttools_source__ = ast_source(module)

    return new_func

def wrap_func_def_in_class(func_def):
    class_def = ast.ClassDef(
        name='klass',
        bases=[],
        keywords=[],
        body=[func_def],
        lineno=0,
        col_offset=0,
        decorator_list=[],
        starargs=None,
        kwargs=None
    )
    return class_def


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
        if hasattr(argspec, '__wrapped__'):
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

@typecheck
def func_def_args(func_def: ast.FunctionDef) -> List[str]:
    args = [arg.arg for arg in func_def.args.args]
    kw_only = [arg.arg for arg in func_def.args.kwonlyargs]
    args = args + kw_only
    if func_def.args.vararg:
        args.append(func_def.args.vararg.arg)
    if func_def.args.kwarg:
        args.append(func_def.args.kwarg.arg)

    if args[0] == 'self':
        args.pop(0)
    return args

def func_args_realizer(args):
    """
    Using an ast.FunctionDef node, create a items list node that
    will give us the passed in args by name.

    def whee(bob, frank=1):
        pass

    whee(1, 3) => [('bob', 1), ('frank', 3)]
    whee(1) => [('bob', 1), ('frank', 1)]
    """
    items = map("('{0}', {0})".format, args)
    items_list = "[ {0} ]".format(', '.join(items))
    return items_list

def arg_name(arg):
    if isinstance(arg, str):
        return arg
    if isinstance(arg, ast.Starred):
        return arg_name(arg.value)
    if isinstance(arg, ast.Name):
        return arg.id
    if isinstance(arg, (ast.arg, ast.keyword)):
        return arg.arg
    raise TypeError("Only accepts str, Name and arg. "
            "Received{0}".format(type(arg)))

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
    args, starargs = split_call_args(node)
    keywords, kwargs = split_call_kwargs(node)

    args = [arg_name(arg) for arg in args]
    kw = [(kw.arg, kw.value) for kw in keywords]

    kw_args, kw_defaults = [], []
    if kw:
        kw_args, kw_defaults = zip(*kw)
    args = args + list(kw_args)

    argspec = inspect.ArgSpec(args, starargs, kwargs, kw_defaults)
    return argspec

def _ast_argspec_def(node):
    args = [arg_name(arg) for arg in node.args.args]
    kw_defaults = node.args.defaults

    varargs = node.args.vararg and node.args.vararg.arg
    keywords = node.args.kwarg and node.args.kwarg.arg
    argspec = inspect.ArgSpec(args, varargs, keywords, kw_defaults)
    return argspec


def add_call_kwargs(node, name):
    """
    add a **name kwarg to call node. python3.5 doesn't have kwarg.
    It instead just uses a keyword with an empty arg
    """
    value = name
    if isinstance(name, str):
        value = ast.Name(id=name, ctx=ast.Load())

    keyword = ast.keyword(arg=None, value=value)
    node.keywords.append(keyword)


def add_call_starargs(node, name):
    """
    add a *name stararg to call node. python3.5 doesn't have stararg.
    It uses a ast.Starred in the args list
    """
    value = name
    if isinstance(name, str):
        value = ast.Name(id=name, ctx=ast.Load())

    starred = ast.Starred(value=value,
            ctx=ast.Load())
    node.args.append(starred)

def get_call_starargs(node):
    """
    Get the stararg name from Call node.

    Only supports the pre 3.5 semantic of a single *args at the end.
    """
    args = node.args
    if not args:
        return None
    last = args[-1]
    star_count = sum(map(lambda obj: isinstance(obj, ast.Starred), args))
    if star_count > 1:
        raise NotImplementedError("Currently only supports one stararg")

    if not isinstance(last, ast.Starred):
        return

    if not isinstance(last.value, ast.Name):
        raise ValueError("Only support starargs that unpack a variable")
    return last.value.id

def get_call_kwargs(node):
    """
    Get the kwargs name from Call node.
    """
    keywords = node.keywords
    if len(keywords) == 0:
        return None

    # dunno if we can get more than one dict unpack in python 3.5
    # check anyways
    kwargs_count = sum(map(lambda obj: obj.arg is None, keywords))
    if kwargs_count > 1:
        raise NotImplementedError("Currently only supports one kwargs")

    last = keywords[-1]
    # keywords have arg = None
    if not last.arg is None:
        return None

    if not isinstance(last.value, ast.Name):
        raise ValueError("Only support starargs that unpack a variable")

    return last.value.id

def split_call_args(node):
    """
    Split Call.args into args and starargs
    """
    args = node.args
    stararg = get_call_starargs(node)
    if stararg:
        args = args[:-1]
    return args, stararg

def split_call_kwargs(node):
    """
    Split Call.keywords into keywords and kwargs
    """
    keywords = node.keywords
    kwargs = get_call_kwargs(node)
    if kwargs:
        keywords = keywords[:-1]
    return keywords, kwargs
