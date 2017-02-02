# -*- coding: utf-8 -*-
# cfoch-peas
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

import gi
gi.require_version('Peas', '1.0')

import os

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Peas
from gi.repository import PeasGtk

from pitivi.configure import get_plugins_dir

class API(GObject.GObject):
    def __init__(self, app):
        GObject.Object.__init__(self)
        self.app = app


class PluginManager:
    LOADERS = ("python3", )
    def __init__(self, app):
        self.app = app
        self.engine = Peas.Engine.get_default()
        self._setup_loaders()
        self._setup_plugins_dir()
        self._setup_extension_set()

    def get_plugins(self):
        return self.engine.get_plugin_list()

    def _load_plugins(self):
        for plugin in self.get_plugins():
            self.engine.load_plugin(plugin)

    def _setup_extension_set(self):
        plugin_iface = API(self.app)
        value = GObject.Value()
        value.init(API)
        value.set_object(plugin_iface)
        self.extension_set = Peas.ExtensionSet.new_with_properties(self.engine, Peas.Activatable, ["object"], [plugin_iface])
        self.extension_set.connect("extension-removed", self.__extension_removed_cb)
        self.extension_set.connect("extension-added", self.__extension_added_cb)

    def _setup_loaders(self):
        for loader in self.LOADERS:
            self.engine.enable_loader(loader)

    def _setup_plugins_dir(self):
        plugins_dir = get_plugins_dir()
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
        self.engine.add_search_path(plugins_dir)

    def __extension_removed_cb(self, unused_set, unused_plugin_info, extension):
        extension.deactivate()

    def __extension_added_cb(self, unused_set, unused_plugin_info, extension):
        extension.activate()
