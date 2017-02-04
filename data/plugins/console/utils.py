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
from io import StringIO


def display_autocompletion(last_obj, matches):
    if len(matches) == 1:
        print(matches[0].split(last_obj)[1], end='')
    elif len(matches) > 1:
        print()
        for match in matches:
            print(match)


class FakeOut(StringIO):
    def __init__(self, console, fn, tag):
        self.fn = fn
        self.console = console
        self.tag = tag

    def write(self, s):
        self.console.write(s, self.tag)

    def writelines(self, l):
        self.console.write(l, self.tag)

    def errors(self, e):
        self.console.write(e, self.tag)
