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
from dialogs import FreesoundLibraryWidget
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Peas


class FreesoundPlugin(GObject.GObject, Peas.Activatable):
    """Add a console for development purposes in Pitivi"""
    __gtype_name__ = 'StoryboardWizardPlugin'
    object = GObject.Property(type=GObject.Object)

    MENU_LABEL = "Feesound Library"

    def __init__(self):
        GObject.GObject.__init__(self)
        self.wizard = None
        self.app = None
        self.freesound_dialog = None

    def do_activate(self):
        API = self.object
        self.app = API.app
        self.add_menu_item()
        self.menu_item.show()
        self.freesound_dialog = FreesoundLibraryWidget()

    def do_deactivate(self):
        self.app = None
        self.remove_menu_item()
        self.freesound_dialog.destroy()

    def add_menu_item(self):
        menu = self.app.gui.builder.get_object("menu")
        self.menu_item = Gtk.MenuItem.new_with_label(FreesoundPlugin.MENU_LABEL)
        self.menu_item.connect("activate", self.__activate_cb)
        menu.add(self.menu_item)

    def show_freesound_dialog(self):
        self.freesound_dialog.show()

    def __activate_cb(self, unused_data):
        self.show_freesound_dialog()
