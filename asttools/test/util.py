def preamble():
    from earthdragon.typecheck import typecheck_enable
    typecheck_enable('asttools')

def run_in_place(func):
    func()
