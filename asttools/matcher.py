import ast
from .common import quick_parse, iter_fields

"""
Structural matching on ast with sentinels for wildcard matching.

template = '<any>'._any_()"
test = ast.parse('"hello {bob}".capture()')
for node in ast.walk(test):
    if matcher.match(node):
        node.kwargs = quick_parse("locals()").value
        node.func.attr = 'format'
"""
def is_any(val):
    # string match
    if val in ['<any>', '_any_']:
        return True

    # ast.Call.args, ast.With.
    if isinstance(val, list) and len(val) == 1:
        return is_any(val[0])

    if isinstance(val, ast.Name) and val.id == '_any_':
        return True
    return False

_missing = object()
class Matcher:
    def __init__(self, template):
        if isinstance(template, str):
            template = quick_parse(template)
            if isinstance(template, ast.Expr):
                template = template.value
        self.template = template

    def match(self, other, node=_missing):
        if node is _missing: # first run
            node = self.template
            # unwrap expression
            if isinstance(other, ast.Expr):
                other = other.value

        method = 'match_' + node.__class__.__name__
        matcher = getattr(self, method, self.generic_match)
        node_item = matcher(other, node)
        return node_item

    def generic_match(self, other, node):
        if type(node) != type(other):
            return False

        # match scalars via equality
        if not isinstance(node, ast.AST):
            return node == other

        return self.match_children(other, node)

    def match_children(self, other, node, skip=()):
        if not isinstance(node, ast.AST):
            return True

        for item, field_name, field_index in iter_fields(node):
            # we still try to grab other's child to make sure we have the same
            # structure.
            try:
                if field_index is None:
                    other_child = getattr(other, field_name)
                else:
                    other_child = getattr(other, field_name)[field_index]
            except (AttributeError, KeyError, IndexError):
                return False

            if field_name in skip:
                continue

            # children did not match, short circuit out of here
            if not self.match(other_child, item):
                return False
        return True

    def match_Str(self, other, node):
        if is_any(node.s):
            return True
        return node.s == other.s

    def match_Attribute(self, other, node):
        skip = ()
        if node.attr == '_any_':
            skip = ('attr')
        if isinstance(node.value, ast.Name) and node.value.id == '_any_':
            skip = ('value')

        return self.match_children(other, node, skip=skip)

    def match_Call(self, other, node):
        """
        call(_any_)
        """
        skip = ()
        if is_any(node.args):
            skip = ('args', 'keywords', 'starargs', 'kwargs')
        return self.match_children(other, node, skip=skip)

    def match_With(self, other, node):
        """
        with With():
            _any_
        """
        skip = ()
        body = node.body
        line = body[0]
        if len(body) == 1 and isinstance(line, ast.Expr) \
        and is_any(line.value):
            skip = ('body')

        return self.match_children(other, node, skip=skip)

    def match_Subscript(self, other, node):
        sl = node.slice
        skip = ()
        if isinstance(sl, ast.Index) and isinstance(sl.value, ast.Name)\
           and sl.value.id == '_any_':
            skip = ('slice')

        return self.match_children(other, node, skip=skip)

    def __eq__(self, other):
        if not isinstance(other, ast.AST):
            raise TypeError("Can only compare to AST")
        return self.match(other)
