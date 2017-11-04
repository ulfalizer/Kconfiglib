# TODO: explain, screenshot

from kconfiglib import Kconfig, \
                       Symbol, Choice, MENU, COMMENT, \
                       BOOL, TRISTATE, STRING, INT, HEX, UNKNOWN, \
                       expr_value, \
                       TRI_TO_STR, STR_TO_TRI
import readline
import sys

# Python 2/3 compatibility hack
if sys.version_info[0] < 3:
    input = raw_input

def indent_print(s, indent):
    print((" " * indent) + s)

def value_str(sc):
    if sc.type in (STRING, INT, HEX):
        return "({})".format(sc.str_value)

    # BOOL or TRISTATE

    if isinstance(sc, Symbol) and sc.choice and sc.choice.tri_value == 2:
        # For choices in y mode, print '-->' next to the selected symbol
        if sc.choice.selection is sc:
            return "-->"
        return "   "

    val_str = {0: " ", 1: "M", 2: "*"}[sc.tri_value]

    if len(sc.assignable) == 1:
        return "-{}-".format(val_str)

    if sc.type == BOOL:
        return "[{}]".format(val_str)

    if sc.type == TRISTATE:
        if sc.assignable[0] == 1:
            return "{" + val_str + "}"  # Gets a bit confusing with .format()
        return "<{}>".format(val_str)

def node_str(node):
    if not node.prompt:
        return ""

    prompt, prompt_cond = node.prompt
    if not expr_value(prompt_cond):
        return ""

    if node.item == MENU:
        return "    " + prompt

    if node.item == COMMENT:
        return "    *** {} ***".format(prompt)

    # Symbol or Choice

    sc = node.item

    if sc.type == UNKNOWN:
        # Skip symbols defined without a type
        return ""

    # {:3} sets the field width to three. Gives nice alignment for empty string
    # values.
    return "{:3} {} ({})".format(value_str(sc), prompt, sc.name)

def print_menuconfig_nodes(node, indent):
    while node is not None:
        string = node_str(node)
        if string:
            indent_print(string, indent)

        if node.list is not None:
            print_menuconfig_nodes(node.list, indent + 8)

        node = node.next

def print_menuconfig(kconf):
    # Print the expanded mainmenu text at the top. This is the same as
    # kconf.top_node.prompt[0], but with variable references expanded.
    print("\n======== {} ========\n".format(kconf.mainmenu_text))

    print_menuconfig_nodes(kconf.top_node.list, 0)
    print("")

def get_value_from_user(sc):
    if not sc.visibility:
        print(sc.name + " is not currently visible")
        return False

    prompt = "Value for {}".format(sc.name)
    if sc.type in (BOOL, TRISTATE):
        prompt += " (available: {})" \
                  .format(", ".join([TRI_TO_STR[val] for val in sc.assignable]))
    prompt += ": "

    val_str = input(prompt).strip()
    if sc.type in (BOOL, TRISTATE):
        if val_str not in STR_TO_TRI:
            print("'{}' is not a valid tristate value".format(val_str))
            return False

        # I was thinking of having set_value() accept "n", "m", "y" as well as
        # a convenience for BOOL / TRISTATE symbols. Consistently using 0, 1, 2
        # makes the format clearer though. That's the best format for
        # everything except readability (where it isn't horrible either).
        val = STR_TO_TRI[val_str]
    else:
        val = val_str

    # Automatically add a "0x" prefix for hex symbols, like the menuconfig
    # interface does. This isn't done when loading .config files, hence why
    # set_value() doesn't do it automatically.
    if sc.type == HEX and not val.startswith(("0x", "0X")):
        val = "0x" + val

    # Let Kconfiglib itself print a warning here if the value is invalid. We
    # could also disable warnings temporarily with
    # kconf.disable_warnings() / kconf.enable_warnings() and print our own
    # warning.
    return sc.set_value(val)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: menuconfig.py <Kconfig file>")

    # Load Kconfig configuration files
    kconf = Kconfig(sys.argv[1])

    # Print the initial configuration tree
    print_menuconfig(kconf)

    while True:
        try:
            cmd = input('Enter a symbol/choice name, "load_config", or "write_config" (or press CTRL+D to exit): ') \
                  .strip()
        except EOFError:
            print("")
            break

        if cmd == "load_config":
            config_filename = input(".config file to load: ")

            try:
                kconf.load_config(config_filename)
            except IOError as e:
                # Print the (spammy) error from Kconfiglib itself
                print(e.message + "\n")
            else:
                print("Configuration loaded from " + config_filename)

            print_menuconfig(kconf)
            continue

        if cmd == "write_config":
            config_filename = input("To this file: ")

            try:
                kconf.write_config(config_filename)
            except IOError as e:
                print(e.message)
            else:
                print("Configuration written to " + config_filename)

            continue

        # Assume 'cmd' is the name of a symbol or choice if it isn't one of the
        # commands above, prompt the user for a value for it, and print the new
        # configuration tree

        if cmd in kconf.syms:
            if get_value_from_user(kconf.syms[cmd]):
                print_menuconfig(kconf)

            continue

        if cmd in kconf.named_choices:
            if get_value_from_user(kconf.named_choices[cmd]):
                print_menuconfig(kconf)

            continue

        print("No symbol/choice named '{}' in the configuration"
              .format(cmd))
