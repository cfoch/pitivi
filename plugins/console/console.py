"""Python console for inspecting and interacting with Pitivi and the project."""
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
from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Peas
from widgets import ConsoleWidget

from pitivi.dialogs.prefs import PreferencesDialog


class Console(GObject.GObject, Peas.Activatable):
    """Plugin which adds a Python console for development purposes."""
    __gtype_name__ = 'ConsolePlugin'
    object = GObject.Property(type=GObject.Object)

    MENU_LABEL = "Developer Console"
    TITLE = "Pitivi Console"

    def __init__(self):
        GObject.GObject.__init__(self)
        self.window = None
        self.terminal = None
        self.menu_item = None
        self.app = None

    def do_activate(self):
        api = self.object
        self.app = api.app
        try:
            self.app.settings.addConfigSection("console")
            self.app.settings.addConfigOption(attrname="consoleColor",
                                              section="console",
                                              key="console-color",
                                              notify=True,
                                              default=ConsoleWidget.DEFAULT_COLOR)
            self.app.settings.addConfigOption(attrname="consoleErrorColor",
                                              section="console",
                                              key="console-error-color",
                                              notify=True,
                                              default=ConsoleWidget.DEFAULT_ERROR_COLOR)
            self.app.settings.addConfigOption(attrname="consoleCommandColor",
                                              section="console",
                                              key="console-command-color",
                                              notify=True,
                                              default=ConsoleWidget.DEFAULT_COMMAND_COLOR)
            self.app.settings.addConfigOption(attrname="consoleNormalColor",
                                              section="console",
                                              key="console-normal-color",
                                              notify=True,
                                              default=ConsoleWidget.DEFAULT_NORMAL_COLOR)
            self.app.settings.addConfigOption(attrname="consoleFont",
                                              section="console",
                                              key="console-font",
                                              notify=True,
                                              default=ConsoleWidget.DEFAULT_FONT.to_string())
        # pylint: disable=broad-except
        except Exception:
            pass

        try:
            self.app.settings.reload_attribute_from_file("console",
                                                         "consoleColor")
            self.app.settings.reload_attribute_from_file("console",
                                                         "consoleErrorColor")
            self.app.settings.reload_attribute_from_file("console",
                                                         "consoleCommandColor")
            self.app.settings.reload_attribute_from_file("console",
                                                         "consoleNormalColor")
            self.app.settings.reload_attribute_from_file("console",
                                                         "consoleFont")
        # pylint: disable=broad-except
        except Exception:
            pass

        PreferencesDialog.addSection("console", _("Console"))
        PreferencesDialog.addColorPreference(attrname="consoleColor",
                                             label=_("Color"),
                                             description=_("Color."),
                                             section="console")
        PreferencesDialog.addColorPreference(attrname="consoleErrorColor",
                                             label=_("Error color"),
                                             description=_("Error color."),
                                             section="console")
        PreferencesDialog.addColorPreference(attrname="consoleCommandColor",
                                             label=_("Command color"),
                                             description=_("Command color."),
                                             section="console")
        PreferencesDialog.addColorPreference(attrname="consoleNormalColor",
                                             label=_("Normal color"),
                                             description=_("Normal color."),
                                             section="console")
        PreferencesDialog.addFontPreference(attrname="consoleFont",
                                            label=_("Font"),
                                            description=_("Select a font."),
                                            section="console")

        if self.app.gui.preferences_dialog is not None:
            self.app.gui.preferences_dialog.add_settings_section("console")

        namespace = {"app": self.app}
        self._setup_dialog(namespace)
        self.add_menu_item()
        self.menu_item.show()

    def do_deactivate(self):
        try:
            PreferencesDialog.removeSection("console")
        # pylint: disable=broad-except
        except Exception:
            pass
        self.window.destroy()
        self.remove_menu_item()
        self.window = None
        self.terminal = None
        self.menu_item = None
        self.app = None

    def show_console(self):
        """Shows the Console widget."""
        self.window.show_all()
        self.window.set_keep_above(True)

    def add_menu_item(self):
        """Insert a menu item into the Pitivi menu"""
        menu = self.app.gui.builder.get_object("menu")
        self.menu_item = Gtk.MenuItem.new_with_label(Console.MENU_LABEL)
        self.menu_item.connect("activate", self.__activate_cb)
        menu.add(self.menu_item)

    def remove_menu_item(self):
        """Remove a menu item from the Pitivi menu"""
        menu = self.app.gui.builder.get_object("menu")
        menu.remove(self.menu_item)

    def _setup_dialog(self, namespace):
        self.window = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.terminal = ConsoleWidget(namespace)

        self._init_colors()
        self.terminal.set_font(self.app.settings.consoleFont)
        self._connect_settings_signals()

        self.window.set_default_size(600, 400)
        self.window.set_title(Console.TITLE)
        self.window.add(self.terminal)
        self.window.connect("delete-event", self.__delete_event_cb)

    def _init_colors(self):
        """Sets the colors from Pitivi settings."""
        self.terminal.error.set_property("foreground-rgba",
                                         self.app.settings.consoleErrorColor)
        self.terminal.command.set_property("foreground-rgba",
                                           self.app.settings.consoleCommandColor)
        self.terminal.normal.set_property("foreground-rgba",
                                          self.app.settings.consoleNormalColor)
        self.terminal.set_color(self.app.settings.consoleColor)

    def _connect_settings_signals(self):
        """Connects the settings' signals."""
        self.app.settings.connect("consoleColorChanged", self.__colorChangedCb,
                                  self.terminal)
        self.app.settings.connect("consoleErrorColorChanged",
                                  self.__errorColorChangedCb,
                                  self.terminal)
        self.app.settings.connect("consoleCommandColorChanged",
                                  self.__commandColorChangedCb,
                                  self.terminal)
        self.app.settings.connect("consoleNormalColorChanged",
                                  self.__commandNormalChangedCb,
                                  self.terminal)
        self.app.settings.connect("consoleFontChanged",
                                  self.__fontChangedCb,
                                  self.terminal)

    @classmethod
    def __colorChangedCb(cls, settings, console):
        console.set_color(settings.consoleColor)

    @classmethod
    def __errorColorChangedCb(cls, settings, console):
        console.error.set_property("foreground-rgba",
                                   settings.consoleErrorColor)

    @classmethod
    def __commandColorChangedCb(cls, settings, console):
        console.command.set_property("foreground-rgba",
                                     settings.consoleCommandColor)

    @classmethod
    def __commandNormalChangedCb(cls, settings, console):
        console.normal.set_property("foreground-rgba",
                                    settings.consoleNormalColor)

    @classmethod
    def __fontChangedCb(cls, settings, console):
        console.set_font(settings.consoleFont)

    def __activate_cb(self, unused_data):
        self.show_console()

    def __delete_event_cb(self, unused_widget, unused_data):
        self.window.hide_on_delete()
        return True
