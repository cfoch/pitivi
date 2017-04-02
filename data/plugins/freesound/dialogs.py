# -*- coding: utf-8 -*-
# Freesound Pitivi Plugin
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
import ssl

import freesound
from gi.repository import Gst
from gi.repository import Gtk
from gi.repository import Pango

from pitivi.utils.ui import beautify_length

ssl._create_default_https_context = ssl._create_unverified_context


class FreesoundLibraryWidget(Gtk.Window):
    def __init__(self, *args, **kwargs):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL, *args, **kwargs)

        builder = Gtk.Builder()
        builder.add_from_file(os.path.join("ui", "freesound.ui"))
        builder.connect_signals(self)

        box = builder.get_object("box")
        self.add(box)

        self.scrolled_window = builder.get_object("scrolled_window")
        self.search_entry = builder.get_object("search_entry")
        self.view = builder.get_object("view")
        self.liststore = builder.get_object("liststore")

        self.API_key = "LmwgFJ8D3mJXZPM4muxJbmAt0EMXhJgPfMcoJYvX"
        self.client = freesound.FreesoundClient()
        self.client.set_token(self.API_key, "token")

    def _search_cb(self, search_entry):
        self.liststore.clear()

        query = self.search_entry.get_text()
        results = self.client.text_search(query=query, fields="id,name,previews,duration")
        for sound in results:
            duration = sound.duration * Gst.SECOND
            data = [sound.id, sound.name, "tag", beautify_length(duration)]
            self.liststore.append(data)
