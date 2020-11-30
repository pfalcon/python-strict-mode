import sys
import os
import imp
from types import ModuleType, MappingProxyType


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
        if k == "_o__":
            object.__setattr__(self, k, v)
        else:
            log.error("Attempt to set %s.%s to %r" % (self, k, v))
            raise StrictModeError("Attempt to set %s.%s to %r" % (self, k, v))

    def __repr__(self):
        return "<ro %s>" % self._o__


fname = sys.argv[1]

sys.argv.pop(0)
sys.path[0] = os.path.dirname(os.path.abspath(fname))
name = fname.rsplit(".", 1)[0]

with open(fname) as f:
    src = f.read()

mod = imp.new_module("__smain__")
globals_dict = mod.__dict__
print(globals_dict)
globals_dict["__file__"] = fname
sys.modules["__main__"] = mod
#, "__name__": "__smain__"}

co = compile(src, fname, "exec")
exec(co, globals_dict)
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

globals_dict["__main__"]()
