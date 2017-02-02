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

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Peas
from gi.repository import PeasGtk


class PluginManagerDialog:
    def __init__(self, engine, transient):
        self.dialog = Gtk.Dialog()
        self.manager = PeasGtk.PluginManager(engine)

        self.dialog.connect("response", self._response_cb)
        self.dialog.set_transient_for(transient)

        content_area = self.dialog.get_content_area()
        content_area.add(self.manager)
        self.dialog.show_all()

    def run(self):
        """Runs the dialog."""
        self.dialog.run()

    def _response_cb(self, unused_button, unused_response_id):
        # Disable missing docstring
        # pylint: disable=C0111
        self.dialog.destroy()
