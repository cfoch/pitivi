# pylint: disable=missing-docstring
# -*- coding: utf-8 -*-
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
import os

from gi.repository import GObject
from gi.repository import Peas

from pitivi.configure import get_plugins_dir
from pitivi.configure import get_user_plugins_dir
from pitivi.settings import GlobalSettings


GlobalSettings.addConfigSection('plugins')
GlobalSettings.addConfigOption("PluginsActivePlugins",
                               section="plugins", key="active-plugins",
                               default=[])


class API(GObject.GObject):
    """Interface that gives access to all the objects inside Pitivi."""
    def __init__(self, app):
        GObject.GObject.__init__(self)
        self.app = app


class PluginManager:
    """Pitivi Plugin Manager to handle a set of plugins."""

    LOADERS = ("python3", )

    def __init__(self, app):
        self.app = app
        self.engine = Peas.Engine.get_default()
        self.app.connect("window-added", self.__window_added_cb)
        self.app.settings.bindProperty(gobject=self.engine,
                                       prop='loaded-plugins',
                                       attrname='PluginsActivePlugins')
        # Set up loaders.
        for loader in self.LOADERS:
            self.engine.enable_loader(loader)

        self._setup_plugins_dir()
        self._setup_extension_set()

    def get_plugins(self):
        """Gets the engine's plugin list."""
        return self.engine.get_plugin_list()

    def get_plugin_info(self, module_name):
        """Gets the plugin info given a `name`.

        Args:
            module_name (str): The module name as registered in the .plugin file.
        Returns:
            Peas.PluginInfo: The plugin info if it exists. Otherwise, returns
                             `None`.
        """
        for plugin_info in self.get_plugins():
            if plugin_info.get_module_name() == module_name:
                return plugin_info
        return None

    def _load_plugins_from_settings(self):
        plugin_names = self.app.settings.PluginsActivePlugins
        for plugin_name in plugin_names:
            plugin_info = self.engine.get_plugin_info(plugin_name)
            if plugin_info in self.get_plugins():
                self.engine.load_plugin(plugin_info)

    def _setup_extension_set(self):
        plugin_iface = API(self.app)
        self.extension_set =\
            Peas.ExtensionSet.new_with_properties(self.engine,
                                                  Peas.Activatable,
                                                  ["object"],
                                                  [plugin_iface])
        self.extension_set.connect("extension-removed",
                                   self.__extension_removed_cb)
        self.extension_set.connect("extension-added",
                                   self.__extension_added_cb)

    def _setup_plugins_dir(self):
        plugins_dir = get_plugins_dir()
        user_plugins_dir = get_user_plugins_dir()
        if os.path.exists(plugins_dir):
            self.engine.add_search_path(plugins_dir)
        if os.path.exists(plugins_dir):
            self.engine.add_search_path(user_plugins_dir)

    @classmethod
    def __extension_removed_cb(cls, unused_set, unused_plugin_info, extension):
        extension.deactivate()

    @classmethod
    def __extension_added_cb(cls, unused_set, unused_plugin_info, extension):
        extension.activate()

    def __window_added_cb(self, unused_app, unused_window):
        self._load_plugins_from_settings()
