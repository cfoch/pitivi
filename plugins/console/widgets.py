# pylint: disable=missing-docstring
# -*- coding: utf-8 -*-
# Pitivi Developer Console
# Copyright (c) 2017, Fabian Orccon <cfoch.fabian@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.
#
# This widget is based on Gedit's pythonconsole plugin
import builtins
import re
import sys
import traceback
from keyword import kwlist

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from utils import display_autocompletion
from utils import FakeOut


class ConsoleWidget(Gtk.ScrolledWindow):
    """
    A GTK+ Widget that displays a Python console.
    This console has access to a set of variables given in a namespace.
    """

    # pylint: disable=too-many-instance-attributes

    __gsignals__ = {
        'grab-focus': 'override',
    }

    DEFAULT_PROMPT = ">>> "
    PROMPT_INDENT = "... "

    DEFAULT_COLOR = Gdk.RGBA(0.51, 0.39, 0.54, 1.0)
    DEFAULT_ERROR_COLOR = Gdk.RGBA(0.96, 0.47, 0.0, 1.0)
    DEFAULT_COMMAND_COLOR = Gdk.RGBA(0.2, 0.39, 0.64, 1.0)
    DEFAULT_NORMAL_COLOR = Gdk.RGBA(0.05, 0.5, 0.66, 1.0)
    DEFAULT_FONT = Pango.FontDescription.from_string("Monospace Regular 12")

    def __init__(self, namespace=None):
        Gtk.ScrolledWindow.__init__(self)
        self.__view = Gtk.TextView()

        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.__view.set_editable(True)
        self.__view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.add(self.__view)

        buf = self.__view.get_buffer()
        self.normal = buf.create_tag("normal")
        self.error = buf.create_tag("error")
        self.command = buf.create_tag("command")

        # Load the default settings

        self.__spaces_pattern = re.compile(r'^\s+')
        if namespace is None:
            self.namespace = {}
        else:
            self.namespace = namespace

        self.block_command = False

        # Init first line
        buf.create_mark("input-line", buf.get_end_iter(), True)
        buf.insert(buf.get_end_iter(), ConsoleWidget.DEFAULT_PROMPT)
        buf.create_mark("input", buf.get_end_iter(), True)

        # Init history
        self.history = ['']
        self.history_pos = 0
        self.current_command = ''
        self.namespace['__history__'] = self.history

        # Set up hooks for standard output.
        self.__stdout = FakeOut(self, self.normal, sys.stdout.fileno())
        self.__stderr = FakeOut(self, self.error, sys.stdout.fileno())

        # Signals
        self.__view.connect("key-press-event", self.__key_press_event_cb)
        buf.connect("mark-set", self.__mark_set_cb)
        buf.connect("insert-text", self.__insert_text_cb)

        # Prompt
        self.prompt = ConsoleWidget.DEFAULT_PROMPT

        self._provider = Gtk.CssProvider()

        self._css_values = {
            "textview": {
                "font-family": ConsoleWidget.DEFAULT_FONT.get_family(),
                "font-size": "%dpt" % int(ConsoleWidget.DEFAULT_FONT.get_size() / Pango.SCALE),
                "font-style": ConsoleWidget.DEFAULT_FONT.get_style().value_nick,
                "font-variant": ConsoleWidget.DEFAULT_FONT.get_variant().value_nick,
                "font-weight": int(ConsoleWidget.DEFAULT_FONT.get_weight())
            },
            "textview > *": {
                "color": ConsoleWidget.DEFAULT_COLOR.to_string()
            }
        }

        self._init_default_colors()

    def set_font(self, font_desc):
        pango_font_desc = Pango.FontDescription.from_string(font_desc)
        self._css_values["textview"]["font-family"] = pango_font_desc.get_family()
        self._css_values["textview"]["font-size"] = "%dpt" % int(pango_font_desc.get_size() / Pango.SCALE)
        self._css_values["textview"]["font-style"] = pango_font_desc.get_style().value_nick
        self._css_values["textview"]["font-variant"] = pango_font_desc.get_variant().value_nick
        self._css_values["textview"]["font-weight"] = int(pango_font_desc.get_weight())
        self._apply_css()
        self.error.set_property("font", font_desc)
        self.command.set_property("font", font_desc)
        self.normal.set_property("font", font_desc)

    def set_color(self, color):
        self._css_values["textview > *"]["color"] = color.to_string()
        self._apply_css()

    def _apply_css(self):
        css = ""
        for css_klass, props in self._css_values.items():
            css += "%s {" % css_klass
            for prop, value in props.items():
                css += "%s: %s;" % (prop, value)
            css += "} "
        css = css.encode("UTF-8")
        self._provider.load_from_data(css)
        Gtk.StyleContext.add_provider(self.__view.get_style_context(),
                                      self._provider,
                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _init_default_colors(self):
        self.error.set_property("foreground-rgba",
                                ConsoleWidget.DEFAULT_ERROR_COLOR)
        self.command.set_property("foreground-rgba",
                                  ConsoleWidget.DEFAULT_COMMAND_COLOR)
        self.normal.set_property("foreground-rgba",
                                 ConsoleWidget.DEFAULT_NORMAL_COLOR)

    def stop(self):
        self.namespace = None

    def __key_press_event_ctrl_return_cb(self, view, unused_event):
        # pylint: disable=invalid-name
        # Get the command
        buf = view.get_buffer()
        inp_mark = buf.get_mark("input")
        inp = buf.get_iter_at_mark(inp_mark)
        cur = buf.get_end_iter()
        line = buf.get_text(inp, cur, False)
        self.current_command = self.current_command + line + "\n"
        self.history_add(line)

        # Prepare the new line
        cur = buf.get_end_iter()
        buf.insert(cur, "\n... ")
        cur = buf.get_end_iter()
        buf.move_mark(inp_mark, cur)

        # Keep indentation of precendent line
        spaces = re.match(self.__spaces_pattern, line)
        if spaces is not None:
            buf.insert(cur, line[spaces.start(): spaces.end()])
            cur = buf.get_end_iter()

        buf.place_cursor(cur)
        GLib.idle_add(self.scroll_to_end)
        return True

    def __key_press_event_return_cb(self, view, event):
        # Get the marks
        buf = view.get_buffer()
        lin_mark = buf.get_mark("input-line")
        inp_mark = buf.get_mark("input")

        # Get the command line
        inp = buf.get_iter_at_mark(inp_mark)
        cur = buf.get_end_iter()
        line = buf.get_text(inp, cur, False)
        self.current_command = self.current_command + line + "\n"
        self.history_add(line)

        # Make the line blue
        lin = buf.get_iter_at_mark(lin_mark)
        buf.apply_tag(self.command, lin, cur)
        buf.insert(cur, "\n")

        cur_strip = self.current_command.rstrip()

        if cur_strip.endswith(":") \
                or (self.current_command[-2:] != "\n\n" and self.block_command):
            # Unfinished block command
            self.block_command = True
            self.prompt = ConsoleWidget.PROMPT_INDENT
        elif cur_strip.endswith("\\"):
            self.prompt = ConsoleWidget.PROMPT_INDENT
        else:
            # Eval the command
            self.__run(self.current_command)
            self.current_command = ''
            self.block_command = False
            self.prompt = ConsoleWidget.DEFAULT_PROMPT

        # Prepare the new line
        cur = buf.get_end_iter()
        buf.move_mark(lin_mark, cur)
        buf.insert(cur, self.prompt)
        cur = buf.get_end_iter()
        buf.move_mark(inp_mark, cur)
        buf.place_cursor(cur)
        GLib.idle_add(self.scroll_to_end)
        return True

    def __key_press_event_down_cb(self, view, event):
        # Next entry from history
        view.stop_emission_by_name("key_press_event")
        self.history_down()
        GLib.idle_add(self.scroll_to_end)
        return True

    def __key_press_event_up_cb(self, view, event):
        # Previous entry from history
        view.stop_emission_by_name("key_press_event")
        self.history_up()
        GLib.idle_add(self.scroll_to_end)
        return True

    def __key_press_event_left_cb(self, view, event):
        # pylint: disable=no-self-use
        modifier_mask = Gtk.accelerator_get_default_mod_mask()
        event_state = event.state & modifier_mask
        buf = view.get_buffer()
        inp = buf.get_iter_at_mark(buf.get_mark("input"))
        cur = buf.get_iter_at_mark(buf.get_insert())
        if inp.compare(cur) == 0:
            if not event_state:
                buf.place_cursor(inp)
            return True
        return False

    def __key_press_event_ctrl_home_cb(self, view, event):
        # pylint: disable=no-self-use
        modifier_mask = Gtk.accelerator_get_default_mod_mask()
        event_state = event.state & modifier_mask
        # Go to the begin of the command instead of the begin of the line
        buf = view.get_buffer()
        it = buf.get_iter_at_mark(buf.get_mark("input"))
        ins = buf.get_iter_at_mark(buf.get_insert())

        while it.get_char().isspace():
            it.forward_char()

        if it.equal(ins):
            it = buf.get_iter_at_mark(buf.get_mark("input"))

        if event_state & Gdk.ModifierType.SHIFT_MASK:
            buf.move_mark_by_name("insert", it)
        else:
            buf.place_cursor(it)
        return True

    def __key_press_event_ctrl_end_cb(self, view, event):
        # pylint: disable=no-self-use
        modifier_mask = Gtk.accelerator_get_default_mod_mask()
        event_state = event.state & modifier_mask
        buf = view.get_buffer()
        it = buf.get_end_iter()
        ins = buf.get_iter_at_mark(buf.get_insert())

        it.backward_char()

        while it.get_char().isspace():
            it.backward_char()

        it.forward_char()

        if it.equal(ins):
            it = buf.get_end_iter()

        if event_state & Gdk.ModifierType.SHIFT_MASK:
            buf.move_mark_by_name("insert", it)
        else:
            buf.place_cursor(it)
        return True

    def __key_press_event_cb(self, view, event):
        modifier_mask = Gtk.accelerator_get_default_mod_mask()
        event_state = event.state & modifier_mask

        ret = False
        if event.keyval == Gdk.KEY_Return and event_state == Gdk.ModifierType.CONTROL_MASK:
            ret = self.__key_press_event_ctrl_return_cb(view, event)
        elif event.keyval == Gdk.KEY_Return:
            ret = self.__key_press_event_return_cb(view, event)
        elif event.keyval == Gdk.KEY_KP_Down or event.keyval == Gdk.KEY_Down:
            ret = self.__key_press_event_down_cb(view, event)
        elif event.keyval == Gdk.KEY_KP_Up or event.keyval == Gdk.KEY_Up:
            ret = self.__key_press_event_up_cb(view, event)
        elif event.keyval == Gdk.KEY_KP_Left or event.keyval == Gdk.KEY_Left or \
                event.keyval == Gdk.KEY_BackSpace:
            ret = self.__key_press_event_left_cb(view, event)
        elif (event.keyval == Gdk.KEY_KP_Home or event.keyval == Gdk.KEY_Home) and \
                event_state == event_state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            # For the console we enable smart/home end behavior incoditionally
            # since it is useful when editing python
            ret = self.__key_press_event_ctrl_home_cb(view, event)
        elif (event.keyval == Gdk.KEY_KP_End or event.keyval == Gdk.KEY_End) and \
                event_state == event_state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            ret = self.__key_press_event_ctrl_end_cb(view, event)
        return ret

    def show_autocompletion(self, command):
        matches, last = self.get_autocompletion_matches(command)
        namespace = {
            "last": last,
            "matches": matches,
            "buf": self.__view.get_buffer(),
            "display_autocompletion": display_autocompletion
        }

        self.__run(
            "display_autocompletion(last, matches, buf)",
            namespace,
            self.namespace)
        if len(matches) > 1:
            self.__refresh_prompt(command)

    def __refresh_prompt(self, text=""):

        buf = self.__view.get_buffer()

        # Get the marks
        lin_mark = buf.get_mark("input-line")
        inp_mark = buf.get_mark("input")

        # Prepare the new line
        cur = buf.get_end_iter()
        buf.move_mark(lin_mark, cur)
        buf.insert(cur, self.prompt)
        cur = buf.get_end_iter()
        buf.move_mark(inp_mark, cur)
        buf.place_cursor(cur)
        self.write(text)

        GLib.idle_add(self.scroll_to_end)
        return True

    def get_autocompletion_matches(self, text):
        """
        Given an input text, return possible matches for autocompletion.
        """
        # pylint: disable=bare-except, eval-used
        identifiers = re.findall(r'[_A-Za-z][\w\.]*\w$', text)
        if identifiers:
            text = identifiers[0]

        pos = text.rfind(".")
        if pos != -1:
            cmd = text[:pos]
        else:
            cmd = text
        namespace = {"cmd": cmd}
        try:
            if pos != -1:
                str_eval = "dir(eval(cmd))"
            else:
                str_eval = "dir()"
            matches = eval(str_eval, namespace, self.namespace)
        except:
            return [], text
        if pos != -1:
            # Get substring after last dot (.)
            rest = text[(pos + 1):]
        else:
            rest = cmd
        # First, assume we are parsing an object.
        matches = [match for match in matches if match.startswith(rest)]

        # If not matches, maybe it is a keyword or builtin function.
        if not matches:
            tmp_matches = kwlist + dir(builtins)
            matches = [
                match for match in tmp_matches if match.startswith(rest)]

        return matches, rest

    def __mark_set_cb(self, buf, it, name):
        input_mark = buf.get_iter_at_mark(buf.get_mark("input"))
        pos = buf.get_iter_at_mark(buf.get_insert())
        self.__view.set_editable(pos.compare(input_mark) != -1)

    def __insert_text_cb(self, buf, it, text, user_data):
        command = self.get_command_line()
        if text == "\t" and command != "":
            # If input text is '\t' and command doesn't start with spaces or tab
            # prevent GtkTextView to insert the text "\t" for autocompletion.
            GObject.signal_stop_emission_by_name(buf, "insert-text")
            self.show_autocompletion(command)

    def get_command_line(self):
        buf = self.__view.get_buffer()
        inp = buf.get_iter_at_mark(buf.get_mark("input"))
        cur = buf.get_end_iter()
        return buf.get_text(inp, cur, False)

    def set_command_line(self, command):
        buf = self.__view.get_buffer()
        mark = buf.get_mark("input")
        inp = buf.get_iter_at_mark(mark)
        cur = buf.get_end_iter()
        buf.delete(inp, cur)
        buf.insert(inp, command)
        self.__view.grab_focus()

    def history_add(self, line):
        if line.strip() != '':
            self.history_pos = len(self.history)
            self.history[self.history_pos - 1] = line
            self.history.append('')

    def history_up(self):
        if self.history_pos > 0:
            self.history[self.history_pos] = self.get_command_line()
            self.history_pos = self.history_pos - 1
            self.set_command_line(self.history[self.history_pos])

    def history_down(self):
        if self.history_pos < len(self.history) - 1:
            self.history[self.history_pos] = self.get_command_line()
            self.history_pos = self.history_pos + 1
            self.set_command_line(self.history[self.history_pos])

    def scroll_to_end(self):
        i = self.__view.get_buffer().get_end_iter()
        self.__view.scroll_to_iter(i, 0.0, False, 0.5, 0.5)
        return False

    def write(self, text, tag=None):
        buf = self.__view.get_buffer()
        if tag is None:
            buf.insert(buf.get_end_iter(), text)
        else:
            buf.insert_with_tags(buf.get_end_iter(), text, tag)

        GLib.idle_add(self.scroll_to_end)

    def __run(self, command, local_namespace=None, global_namespace=None):
        # pylint: disable=eval-used, exec-used, bare-except
        sys.stdout, self.__stdout = self.__stdout, sys.stdout
        sys.stderr, self.__stderr = self.__stderr, sys.stderr

        if local_namespace is None:
            local_namespace = self.namespace
        if global_namespace is None:
            global_namespace = self.namespace
        try:
            try:
                eval_result = eval(command, local_namespace, global_namespace)
                if eval_result is not None:
                    print(eval_result)
            except SyntaxError:
                exec(command, self.namespace)
        except:
            if hasattr(sys, 'last_type') and sys.last_type == SystemExit:
                self.destroy()
            else:
                traceback.print_exc()

        sys.stdout, self.__stdout = self.__stdout, sys.stdout
        sys.stderr, self.__stderr = self.__stderr, sys.stderr
