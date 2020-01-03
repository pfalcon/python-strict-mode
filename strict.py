import sys
import os
import imp
import ast
from types import ModuleType, MappingProxyType


is_runtime = False


# Guess what - can't use logging is some special classes below,
# so mock own logging.
class MiniLog:

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40

    def __init__(self, name):
        self.name = name
        self.level = self.DEBUG

    def setLevel(self, level):
        self.level = level

    def log(self, level, msg):
        if level >= self.level:
            sys.stderr.write("%s: %s\n" % (self.name, msg))

    def debug(self, msg):
        self.log(self.DEBUG, msg)

    def info(self, msg):
        self.log(self.INFO, msg)

    def warning(self, msg):
        self.log(self.WARNING, msg)

    def error(self, msg):
        self.log(self.ERROR, msg)


log = MiniLog("strict")
log.setLevel(log.WARNING)


class StrictModeError(RuntimeError):
    pass


class ROProxy:

    def __init__(self, o):
        # Use obfuscated attribute name to store underlying object.
        # But we could also store it in external mapping, that would
        # be slower, but completely sandboxed.
        self._o__ = o

    def __getattribute__(self, k):
        if k == "_o__":
            return object.__getattribute__(self, k)
        log.debug("getattr: %s.%s" % (self, k))
        res = object.__getattribute__(self._o__, k)
        if k == "__dict__":
            res = MappingProxyType(res)
        return res

    def __setattr__(self, k, v):
        if k == "_o__" and not is_runtime:
            object.__setattr__(self, k, v)
        else:
            log.error("Attempt to set %s.%s to %r" % (self, k, v))
            raise StrictModeError("Attempt to set %s.%s to %r" % (self, k, v))

    def __repr__(self):
        return "<ro %s>" % self._o__


class DictWrap(dict):

    def __init__(self, m):
        self._m__ = m
        super().__init__(m.__dict__)

    def __getitem__(self, k):
        #print("*get", k)
        try:
            return getattr(self._m__, k)
        except AttributeError:
            return super().__getitem__(k)

    def __setitem__(self, k, v):
        global is_runtime
        log.debug("setitem: %s.__dict__.%s=%r" % (self._m__, k, v))
        if is_runtime:
            if k not in self:
                print("Attempt to assign to undeclared global var: %s" % k)
                raise StrictModeError("Attempt to assign to undeclared global var: %s" % k)
        setattr(self._m__, k, v)
        super().__setitem__(k, v)

    def __delitem__(self, k):
        global is_runtime
        if is_runtime:
            if k not in self:
                raise StrictModeError("Attempt to delete a global var: %s" % k)
        delattr(self._m__, k)
        super().__delitem__(k)


class ASTPreprocessor(ast.NodeVisitor):

    def __init__(self):
        self.globals = set()

    def visit_Global(self, node):
        for n in node.names:
            self.globals.add(n)


class ProxyPathFinder:

    def __init__(self, sub):
        self.sub = sub

    def find_spec(self, fullname, path, target_mod):
        spec = self.sub.find_spec(fullname, path, target_mod)
        log.debug("find_spec: %s -> %s" % ((fullname, path, target_mod), spec))
        if spec and spec.loader and spec.origin.endswith(".py"):
            spec.loader = ProxyLoader(spec.loader)
        return spec


def make_module(modname, fname, src, sysname=None):
    log.debug("make_module: %s" % modname)
    shortname = modname.rsplit(".", 1)[-1]
    mod = imp.new_module(shortname)
    mod.__file__ = fname
    mod = populate_module(mod, src)
    sys.modules[sysname or modname] = mod
    return mod


def populate_module(mod, src):
    tree = ast.parse(src)
    #print(ast.dump(tree))

    globc = ASTPreprocessor()
    globc.visit(tree)

#    globals_dict = mod.__dict__
#    globals_dict = DictWrap(globals_dict)
    globals_dict = DictWrap(mod)
    log.debug("newly inited module dict: %s" % globals_dict)

    co = compile(tree, mod.__file__, "exec")
    exec(co, globals_dict)
    #print(globals_dict.keys())

    for v in globc.globals:
        if v not in globals_dict:
            print(
                "Warning: variable '%s' is accessed as global, "
                "but not initialized at the module scope, "
                "initializing to None" % v
            )
            globals_dict[v] = None

    return mod


class ProxyLoader:

    def __init__(self, sub):
        #print("ProxyLoader:", sub)
        self.sub = sub

    def create_module(self, spec):
        return None

    def exec_module(self, mod):
        log.info("exec_module: %s" % mod)
        src = self.sub.get_source(mod.__name__)
        return populate_module(mod, src)


fname = sys.argv[1]

sys.argv.pop(0)
sys.path[0] = os.path.dirname(os.path.abspath(fname))

with open(fname) as f:
    src = f.read()

sys.meta_path[-1] = ProxyPathFinder(sys.meta_path[-1])
sys.path_importer_cache.clear()

mod = make_module("__smain__", fname, src, sysname="__main__")

#print("=== Sealing namespaces ===")

for name, m in sys.modules.items():
#    print(name, m)
    sys.modules[name] = ROProxy(m)

processed = set()

def roproxy_ns(mod):
    if mod in processed:
        return
    processed.add(mod)
    log.info("Sealing %s" % mod)
    for k, v in mod.__dict__.items():
        if isinstance(v, ModuleType):
            mod.__dict__[k] = ROProxy(v)
            roproxy_ns(v)

roproxy_ns(mod)

log.warning("Entering run-time")
#print(mod)
#print(dir(mod))
is_runtime = True
getattr(mod, "__main__")()
