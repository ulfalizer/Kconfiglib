# Prints a tree of all items in the configuration

import kconfiglib
import sys

def print_with_indent(s, indent):
    print (" " * indent) + s

def print_items(items, indent):
    for item in items:
        if item.is_symbol():
            print_with_indent("config {0}".format(item.get_name()), indent)
        elif item.is_menu():
            print_with_indent('menu "{0}"'.format(item.get_title()), indent)
            print_items(item.get_items(), indent + 2)
        elif item.is_choice():
            print_with_indent('choice', indent)
            print_items(item.get_items(), indent + 2)
        elif item.is_comment():
            print_with_indent('comment "{0}"'.format(item.get_text()), indent)

conf = kconfiglib.Config(sys.argv[1])
print_items(conf.get_top_level_items(), 0)
