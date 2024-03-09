import ast
import inspect
import types
from typing import List

from .common import get_source
from .repr import ast_source
from .sigparams import (
    ast_sigparams as ast_sigparams,
)


def klass_grabber(ns, func_name):
    return getattr(ns['klass'], func_name)


def getitem_grabber(ns, func_name):
    return ns[func_name]


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
        module = ast.Module([code], type_ignores=[])

    if not isinstance(module, ast.Module):
        raise TypeError("Expected ast.Module by this point.")

    func_def = module.body[0]
    func_name = func_def.name

    grabber = getitem_grabber

    uses_super = False
    if func and func.__closure__ and not ignore_closure:
        if func.__code__.co_freevars == ('__class__',):
            uses_super = True
        else:
            raise Exception("Current can't handle closures other than super()")

    if uses_super:
        class_def = wrap_func_def_in_class(func_def)
        module.body = [class_def]
        grabber = klass_grabber

    module = ast.fix_missing_locations(module)
    module_obj = compile(module, filename, 'exec')

    ns = {}
    exec(module_obj, globals, ns)
    new_func = grabber(ns, func_name)

    if uses_super:
        new_func = types.FunctionType(
            new_func.__code__,
            new_func.__globals__,
            closure=func.__closure__
        )

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


def arglist(node):
    try:
        return node.args.args
    except AttributeError:
        return node.args


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

    starred = ast.Starred(
        value=value,
        ctx=ast.Load()
    )
    node.args.append(starred)


def get_call_kwargs(node):
    sigparams = ast_sigparams(node)
    for name, param in sigparams.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return name


def get_call_starargs(node):
    sigparams = ast_sigparams(node)
    starargs = [
        param.name for param in sigparams.values()
        if param.kind == inspect.Parameter.VAR_POSITIONAL
    ]
    if len(starargs) > 1:
        raise NotImplementedError("Got more than one starargs")
    if len(starargs) == 1:
        return starargs[0]
