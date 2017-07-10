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
from io import TextIOBase


def display_autocompletion(last_obj, matches, text_buffer):
    """Print possible matches (to FakeOut)."""
    if len(matches) == 1:
        tokens = matches[0].split(last_obj)
        if len(tokens) >= 1:
            text_buffer.insert(text_buffer.get_end_iter(), tokens[1])
    elif len(matches) > 1:
        print()
        for match in matches:
            print(match)


class FakeOut(TextIOBase):
    def __init__(self, console, tag, fn):
        TextIOBase.__init__(self)
        self.console = console
        self.tag = tag
        # pylint: disable=invalid-name
        self.fn = fn

    def write(self, string):
        self.console.write(string, self.tag)

    def writelines(self, lines):
        self.console.write(lines, self.tag)

    def errors(self, error):
        self.console.write(error, self.tag)
