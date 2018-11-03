#!/usr/bin/env python
import os
import sys
import argparse

information = """
Selects a Kconfig file as source and provides UI frontend

UI Usage:
 -> Double click to select/de-select/edit
 -> use the menus to interact overall

Kconfiglib: https://github.com/ulfalizer/Kconfiglib

Loosely based on https://github.com/CoryXie/SConf

Copyright (c) 2017-2018, Texas Instruments Inc, http://www.ti.com

# License

Copyright (c) 2011-2015, Ulf Magnusson ulfalizer@gmail.com

Copyright (c) 2015-2016, Cory Xie cory.xie@gmail.com

Permission to use, copy, modify, and/or distribute this software for
any purpose with or without fee is hereby granted, provided that
the above copyright notice and this permission notice appear in all
copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA
OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

try:
    # for Python2
    import Tkinter as tk
    import ttk as ttk
    import ScrolledText as tkst
    import tkMessageBox as tkmsgbx
    import tkFileDialog as tkfile
except ImportError:
   # for Python3
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.scrolledtext as tkst
    import tkinter.messagebox as tkmsgbx
    import tkinter.filedialog as tkfile

from kconfiglib import Kconfig, \
    Symbol, Choice, MENU, COMMENT, \
    BOOL, TRISTATE, STRING, INT, HEX, UNKNOWN, \
    expr_value, \
    TRI_TO_STR, standard_config_filename


def usage(parser, err_str):
    """ Helper for printing usage
    """
    print(err_str + '\n')
    parser.print_help()


def main():
    """ Main entry point
    """

    parser = argparse.ArgumentParser(prog=__file__,
                                     description=information,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    optional = parser._action_groups.pop()
    optional.add_argument(
        '-k', '--kfile', help="Root Kconfig File", action="store",
        default='Kconfig')
    optional.add_argument(
        '-o', '--ofile', help="Config File to use", action="store",
        default=standard_config_filename())
    optional.add_argument(
        '-t', '--title', help="Title to use", action="store",
        default='Configuration Utility')
    optional.add_argument(
        '-H', '--header', help="Header to use in config file", action="store",
        default=None)
    optional.add_argument(
        '-C', '--tree_closed', help="Keep the tree closed by default", action="store_true",
        default=False)

    parser._action_groups.append(optional)
    cmd_args, unknown = parser.parse_known_args()

    kfile = cmd_args.kfile

    if len(unknown) == 1:
        kfile = ''.join(unknown)

    if len(unknown) > 1:
        usage("Error: Unknown set of optional arguments: " + str(unknown))
        sys.exit(1)

    cfile = cmd_args.ofile
    title = cmd_args.title
    header = cmd_args.header
    if cmd_args.tree_closed is True:
        default_open = False
    else:
        default_open = True

    kfile = os.path.abspath('.').replace('\\', '/') + "/" + kfile
    if not os.path.exists(kfile):
        usage(parser, 'Error: ' + kfile + ": Does not exist")
        sys.exit(2)

    cfile = os.path.abspath('.').replace('\\', '/') + "/" + cfile

    try:
        conf = Kconfig(kfile)
    except Exception as exc:
        usage(parser, 'Error: Failed to parse ' + kfile)
        raise (exc)
        sys.exit(3)

    if os.path.exists(cfile):
        try:
            conf.load_config(cfile)
        except Exception as exc:
            usage(parser, 'Error: Failed to parse ' + cfile)
            raise (exc)
            sys.exit(3)

    # Now for gui
    root = tk.Tk()

    root.title(title)

    app = MainxMenuConfigApp(root, conf, cfile, header, default_open)

    # And stick around...
    root.mainloop()


class MainxMenuConfigApp():

    def __init__(self, root, conf, cfile, header, default_open=False):
        self.conf = conf
        self.root = root
        self.cfile = cfile
        self.header = header
        self.modified = 0
        self.symbol = None
        self.default_open = default_open
        self.createMenu()
        self.createTree()
        self.populateTree()

    def createMenu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.root.config(menu=self.menu)

        self.filemenu = tk.Menu(self.menu, tearoff=0)
        self.filemenu.add_command(
            label="Save",
            command=self.onSave,
            underline=0,
            accelerator=' ctrl+s')
        self.filemenu.add_command(label="Save As", command=self.onSaveAs)
        self.filemenu.add_separator()
        self.filemenu.add_command(
            label="Reload Config",
            command=self.onReloadConfig)
        self.filemenu.add_command(
            label="Load Config File",
            command=self.onReloadConfigAs)
        self.filemenu.add_separator()
        self.filemenu.add_command(
            label="Quit",
            underline=0,
            command=self.onQuit,
            accelerator=' ctrl+q')
        self.menu.add_cascade(label="File", underline=0, menu=self.filemenu)

        self.helpmenu = tk.Menu(self.menu, tearoff=0)
        self.helpmenu.add_command(
            label="Current Symbol Help",
            command=self.onHelp,
            underline=15,
            accelerator=' ctrl+h')
        self.helpmenu.add_command(
            label="Find Symbol",
            command=self.onFind,
            underline=0,
            accelerator=' ctrl+f')
        self.menu.add_cascade(
            label="Symbol Information",
            underline=0,
            menu=self.helpmenu)
        self.menu.add_command(
            label="About",
            command=self.onAbout,
            underline=0)

        self.root.bind_all('<Control-Key-s>', self.onSave)
        self.root.bind_all('<Control-Key-q>', self.onQuit)
        self.root.bind_all('<Control-Key-h>', self.onHelp)
        self.root.bind_all('<Control-Key-f>', self.onFind)
        self.root.protocol("WM_DELETE_WINDOW", self.onQuit)

    def onAbout(self, ev=None):
        self.w = HelpPopupWindow(self.root, "About", information)
        self.root.wait_window(self.w.top)
        return

    def onSave(self, ev=None):
        try:
            if self.header is None:
                self.conf.write_config(self.cfile)
            else:
                self.conf.write_config(self.cfile, header=self.header)
        except Exception as exc:
            tkmsgbx.showerror(
                "Fail save",
                "Failed to Save configuration to" +
                self.cfile +
                "!" + str(exc))
            raise(exc)
            return

        tkmsgbx.showinfo(
            "Saved config",
            "Configurations Saved to " +
            self.cfile +
            "!")
        self.modified = 0
        return

    def onSaveAs(self):
        self.cfile = tkfile.asksaveasfilename(
            title="Select Config file to save to")
        self.onSave()
        return

    def onQuit(self, ev=None):
        if self.modified != 0:
            if tkmsgbx.askyesno(
                    "Save Configuration?", "Configuration has been modified: Save this config?"):
                self.onSave()
        self.root.quit()
        return

    def onHelp(self, ev=None, sym=None):
        if sym is None:
            sym = self.symbol
        if sym is None:
            return
        help_txt = sym.nodes[0].help
        info_txt = sym.__str__()
        if help_txt is None:
            help_txt = "No Help defined\n"
        information = "Help Text:\n" + help_txt + \
            "Symbol Information:\n" + info_txt
        self.w = HelpPopupWindow(self.root, sym.name, information)
        self.root.wait_window(self.w.top)
        return

    def onFind(self, ev=None):
        self.pop = TextPopupWindow(self.root, "Enter Name of Symbol", "")
        self.root.wait_window(self.pop.top)
        if self.pop.v is True:
            if self.pop.value in self.conf.syms:
                symbol = self.conf.syms[self.pop.value]
            else:
                symbol = None
            if symbol is None:
                tkmsgbx.showerror(
                    "Search Failed!",
                    "Did not find symbol '" +
                    self.pop.value +
                    "'!")
            else:
                self.onHelp(sym=symbol)
        return

    def onReloadConfig(self):
        if os.path.exists(self.cfile):
            try:
                self.conf.load_config(self.cfile)
                tkmsgbx.showinfo(
                    "config reloaded!",
                    "Config reloaded from:" +
                    self.cfile +
                    "!")
                self.reCreateTree()
                self.modified = 0
            except Exception as exc:
                tkmsgbx.showerror(
                    "Fail parse config!",
                    "Config file:" +
                    self.cfile +
                    " - Parse error!")
                raise (exc)
        else:
            tkmsgbx.showerror(
                "Fail reload config!",
                "Config file:" +
                self.cfile +
                " - does not exist!")

        return

    def onReloadConfigAs(self):
        self.cfile = tkfile.askopenfilename(
            title="Select Config file to load from")
        self.onReloadConfig()
        return

    def onSelection(self, event):
        mitem = self.tree.focus()
        values = self.tree.item(mitem, "values")
        if (values):
            symbol = self.conf.syms[values[0]]
            if (symbol):
                self.symbol = symbol
        return

    def createTree(self):
        self.tree = ttk.Treeview(
            self.root,
            selectmode="browse",
            columns=("name",
                     "desc",
                     "value",
                     "type"),
            displaycolumns=("desc",
                            "value",
                            "type"),
            height=30)
        ysb = ttk.Scrollbar(orient=tk.VERTICAL, command=self.tree.yview)
        xsb = ttk.Scrollbar(orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.tree.heading('#0', text='Configuration', anchor='w')
        self.tree.column("#0", minwidth=0, width=300, stretch=True)

        self.tree.heading("name", text="Name")
        self.tree.column("name", minwidth=0, width=80, stretch=True)

        self.tree.heading("desc", text="Description")
        self.tree.column("desc", minwidth=0, width=200, stretch=True)

        self.tree.heading("value", text="Value")
        self.tree.column("value", minwidth=0, width=50, stretch=True)

        self.tree.heading("type", text="Type")
        self.tree.column("type", minwidth=0, width=40, stretch=True)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky='ns')
        xsb.grid(row=1, column=0, sticky='ew')
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.root.grid()

        self.tree.bind("<Double-1>", self.onDoubleClick)
        self.tree.bind("<Return>", self.onDoubleClick)
        self.tree.bind("<space>", self.onDoubleClick)
        self.tree.bind("<<TreeviewSelect>>", self.onSelection)

    def populateTree(self):
        self.nodes = self.conf.top_node.list
        self.odd = 0
        self.add_subr_items(self.nodes, root_tree=True)
        self.tree.tag_configure(
            'oddn',
            background='antique white',
            foreground='wheat4')
        self.tree.tag_configure(
            'oddy',
            background='linen',
            foreground='green3')
        self.tree.tag_configure(
            'oddm',
            background='linen',
            foreground='green4')
        self.tree.tag_configure(
            'oddv',
            background='linen',
            foreground='blue')

        self.tree.tag_configure(
            'evenn',
            background='light goldenrod yellow',
            foreground='wheat4')
        self.tree.tag_configure(
            'eveny',
            background='light yellow',
            foreground='green3')
        self.tree.tag_configure(
            'evenm',
            background='light yellow',
            foreground='green3')
        self.tree.tag_configure(
            'evenv',
            background='light yellow',
            foreground='blue')

        self.tree.tag_configure('menu', background='bisque2')
        self.tree.tag_configure(
            'choice',
            background='lavender',
            foreground='DarkOrange4')
        self.tree.tag_configure(
            'comment',
            background='light blue',
            foreground='purple3')

    def value_str(self, sc):

        tags = self.tag_str(sc)
        if sc.type in (STRING, INT, HEX):
            return "{}v".format(tags), "{}".format(sc.str_value)

        # BOOL or TRISTATE

        # The choice mode is an upper bound on the visibility of choice symbols, so
        # we can check the choice symbols' own visibility to see if the choice is
        # in y mode
        if isinstance(sc, Symbol) and sc.choice and sc.visibility == 2:
            # For choices in y mode, print '<--' next to the selected symbol
            if sc.choice.selection is sc:
                return "{}y".format(tags), "<--"
            else:
                return "{}n".format(tags), "   "

        tri_val_str = ("n", "M", "y")[sc.tri_value]
        tri_val_tag = ("n", "m", "y")[sc.tri_value]

        final_tag = tags + tri_val_tag
        if len(sc.assignable) == 1:
            # Pinned to a single value
            return final_tag, "-{}-".format(tri_val_str)

        if sc.type == BOOL:
            return final_tag, "[{}]".format(tri_val_str)

        if sc.type == TRISTATE:
            if sc.assignable == (1, 2):
                # m and y available
                # Gets a bit confusing with .format()
                return final_tag, "{" + tri_val_str + "}"
            return final_tag, "<{}>".format(tri_val_str)

    def get_value(self, sym):
        return sym.str_value

    def is_symbol(self, sym):
        if isinstance(sym, Symbol):
            return True
        else:
            return False

    def is_choice(self, sym):
        if isinstance(sym, Choice):
            return True
        else:
            return False

    def tag_str(self, sc):
        if self.odd is 0:
            tag = 'even'
            self.odd = 1
        else:
            tag = 'odd'
            self.odd = 0

        if sc == MENU:
            return 'menu'
        if sc == COMMENT:
            return 'comment'

        if isinstance(sc, Symbol):
            if self.odd is 1:
                return 'odd'
            else:
                return 'even'

        if isinstance(sc, Choice):
            return 'choice'

        return ''

    def type_str(self, sc):
        if sc.type == BOOL:
            return 'bool'
        if sc.type == TRISTATE:
            return 'tristate'
        if sc.type is HEX:
            return 'hex'
        if sc.type is INT:
            return 'integer'
        if sc.type is STRING:
            return 'string'
        return 'unknown type'

    def add_str(self, node, parent, default_open):
        if not node.prompt:
            return parent

        # Even for menu nodes for symbols and choices, it's wrong to check
        # Symbol.visibility / Choice.visibility here. The reason is that a symbol
        # (and a choice, in theory) can be defined in multiple locations, giving it
        # multiple menu nodes, which do not necessarily all have the same prompt
        # visibility. Symbol.visibility / Choice.visibility is calculated as the OR
        # of the visibility of all the prompts.
        prompt, prompt_cond = node.prompt
        if not expr_value(prompt_cond):
            return parent

        # Handle Symbols and choices
        sc = node.item

        if node.item == MENU:
            s = 'menu "{0}"'.format(prompt)
            tags = self.tag_str(sc)
            parent = self.tree.insert(
                parent, "end", text=s, tags=(
                    tags,), open=default_open)
            return parent

        if node.item == COMMENT:
            s = '->{0}<-'.format(prompt)
            tags = self.tag_str(sc)
            self.tree.insert(
                parent, "end", text=s, tags=(
                    tags,), open=default_open)
            return parent

        if sc.type == UNKNOWN:
            return parent

        if sc.name is not None:
            name = '{0}'.format(sc.name)
        else:
            name = ''
        if isinstance(sc, Symbol):
            tags, val = self.value_str(sc)
            t = self.type_str(sc)
            self.tree.insert(parent, "end", text=name,
                             values=[name,
                                     prompt,
                                     val,
                                     t],
                             tags=(tags,),
                             open=default_open)
        if isinstance(sc, Choice):
            s = 'choice "{0}"'.format(prompt)
            tags = self.tag_str(sc)
            parent = self.tree.insert(
                parent, "end", text=s, tags=(
                    tags,), open=default_open)
        return parent

    def add_subr_items(self, node, parent="", root_tree=False):
        oparent = parent
        while node:
            parent = self.add_str(node, parent, self.default_open)
            if node.list:
                self.add_subr_items(node.list, parent)
            if not oparent is None:
                parent = oparent
            node = node.next

    def search_for_item(self, name, item=None):
        children = self.tree.get_children(item)
        for child in children:
            nameval = self.tree.set(child, "name")
            if nameval == name:
                return child
            else:
                res = self.search_for_item(name, child)
                if res:
                    return res
        return None

    def reCreateTree(self, symbol=None):
        if not symbol is None:
            nameval = symbol.name
        children = self.tree.get_children(None)
        for child in children:
            self.tree.delete(child)
        self.populateTree()
        if not symbol is None:
            mitem = self.search_for_item(nameval)
            self.tree.focus(mitem)

    def onDoubleClick(self, event):
        mitem = self.tree.identify('item', event.x, event.y)
        nameval = self.tree.set(mitem, "name")
        try:
            symbol = self.conf.syms[nameval]
        except KeyError as kerr:
            symbol is None

        if symbol is None:
            return

        if self.is_symbol(symbol) or self.is_choice(symbol):
            text = symbol.nodes[0].help
        elif symbol.is_menu():
            text = symbol.help
        else:
            # Comment
            text = symbol.nodes[0].prompt
        if text is not None and "warning:" in text.lower():
            text = text.split("warning:", 1)[-1]
            text = text.replace('\n', ' ').replace('\r', ' ').lstrip().rstrip()
            if not tkmsgbx.askyesno("CONFIG WARNING", "The '" + symbol.name
                                    + "' config has the following warning:\n" + text + ".\nProceed?"):
                return

        self.modified = 1

        # If we have a int/hex/string type.. just edit it and update.
        if symbol.type in (HEX, INT, STRING):
            self.pop = TextPopupWindow(
                self.root,
                symbol.name,
                self.get_value(symbol))
            self.root.wait_window(self.pop.top)
            if self.pop.v is True:
                symbol.set_value(self.pop.value)
                self.tree.set(mitem, "value", self.get_value(symbol))
            return

        # Bool type, we just recreate the tree.
        if symbol.type is BOOL or symbol.type is TRISTATE and not 1 in symbol.assignable:
            if (self.is_choice(symbol) and len(
                    symbol.get_parent().get_items()) == 1):
                return
            if (self.get_value(symbol) == "y"):
                symbol.set_value("n")
            else:
                symbol.set_value("y")
            self.reCreateTree(symbol)
            return

        # Tristate.. we will try and update the tree the same way.
        if symbol.type is BOOL or symbol.type is TRISTATE and 1 in symbol.assignable:
            nono = False
            if (self.is_choice(symbol) and len(
                    symbol.get_parent().get_items()) == 1):
                nono = True
            # 'y'->'m'->'n'->'y'->'m'->'n'->...
            if (self.get_value(symbol) == "y"):
                symbol.set_value("m")
            elif (self.get_value(symbol) == "m"):
                symbol.set_value("n")
            else:
                symbol.set_value("y")

            self.reCreateTree(symbol)
        return


class HelpPopupWindow(object):

    def __init__(self, root, symbol_name, help_txt):
        top = self.top = tk.Toplevel(root)
        top.title(symbol_name)
        self.l = tk.Label(top, text=help_txt)
        self.l.pack()
        self.b = tk.Button(top, text='Ok', command=self.cleanup)
        self.b.pack()

    def cleanup(self):
        self.top.destroy()


class TextPopupWindow(object):

    def __init__(self, root, config, value):
        self.top = top = tk.Toplevel(root)
        self.l = tk.Label(top, text=config)
        self.l.grid(row=0, column=0)
        self.e = tk.Entry(top)
        self.e.delete(0, tk.END)
        self.e.insert(0, value)
        self.e.grid(row=0, column=1)
        self.b = tk.Button(top, text='Submit', command=self.Submit)
        self.b.grid(row=1, column=0)
        self.c = tk.Button(top, text='Cancel', command=self.Cancel)
        self.c.grid(row=1, column=1)
        self.v = False
        self.top.grid()
        self.top.wm_title("Set " + config)

    def Submit(self):
        self.value = self.e.get()
        self.v = True
        self.top.destroy()

    def Cancel(self):
        self.v = False
        self.top.destroy()


if __name__ == "__main__":
    main()

# Format via !autopep8 -i -a %
# vim: et:ts=4
