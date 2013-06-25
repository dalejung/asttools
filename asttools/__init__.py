import ast

class testcontext(object):
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

with_1 = """
with testcontext():
    pass
"""

code = ast.parse(with_1)
w = code.body[0]

with_2 = """
with testcontext():
    v1 = 1
    v2 = 1
    dale = 123
    bob = 'bob'
"""

code = ast.parse(with_2)
w = code.body[0]
print ast.dump(w)

# executing a subset of a code block
new_module = ast.parse('')
new_module.body = w.body[1:]
c = compile(new_module, '<string>', 'exec')
ns = {}
exec c in ns
print ns.keys()
