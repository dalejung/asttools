import ast

from .graph import graph_walk

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
    source = ast.unparse(obj)
    return source.strip()

class IndentDumper:
    def visit(self, item):
        node = item['node']
        class_name = node.__class__.__name__
        type_method = 'visit_{class_name}'.format(class_name=class_name)

        generic = self.visit_generic
        if not isinstance(node, ast.AST):
            generic = self.visit_non_ast

        handler = getattr(self, type_method, generic)
        rep = handler(item)
        if rep is None:
            return None

        field = item['field_name']
        field_index = item['field_index']
        if field_index is not None:
            field = "{field}[{field_index}]".format(**locals())

        return "{field} = {rep}".format(field=field, rep=rep)

    def visit_generic(self, item):
        node = item['node']
        class_name = node.__class__.__name__
        return class_name

    def visit_Name(self, item):
        node = item['node']
        class_name = node.__class__.__name__
        return "Name(id={id})".format(id=node.id)

    def visit_Attribute(self, item):
        node = item['node']
        class_name = node.__class__.__name__
        return "Attribute(attr={attr})".format(attr=node.attr)

    def visit_Str(self, item):
        node = item['node']
        class_name = node.__class__.__name__
        return "{class_name}(s={s})".format(class_name=class_name,
                                                  s=repr(node.s))

    def visit_non_ast(self, item):
        # normal repr printing for nonasts
        node = item['node']
        return repr(node)

    def visit_Load(self, item):
        return None


def indented(code):
    if isinstance(code, str):
        code = ast.parse(text)

    dumper = IndentDumper()
    walker = graph_walk(code)
    for item in walker:
        node = item['node']
        indent = "  " * item['depth']
        rep = dumper.visit(item)
        if rep is None:
            continue
        for line in rep.split('\n'):
            print(indent, line)
