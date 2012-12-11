# Does a case-insensitive search for a string in the help texts for symbols and
# choices and the titles of menus and comments. Prints the matching items
# together with their locations and the matching text. Used like
#
#  $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/help_grep.py SCRIPT_ARG=<search text>

import kconfiglib
import sys

if len(sys.argv) < 3:
    print 'Pass search string with SCRIPT_ARG="search string"'
    sys.exit(1)
search_string = sys.argv[2].lower()

conf = kconfiglib.Config(sys.argv[1])

for item in conf.get_symbols() +\
            conf.get_choices() + conf.get_menus() + conf.get_comments():
    if item.is_symbol() or item.is_choice():
        text = item.get_help()
    elif item.is_menu():
        text = item.get_title()
    else:
        # Comment
        text = item.get_text()

    # Case-insensitive search
    if text is not None and search_string in text.lower():
        if item.is_symbol() or item.is_choice():
            # Indent lines in help text. (There might be a nicer way. :)
            text = "\n".join(["  " + s for s in text.splitlines()])

            # Don't worry about symbols/choices defined in multiple locations to
            # keep things simple
            fname, linenr = item.get_def_locations()[0]
            if item.is_symbol():
                print "config {0} at {1}:{2}:\n{3}".\
                      format(item.get_name(), fname, linenr, text)
            elif item.is_choice():
                print "choice at {0}:{1}:\n{2}".\
                      format(fname, linenr, text)

        else:
            # Menu or comment
            fname, linenr = item.get_location()
            if item.is_menu():
                print 'menu "{0}" at {1}:{2}'.\
                      format(text, fname, linenr)
            else:
                # Comment
                print 'comment "{0}" at {1}:{2}'.\
                      format(text, fname, linenr)
