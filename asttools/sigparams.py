import ast
from typing import (
    Any,
    cast,
)
from inspect import (
    Parameter,
    _empty,
)

from .common import get_arg_name


def ast_sigparams(node):
    """
    Get the sigparams equivalent from ast.Call and ast.FunctionDef.

    Both:

    def func(arg1, arg2, *args, **kwargs):
        pass

    func(arg1, arg2, *args, **kwargs)

    will return the same sigparams.

    Note: The defaults will ast.Node since we don't know the values of
    variables till runtime.
    """
    if isinstance(node, ast.Call):
        ret = _ast_sigparams_call(node)
    elif isinstance(node, ast.FunctionDef):
        ret = _ast_sigparams_def(node)
    else:
        raise TypeError()

    return ret


def create_sigparam(
    args: dict[str | int, Any],
    keywords: dict[str | int, Any],
    require_starargs_for_keyword_only=False,
):

    contains_starargs = False
    parameters = {}
    for arg, default in args.items():
        if isinstance(arg, int):
            raise Exception("Cannot handle constant args currently")

        if arg.startswith('*'):
            param = Parameter(default, kind=Parameter.VAR_POSITIONAL)
            contains_starargs = True
        else:
            default_value = get_sig_default_value(default)
            param = Parameter(
                get_arg_name(arg),
                default=default_value,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
            )
        assert param.name not in parameters
        parameters[param.name] = param

    # NOTE: Calling semantics doesn't really have a POSITIONAL_OR_KEYWORD. That
    # is meaningless since a call param is either positional or keyword. But
    # since I'm trying to align the semantics of Call/func defs, I will treat
    # keywords without starargs as being POSITIONAL_OR_KEYWORD.
    # TODO: should I just have an equality tester that normalizes KEYWORD_ONLY
    # and POSITIONAL_OR_KEYWORD?
    keyword_kind = Parameter.KEYWORD_ONLY
    if require_starargs_for_keyword_only and not contains_starargs:
        keyword_kind = Parameter.POSITIONAL_OR_KEYWORD

    for kw_name, kw_default in keywords.items():
        # keyword won't have int keys
        assert isinstance(kw_name, str)
        if kw_name.startswith('**'):
            param = Parameter(kw_default, kind=Parameter.VAR_KEYWORD)
        else:
            kw_default_value = get_sig_default_value(kw_default)
            param = Parameter(
                kw_name,
                default=kw_default_value,
                kind=keyword_kind
            )
        assert param.name not in parameters
        parameters[param.name] = param

    return parameters


def get_sig_default_value(node):
    if node is _empty:
        return _empty

    match node:
        case ast.Constant():
            return node.value
        case _:
            raise ValueError(f"Cannot derive live value from {node}")


def get_call_arg_params(node: ast.Call) -> dict[str | int, Any]:
    """
    """
    args = node.args
    arg_params = {}
    for i, arg in enumerate(args):
        match arg:
            case ast.Constant():
                arg_params[i] = arg.value
            case ast.Name():
                arg_params[arg.id] = _empty
            case ast.Starred():
                if not isinstance(arg.value, ast.Name):
                    raise ValueError("Only support name for *varargs")
                name = cast(ast.Name, arg.value)
                arg_params['*' + name.id] = name.id
    return arg_params


def get_call_keyword_params(node: ast.Call):
    keywords = node.keywords

    kw_params = {}
    for kw in keywords:
        if kw.arg is None:
            if not isinstance(kw.value, ast.Name):
                raise ValueError("Only support name for **kwargs")
            name = cast(ast.Name, kw.value)
            kw_params['**' + name.id] = name.id
        else:
            kw_params[kw.arg] = kw.value

    return kw_params


def _ast_sigparams_call(call: ast.Call):
    arg_params = get_call_arg_params(call)
    kw_params = get_call_keyword_params(call)
    parameters = create_sigparam(
        arg_params,
        kw_params,
        require_starargs_for_keyword_only=True
    )
    return parameters


def _ast_sigparams_def(node: ast.FunctionDef):
    def_args = node.args

    arg_params = get_params_from_func_def(
        def_args.args,
        def_args.defaults,
        def_args.vararg,
        '*',
    )

    kw_params = get_params_from_func_def(
        def_args.kwonlyargs,
        def_args.kw_defaults,
        def_args.kwarg,
        '**',
    )
    parameters = create_sigparam(arg_params, kw_params)
    return parameters


def get_params_from_func_def(
        args: list[ast.arg],
        defaults: list,
        variadic: ast.arg | None,
        variadic_perfix: str,
):
    params: dict[str | int, Any] = {
        arg.arg: _empty for arg in args
    }

    for name, default in zip(reversed(params.keys()), defaults):
        params[name] = default

    if variadic:
        params[variadic_perfix + variadic.arg] = variadic.arg

    return params


if __name__ == '__main__':
    ...
