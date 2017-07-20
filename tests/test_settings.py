# -*- coding: utf-8 -*-
# Pitivi video editor
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
"""Tests for the pitivi.settings module."""
# pylint: disable=missing-docstring
import os
import tempfile
import unittest
from unittest import mock

from gi.repository import Gdk
from gi.repository import GObject

from pitivi.settings import ConfigError
from pitivi.settings import GlobalSettings


class TestGlobalSettings(unittest.TestCase):
    """Tests the GlobalSettings class."""

    def setUp(self):
        self.__attributes = []
        self.__options = GlobalSettings.options
        self.__environment = GlobalSettings.environment
        self.__defaults = GlobalSettings.defaults
        self.__add_config_option_real = GlobalSettings.addConfigOption
        GlobalSettings.options = {}
        GlobalSettings.environment = set()
        GlobalSettings.defaults = {}
        GlobalSettings.addConfigOption = self.__add_config_option

    def __add_config_option(self, attrname, *args, **kwargs):
        """Calls GlobalSettings.addConfigOption but remembers attributes.

        It receives the same arguments as GlobalSettings.addConfigOption but
        remembers attributes so they can be cleaned later.
        """
        self.__add_config_option_real(attrname, *args, **kwargs)
        if hasattr(GlobalSettings, attrname):
            self.__attributes.append(attrname)

    def tearDown(self):
        GlobalSettings.options = self.__options
        GlobalSettings.environment = self.__environment
        GlobalSettings.defaults = self.__defaults
        GlobalSettings.addConfigOption = self.__add_config_option_real
        self.__clean_settings_attributes()

    def __clean_settings_attributes(self):
        """Cleans new attributes set to GlobalSettings."""
        for attribute in self.__attributes:
            delattr(GlobalSettings, attribute)
        self.__attributes = []

    def test_add_section(self):
        GlobalSettings.addConfigSection("section-a")
        with self.assertRaises(ConfigError):
            GlobalSettings.addConfigSection("section-a")

    def test_add_config_option(self):
        def add_option():
            GlobalSettings.addConfigOption("optionA1", section="section-a",
                                           key="option-a-1", default=False)
        # "section-a" does not exist.
        with self.assertRaises(ConfigError):
            add_option()

        GlobalSettings.addConfigSection("section-a")
        add_option()
        self.assertFalse(GlobalSettings.optionA1)
        with self.assertRaises(ConfigError):
            add_option()

    def test_read_config_file(self):
        GlobalSettings.addConfigSection("section-1")
        GlobalSettings.addConfigOption("section1OptionA", section="section-1",
                                       key="option-a", default=50)
        GlobalSettings.addConfigOption("section1OptionB", section="section-1",
                                       key="option-b", default=False)
        GlobalSettings.addConfigOption("section1OptionC", section="section-1",
                                       key="option-c", default="")
        GlobalSettings.addConfigOption("section1OptionD", section="section-1",
                                       key="option-d", default=["foo"])
        GlobalSettings.addConfigOption("section1OptionE", section="section-1",
                                       key="option-e", default=Gdk.RGBA())

        self.assertEqual(GlobalSettings.section1OptionA, 50)
        self.assertEqual(GlobalSettings.section1OptionB, False)
        self.assertEqual(GlobalSettings.section1OptionC, "")
        self.assertEqual(GlobalSettings.section1OptionD, ["foo"])
        self.assertEqual(GlobalSettings.section1OptionE, Gdk.RGBA())

        conf_file_content = ("[section-1]\n"
                             "option-a = 10\n"
                             "option-b = True\n"
                             "option-c = Pigs fly\n"
                             "option-d=\n"
                             "     elmo\n"
                             "          knows\n"
                             "     where you live\n"
                             "option-e=rgba(51,102,255,0.4)")

        with mock.patch("pitivi.settings.xdg_config_home") as xdg_config_home,\
                tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "pitivi.conf"), "w") as tmp_file:
                tmp_file.write(conf_file_content)
            xdg_config_home.return_value = temp_dir
            settings = GlobalSettings()

        self.assertEqual(settings.section1OptionA, 10)
        self.assertEqual(settings.section1OptionB, True)
        self.assertEqual(settings.section1OptionC, "Pigs fly")
        expected_d_value = [
            "elmo",
            "knows",
            "where you live"
        ]
        self.assertEqual(settings.section1OptionD, expected_d_value)
        self.assertEqual(settings.section1OptionE, Gdk.RGBA(0.2, 0.4, 1.0, 0.4))

    def test_write_config_file(self):
        GlobalSettings.addConfigSection("section-new")
        GlobalSettings.addConfigOption("sectionNewOptionA",
                                       section="section-new", key="option-a",
                                       default="elmo")

        with mock.patch("pitivi.settings.xdg_config_home") as xdg_config_home,\
                tempfile.TemporaryDirectory() as temp_dir:
            xdg_config_home.return_value = temp_dir
            settings1 = GlobalSettings()

            settings1.sectionNewOptionA = "kermit"
            settings1.storeSettings()

            settings2 = GlobalSettings()
            self.assertEqual(settings2.sectionNewOptionA, "kermit")

    def test_bind_property(self):
        class MyGObject(GObject.GObject):
            # pylint: disable=attribute-defined-outside-init
            def __init__(self):
                GObject.GObject.__init__(self)

            @GObject.Property(flags=GObject.ParamFlags.READABLE)
            def prop_r(self):
                # pylint: disable=no-self-use
                return "read-only"

            @GObject.Property(type=str)
            def prop_rw(self):
                return self.value

            @prop_rw.setter
            def prop_rw(self, value):
                self.value = value

        GlobalSettings.addConfigSection("section")
        GlobalSettings.addConfigOption("myOptionRW",
                                       section="section", key="option-rw",
                                       default="")
        GlobalSettings.addConfigOption("myOptionR",
                                       section="section", key="option-r",
                                       default="")

        settings = GlobalSettings()
        gobject = MyGObject()

        self.assertEqual(settings.myOptionRW, "")
        settings.bindProperty(gobject, "prop-rw", "myOptionRW")
        gobject.prop_rw = "pigs fly"
        self.assertEqual(settings.myOptionRW, "pigs fly")

        with self.assertRaises(AttributeError):
            settings.bindProperty(gobject, "prop-rw", "unknownAttribute")
        with self.assertRaises(ConfigError):
            settings.bindProperty(gobject, "prop-r", "myOptionR")
