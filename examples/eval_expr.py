# Evaluates an expression in the context of a configuration. (Here we could
# load a .config as well.)

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])
print conf.eval("(TRACE_IRQFLAGS_SUPPORT || PPC32) && STACKTRACE_SUPPORT")
