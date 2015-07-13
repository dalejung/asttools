import ast

class AstGraphWalker(object):
    """
    Like ast.walk except that it emits a dict:
        {
            node : ast.AST,
            parent : ast.AST,
            field_name : str,
            field_index : int or None,
            current_depth : int,
            line : _ast.stmt.
            location : {parent, field_name, field_index}
        }

        field_index is None when field is not a list
        current_depth starts from 0 at the top.

    This is largely a copy of AstGrapher but turned into a generator.

    # TODO merge the logic of both visitors.
    """

    def __init__(self, code):
        # 0 based depth
        self.current_depth = -1

        if isinstance(code, str):
            code = ast.parse(code)
        self.code = code
        self._processed = False
        self.line = None

    def process(self):
        if self._processed:
            raise Exception('Grapher has already processed code')
        yield from self.visit(self.code)
        self._processed = True

    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        yield from visitor(node)

    def visit_Module(self, node):
        body = node.body
        for line in node.body:
            self.line = line
            yield from self.generic_visit(line)

    def generic_visit(self, node):
        self.current_depth += 1
        for field_name, field in ast.iter_fields(node):
            if isinstance(field, list):
                for i, item in enumerate(field):
                    yield from self.handle_item(node, item, field_name, i)
                continue

            # need to flatten so we don't have special processing
            # for lists vs single values
            item = field
            yield from self.handle_item(node, item, field_name)
        self.current_depth -= 1

    def handle_item(self, parent, node, field_name, i=None):
        """ insert node => (parent, field_name, i) into graph"""
        if isinstance(node, (str, int, bytes, float, type(None))):
            # skip scalars
            return

        location = {
            'parent': parent,
            'field_name': field_name,
            'field_index': i
        }

        item = {
            'node': node,
            'depth': self.current_depth,
            'location': location,
            'line': self.line
        }

        item.update(location)
        yield item

        yield from self.visit(node) 

def graph_walk(code):
    walker = AstGraphWalker(code)
    return walker.process()
