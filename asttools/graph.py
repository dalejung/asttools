import ast
from collections import OrderedDict

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

class AstGraphWalker(object):
    """
    Like ast.walk except that it emits a dict:
        {
            node : ast.AST,
            parent : ast.AST,
            field_name : str,
            field_index : int or None,
            fields : OrderedDict {field_name : [field_item]}
            current_depth : int,
            line : _ast.stmt.
            location : {parent, field_name, field_index}
        }

        field_index is None when field is not a list
        current_depth starts from 0 at the top.

    In reality, I should just make this functions.
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
        yield from self.visit(self.code, None, None, None)
        self._processed = True

    def visit(self, node, parent, field_name, field_index):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        node_item = yield from visitor(node, parent, field_name, field_index)
        return node_item

    def visit_Module(self, node, parent, field_name, field_index):
        lines = []
        for i, line in enumerate(node.body):
            self.line = line
            line_item = yield from self.visit(line, node, 'body', i)
            lines.append(line_item)
        self.lines = lines

    def generic_visit(self, node, parent, field_name, field_index):
        self.current_depth += 1
        node_item = self.handle_item(node, parent, field_name, field_index)
        if node_item is None:
            return

        fields = OrderedDict()
        for item, field_name, field_index in iter_fields(node):
            fieldset = fields.setdefault(field_name, [])
            field_item = yield from self.visit(item, node, field_name, field_index)
            fieldset.append(field_item)

        node_item['fields'] = fields
        self.current_depth -= 1
        yield node_item
        return node_item

    def handle_item(self, node, parent, field_name, i=None):
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
        return item

def graph_walk(code):
    walker = AstGraphWalker(code)
    return walker.process()
