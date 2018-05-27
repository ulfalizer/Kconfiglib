# Prints all symbols, choices, menus, and comments that reference a symbol with
# a particular name in any of their properties or property conditions.
# Demonstrates expression fetching and walking.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/find_symbol.py SCRIPT_ARG=<name>
#
# Example output for SCRIPT_ARG=X86:
#
#
#   Found 452 locations that reference 'X86':
#   
#   ========== Location 1 (init/Kconfig:1122) ==========
#   
#   config SGETMASK_SYSCALL
#           bool
#           prompt "sgetmask/ssetmask syscalls support" if EXPERT
#           default PARISC || MN10300 || BLACKFIN || M68K || PPC || MIPS || X86 || SPARC || CRIS || MICROBLAZE || SUPERH
#           help
#             sys_sgetmask and sys_ssetmask are obsolete system calls
#             no longer supported in libc but still enabled by default in some
#             architectures.
#             
#             If unsure, leave the default option here.
#   
#   ---------- Parent 1 (init/Kconfig:1091)  ----------
#   
#   menuconfig EXPERT
#           bool
#           prompt "Configure standard kernel features (expert users)"
#           select DEBUG_KERNEL
#           help
#             This option allows certain base kernel options and settings
#             to be disabled or tweaked. This is for specialized
#             environments which can tolerate a "non-standard" kernel.
#             Only use this if you really know what you are doing.
#   
#   ---------- Parent 2 (init/Kconfig:39)  ----------
#   
#   menu "General setup"
#   
#   ========== Location 2 (arch/Kconfig:28) ==========
#   
#   config OPROFILE_EVENT_MULTIPLEX
#           bool
#           prompt "OProfile multiplexing support (EXPERIMENTAL)" if OPROFILE && X86
#           default "n" if OPROFILE && X86
#           help
#             The number of hardware counters is limited. The multiplexing
#             feature enables OProfile to gather more events than counters
#             are provided by the hardware. This is realized by switching
#             between events at a user specified time interval.
#             
#             If unsure, say N.
#   
#   ---------- Parent 1 (arch/Kconfig:15)  ----------
#   
#   config OPROFILE
#   ... (tons more lines)

from kconfiglib import Kconfig, Symbol, Choice, MENU, COMMENT, NOT
import sys

def expr_contains_sym(expr, sym_name):
    """
    Returns True if a symbol (or choice, though that's unlikely) with name
    'sym_name' appears in the expression 'expr', and False otherwise.

    Note that "foo" is represented as a constant symbol, like in the C
    implementation.
    """
    # Choice symbols have a Choice instance propagated to the conditions of
    # their properties, so we need this test rather than
    # isinstance(expr, Symbol)
    if not isinstance(expr, tuple):
        return expr.name == sym_name

    if expr[0] == NOT:
        return expr_contains_sym(expr[1], sym_name)

    # AND, OR, or relation
    return expr_contains_sym(expr[1], sym_name) or \
           expr_contains_sym(expr[2], sym_name)

def sc_references_sym(sc, sym_name):
    """
    Returns True if a symbol with name 'sym_name' appears in any of the
    properties or property conditions of the Symbol or Choice 'sc', and False
    otherwise.
    """
    # Search defaults
    for default, cond in sc.defaults:
        if expr_contains_sym(default, sym_name) or \
           expr_contains_sym(cond, sym_name):
            return True

    if isinstance(sc, Symbol):
        # Search selects
        for select, cond in sc.selects:
            if select.name == sym_name or \
               expr_contains_sym(cond, sym_name):
                return True

        # Search implies
        for imply, cond in sc.implies:
            if imply.name == sym_name or \
               expr_contains_sym(cond, sym_name):
                return True

        # Search ranges
        for low, high, cond in sc.ranges:
            if low.name == sym_name or \
               high.name == sym_name or \
               expr_contains_sym(cond, sym_name):
                return True

    return False

def node_references_sym(node, sym_name):
    """
    Returns True if a symbol with name 'sym_name' appears in the prompt
    condition of the MenuNode 'node' or in any of the properties of a
    symbol/choice stored in the menu node, and False otherwise.

    For MENU menu nodes, also searches the 'visible if' condition.

    Note that prompts are always stored in menu nodes. This is why a symbol can
    be defined in multiple locations and have a different prompt in each
    location. For MENU and COMMENT menu nodes, the prompt holds the menu title
    or comment text. This organization matches the C implementation.
    """
    if node.prompt:
        # Search the prompt condition
        if expr_contains_sym(node.prompt[1], sym_name):
            return True

    if isinstance(node.item, (Symbol, Choice)):
        # Search symbol or choice
        return sc_references_sym(node.item, sym_name)

    if node.item == MENU:
        # Search the 'visible if' condition
        return expr_contains_sym(node.visibility, sym_name)

    # Comments are already handled by searching the prompt condition, because
    # 'depends on' gets propagated to it. This is why we don't need to look at
    # the direct dependencies for MENU either.

def nodes_referencing_sym(node, sym_name):
    """
    Returns a list of all menu nodes in the menu tree rooted at 'node' that
    reference a symbol with name 'sym_name' in any of their properties. Also
    checks the properties of any symbols or choices contained in the menu
    nodes.
    """
    res = []

    while node:
        if node_references_sym(node, sym_name):
            res.append(node)

        if node.list:
            res.extend(nodes_referencing_sym(node.list, sym_name))

        node = node.next

    return res

# find_undefined.py makes use nodes_referencing_sym(), so allow use to be
# imported
if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit('Pass symbol name (without "CONFIG_" prefix) with SCRIPT_ARG=<name>')

    sym_name = sys.argv[2]

    kconf = Kconfig(sys.argv[1])
    nodes = nodes_referencing_sym(kconf.top_node, sym_name)

    if not nodes:
        sys.exit("No reference to '{}' found".format(sym_name))

    print("Found {} locations that reference '{}':\n".format(len(nodes), sym_name))

    for i, node in enumerate(nodes, 1):
        print("========== Location {} ({}:{}) ==========\n".format(i, node.filename, node.linenr))
        print(node)

        parent_i = 0

        # Print the parents of the menu node too
        while True:
            node = node.parent
            if node is kconf.top_node:
		# Don't print the top node. Would say something like the
		# following, which isn't that interesting:
                #
		#   menu "Linux/$ARCH $KERNELVERSION Kernel Configuration"
                break

            parent_i += 1

            print("---------- Parent {} ({}:{})  ----------\n"
                  .format(parent_i, node.filename, node.linenr))
            print(node)
