# PiTiVi , Non-linear video editor
#
#       pitivi/medialibrary.py
#
# Copyright (c) 2012, Fabian Orccon <fabian.orccon@pucp.pe>
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
import gtk
from gettext import gettext as _


class StopMotionDialog(gtk.Dialog):
    def __init__(self, app, quantity):
        gtk.Dialog.__init__(self)
        self.quantity = quantity
        self.duration = None

        self._createUI()

    def _createUI(self):
        adjustment = gtk.Adjustment(value=0, lower=0, upper=7600, step_incr=1)

        hbox = gtk.HBox()

        label_duration = gtk.Label(_("Duration (seconds): "))
        self.button_spin = gtk.SpinButton(adjustment)

        hbox.pack_start(label_duration, expand=True, fill=True)
        hbox.pack_start(self.button_spin, expand=False, fill=True)

        self.button_cancel = gtk.Button(_("Cancel"))
        self.button_ok = gtk.Button(_("Apply"))

        self.button_cancel.connect("clicked", self._destroyCb)
        self.button_ok.connect("clicked", self._okCb)

        self.vbox.add(hbox)
        self.action_area.pack_start(self.button_cancel, expand=True, fill=True)
        self.action_area.pack_start(self.button_ok, expand=True, fill=True)

        self.set_title(_("Stop motion"))
        self.set_default_size(400, 150)

    def _getDurationPerClip(self):
        return long(self.total_duration / self.quantity)

    def _destroyCb(self, widget, data=None):
        self.destroy()

    def _okCb(self, widget, data=None):
        self.total_duration = self.button_spin.get_value() * 10e8
        self.duration = self._getDurationPerClip()
        self._destroyCb(widget, data)

    def run(self):
        self.show_all()
        response = gtk.Dialog.run(self)
