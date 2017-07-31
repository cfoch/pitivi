# -*- coding: utf-8 -*-
# Pitivi video editor
# Copyright (c) 2005, Edward Hervey <bilboed@bilboed.com>
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
"""User preferences."""
import itertools
import os
import weakref
from gettext import gettext as _
from threading import Timer

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Peas

from pitivi.configure import get_ui_dir
from pitivi.pluginmanager import PluginManager
from pitivi.pluginmanager import PluginType
from pitivi.settings import GlobalSettings
from pitivi.utils import widgets
from pitivi.utils.loggable import Loggable
from pitivi.utils.ui import alter_style_class
from pitivi.utils.ui import fix_infobar
from pitivi.utils.ui import PADDING
from pitivi.utils.ui import SPACING


GlobalSettings.addConfigSection("user-interface")

GlobalSettings.addConfigOption('prefsDialogWidth',
                               section="user-interface",
                               key="prefs-dialog-width",
                               default=600)

GlobalSettings.addConfigOption('prefsDialogHeight',
                               section="user-interface",
                               key="prefs-dialog-height",
                               default=400)


class PreferencesDialog(Loggable):
    """Preferences for how the app works."""
    _instances = weakref.WeakSet()
    prefs = {}
    section_names = {"timeline": _("Timeline")}

    def __init__(self, app):
        Loggable.__init__(self)
        PreferencesDialog._instances.add(self)

        self.app = app

        self.app.shortcuts.connect("accel-changed", self.__accel_changed_cb)

        self.settings = app.settings
        self.widgets = {}
        self.resets = {}
        self.original_values = {}
        self.action_ids = {}

        # Identify the widgets we'll need
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(get_ui_dir(), "preferences.ui"))
        builder.connect_signals(self)
        self.dialog = builder.get_object("dialog1")
        self.sidebar = builder.get_object("sidebar")
        self.stack = builder.get_object("stack")
        self.revert_button = builder.get_object("revertButton")
        self.factory_settings = builder.get_object("resetButton")
        self.restart_warning = builder.get_object("restartWarning")

        for section_id, options in sorted(self.prefs.items()):
            self.add_settings_section(section_id)
        self.factory_settings.set_sensitive(self._canReset())

        self.__add_shortcuts_section()
        self.__add_plugin_manager_section()
        self.dialog.set_transient_for(app.gui)

    def run(self):
        """Runs the dialog."""
        self.dialog.run()

# Public API
    @classmethod
    def add_section(cls, section, title):
        """Adds a new valid section.

        Args:
            section (str): The id of a preferences category.
            title (str): The title of the new `section`.
        """
        cls.section_names[section] = title

    @classmethod
    def remove_section(cls, section):
        if section in ("timeline", "plugins", "shortcuts"):
            raise Exception("Removing Pitivi's default sections is not allowed.")
        try:
            del cls.section_names[section]
        except KeyError:
            pass
        try:
            del cls.prefs[section]
        except KeyError:
            pass
        for obj in cls._instances:
            page = obj.stack.get_child_by_name(section)
            if page is not None:
                obj.stack.remove(page)
                page.destroy()
            else:
                obj.log("No widget associated to section '%s' found" % section)

    @classmethod
    def _add_preference(cls, attrname, label, description, section,
                        widget_class, **args):
        """Adds a user preference.

        Args:
            attrname (str): The id of the setting holding the preference.
            label (str): The user-visible name for this option.
            description (str): The user-visible description explaining this
                option. Ignored unless `label` is non-None.
            section (str): The id of a preferences category.
                See `PreferencesDialog.section_names` for valid ids.
            widget_class (type): The class of the widget for displaying the
                option.
        """
        if section not in cls.section_names:
            raise Exception("%s is not a valid section id" % section)
        if section not in ("timeline", ):
            raise Exception("Adding preference to default Pitivi's sections is "
                            "not allowed.")
        if section not in cls.prefs:
            cls.prefs[section] = {}
        cls.prefs[section][attrname] = (label, description, widget_class, args)

    @classmethod
    def addPathPreference(cls, attrname, label, description, section=None):
        """Adds a user preference for a file path."""
        cls._add_preference(attrname, label, description, section,
                            widgets.PathWidget)

    @classmethod
    def addNumericPreference(cls, attrname, label, description, section=None,
                             upper=None, lower=None):
        """Adds a user preference for a number.

        Show up as either a Gtk.SpinButton or a horizontal Gtk.Scale, depending
        whether both the upper and lower limits are set.
        """
        cls._add_preference(attrname, label, description, section,
                            widgets.NumericWidget, upper=upper, lower=lower)

    @classmethod
    def addTextPreference(cls, attrname, label, description, section=None, matches=None):
        """Adds a user preference for text."""
        cls._add_preference(attrname, label, description, section,
                            widgets.TextWidget, matches=matches)

    @classmethod
    def addChoicePreference(cls, attrname, label, description, choices, section=None):
        """Adds a user preference for text options."""
        cls._add_preference(attrname, label, description, section,
                            widgets.ChoiceWidget, choices=choices)

    @classmethod
    def addTogglePreference(cls, attrname, label, description, section=None):
        """Adds a user preference for an on/off option."""
        cls._add_preference(attrname, label, description, section,
                            widgets.ToggleWidget)

    @classmethod
    def addColorPreference(cls, attrname, label, description, section=None, value_type=int):
        """Adds a user preference for a color."""
        cls._add_preference(attrname, label, description, section,
                            widgets.ColorWidget, value_type=value_type)

    @classmethod
    def addFontPreference(cls, attrname, label, description, section=None):
        """Adds a user preference for a font."""
        cls._add_preference(attrname, label, description, section,
                            widgets.FontWidget)

    def _add_page(self, section, widget):
        """Adds a `widget` to the internal stack.

        Be sure to call the add_section method before using this function.

        Args:
            section (str): The section name.
            widget (Gtk.Widget): The page to be added.
        Raises:
            Exception: When the `section` has no title assocciated to it.
        """
        if section not in self.section_names:
            raise Exception("%s is not a valid section id" % section)
        self.stack.add_titled(widget, section, self.section_names[section])

    def add_settings_section(self, section_id):
        """Adds a section for the preference which have been registered."""
        options = self.prefs[section_id]

        grid = Gtk.Grid()
        grid.set_border_width(SPACING)
        grid.props.column_spacing = SPACING
        grid.props.row_spacing = SPACING / 2

        prefs = []
        for attrname in options:
            label, description, widget_class, args = options[attrname]
            widget = widget_class(**args)
            widget.setWidgetValue(getattr(self.settings, attrname))
            widget.connectValueChanged(
                self._valueChangedCb, widget, attrname)
            widget.set_tooltip_text(description)
            self.widgets[attrname] = widget
            # Add a semicolon, except for checkbuttons.
            if isinstance(widget, widgets.ToggleWidget):
                widget.set_label(label)
                label_widget = None
            else:
                # Translators: This adds a semicolon to an already
                # translated name of a preference.
                label = _("%(preference_label)s:") % {"preference_label": label}
                label_widget = Gtk.Label(label=label)
                label_widget.set_tooltip_text(description)
                label_widget.set_alignment(1.0, 0.5)
                label_widget.show()
            icon = Gtk.Image()
            icon.set_from_icon_name(
                "edit-clear-all-symbolic", Gtk.IconSize.MENU)
            revert = Gtk.Button()
            revert.add(icon)
            revert.set_tooltip_text(_("Reset to default value"))
            revert.set_relief(Gtk.ReliefStyle.NONE)
            revert.set_sensitive(not self.settings.isDefault(attrname))
            revert.connect("clicked", self._resetOptionCb, attrname)
            revert.show_all()
            self.resets[attrname] = revert
            row_widgets = (label_widget, widget, revert)
            # Construct the prefs list so that it can be sorted.
            # Make sure the L{ToggleWidget}s appear at the end.
            prefs.append((label_widget is None, label, row_widgets))

        # Sort widgets: I think we only want to sort by the non-localized
        # names, so options appear in the same place across locales ...
        # but then I may be wrong
        for y, (_1, _2, row_widgets) in enumerate(sorted(prefs)):
            label, widget, revert = row_widgets
            if not label:
                grid.attach(widget, 0, y, 2, 1)
                grid.attach(revert, 2, y, 1, 1)
            else:
                grid.attach(label, 0, y, 1, 1)
                grid.attach(widget, 1, y, 1, 1)
                grid.attach(revert, 2, y, 1, 1)
            widget.show()
            revert.show()
        grid.show()
        self._add_page(section_id, grid)

    def __add_plugin_manager_section(self):
        page = PluginPreferencesPage(self.app)
        page.show_all()
        self.section_names["plugins"] = _("Plugins")
        self._add_page("plugins", page)

    def __add_shortcuts_section(self):
        """Adds a section with keyboard shortcuts."""
        shortcuts_manager = self.app.shortcuts
        self.description_size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self.accel_size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self.content_box = Gtk.ListBox()
        self.list_store = Gio.ListStore.new(ModelItem)
        index = 0
        for group in shortcuts_manager.groups:
            actions = shortcuts_manager.group_actions[group]
            for action, title in actions:
                item = ModelItem(self.app, action, title, group)
                self.list_store.append(item)
                self.action_ids[action] = index
                index += 1
        self.content_box.bind_model(self.list_store, self._create_widget_func, None)
        self.content_box.set_header_func(self._add_header_func, None)
        self.content_box.connect("row_activated", self.__row_activated_cb)
        self.content_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.content_box.props.margin = PADDING * 3
        viewport = Gtk.Viewport()
        viewport.add(self.content_box)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add_with_viewport(viewport)
        scrolled_window.set_min_content_height(500)
        scrolled_window.set_min_content_width(600)

        outside_box = Gtk.Box()
        outside_box.add(scrolled_window)
        outside_box.show_all()

        self.section_names["shortcuts"] = _("Shortcuts")
        self._add_page("shortcuts", outside_box)

    def __row_activated_cb(self, list_box, row):
        index = row.get_index()
        item = self.list_store.get_item(index)
        customsation_dialog = CustomShortcutDialog(self.app, self.dialog, item)
        customsation_dialog.show()

    def _create_widget_func(self, item, user_data):
        """Generates and fills up the contents for the model."""
        accel_changed = self.app.shortcuts.is_changed(item.action_name)

        title_label = Gtk.Label()
        accel_label = Gtk.Label()
        title_label.set_text(item.title)
        accel_label.set_text(item.get_accel())
        if not accel_changed:
            accel_label.set_state_flags(Gtk.StateFlags.INSENSITIVE, True)
        title_label.props.xalign = 0
        title_label.props.margin_left = PADDING * 2
        title_label.props.margin_right = PADDING * 2
        self.description_size_group.add_widget(title_label)
        accel_label.props.xalign = 0
        accel_label.props.margin_left = PADDING * 2
        accel_label.props.margin_right = PADDING * 2
        self.accel_size_group.add_widget(accel_label)

        # Add the third column with the reset button.
        button = Gtk.Button.new_from_icon_name("edit-clear-all-symbolic",
                                               Gtk.IconSize.MENU)
        button.set_tooltip_text(_("Reset the shortcut to the default accelerator"))
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.connect("clicked", self.__reset_accelerator_cb, item)
        button.set_sensitive(accel_changed)

        title_label.show()
        accel_label.show()
        button.show()

        # Pack the three widgets above into a row and add to parent_box.
        contents_box = Gtk.Box()
        contents_box.pack_start(title_label, True, True, 0)
        contents_box.pack_start(accel_label, True, False, 0)
        contents_box.pack_start(button, False, False, 0)

        return contents_box

    def _add_header_func(self, row, before, unused_user_data):
        """Adds a header for a new section in the model."""
        group = self.list_store.get_item(row.get_index()).group
        try:
            prev_group = self.list_store.get_item(row.get_index() - 1).group
        except OverflowError:
            prev_group = None

        if prev_group != group:
            header = Gtk.Label()
            header.set_use_markup(True)
            group_title = self.app.shortcuts.group_titles[group]
            header.set_markup("<b>%s</b>" % group_title)
            header.props.margin_top = PADDING * 3
            header.props.margin_bottom = PADDING
            header.props.margin_left = PADDING * 2
            header.props.margin_right = PADDING * 2
            header.props.xalign = 0
            alter_style_class("group_title", header, "font-size: small;")
            header.get_style_context().add_class("group_title")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.add(header)
            box.get_style_context().add_class("background")
            box.show_all()
            row.set_header(box)
        else:
            row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def __reset_accelerator_cb(self, unused_button, item):
        """Resets the accelerator to the default value."""
        self.app.shortcuts.reset_accels(item.action_name)

    def __accel_changed_cb(self, shortcuts_manager, action_name):
        """Handles the changing of a shortcut's accelerator."""
        if action_name:
            index = self.action_ids[action_name]
            count = 1
        else:
            # All items changed.
            index = 0
            count = self.list_store.get_n_items()
        self.list_store.emit("items-changed", index, count, count)

    def _factorySettingsButtonCb(self, unused_button):
        """Resets all settings to the defaults."""
        for section in self.prefs.values():
            for attrname in section:
                self._resetOptionCb(self.resets[attrname], attrname)
        self.app.shortcuts.reset_accels()

    def _revertButtonCb(self, unused_button):
        """Resets all settings to the values when the dialog was opened."""
        for attrname, value in self.original_values.items():
            self.widgets[attrname].setWidgetValue(value)
            setattr(self.settings, attrname, value)
        self.original_values = {}
        self.revert_button.set_sensitive(False)
        self.factory_settings.set_sensitive(self._canReset())

    def _resetOptionCb(self, button, attrname):
        """Resets a particular setting to the factory default."""
        if not self.settings.isDefault(attrname):
            self.settings.setDefault(attrname)
        self.widgets[attrname].setWidgetValue(getattr(self.settings, attrname))
        button.set_sensitive(False)
        self.factory_settings.set_sensitive(self._canReset())

    def _response_cb(self, unused_button, unused_response_id):
        # Disable missing docstring
        # pylint: disable=C0111
        self.dialog.destroy()

    def _valueChangedCb(self, unused_fake_widget, real_widget, attrname):
        # Disable missing docstring
        # pylint: disable=C0111
        value = getattr(self.settings, attrname)
        if attrname not in self.original_values:
            self.original_values[attrname] = value
            if not GlobalSettings.notifiesConfigOption(attrname):
                self.restart_warning.show()
            self.revert_button.set_sensitive(True)

        # convert the value of the widget to whatever type it is currently
        if value is not None:
            value = type(value)(real_widget.getWidgetValue())
        setattr(self.settings, attrname, value)

        # adjust controls as appropriate
        self.resets[attrname].set_sensitive(
            not self.settings.isDefault(attrname))
        self.factory_settings.set_sensitive(True)

    def _configureCb(self, unused_widget, event):
        # Disable missing docstring
        # pylint: disable=C0111
        self.settings.prefsDialogWidth = event.width
        self.settings.prefsDialogHeight = event.height

    def _canReset(self):
        # Disable missing docstring
        # pylint: disable=C0111
        for section in self.prefs.values():
            for attrname in section:
                if not self.settings.isDefault(attrname):
                    return True
        return False


class ModelItem(GObject.Object):
    """Holds the data of a keyboard shortcut for a Gio.ListStore."""

    def __init__(self, app, action_name, title, group):
        GObject.Object.__init__(self)
        self.app = app
        self.action_name = action_name
        self.title = title
        self.group = group

    def get_accel(self):
        """Returns the corresponding accelerator in a viewable format."""
        try:
            accels = self.app.get_accels_for_action(self.action_name)[0]
        except IndexError:
            accels = ""

        keyval, mods = Gtk.accelerator_parse(accels)
        return Gtk.accelerator_get_label(keyval, mods)


class CustomShortcutDialog(Gtk.Dialog):
    """Dialog for customising accelerator invoked by activating a row in preferences."""
    FORBIDDEN_KEYVALS = [Gdk.KEY_Escape]

    def __init__(self, app, pref_dialog, customised_item):
        Gtk.Dialog.__init__(self, use_header_bar=True, flags=Gtk.DialogFlags.MODAL)
        self.app = app
        self.preferences = pref_dialog
        self.customised_item = customised_item

        self.set_title(_("Set Shortcut"))
        # Set a minimum size.
        self.set_size_request(500, 300)
        # Set a maximum size.
        geometry = Gdk.Geometry()
        geometry.max_width = self.get_size_request()[0]
        geometry.max_height = -1
        self.set_geometry_hints(None, geometry, Gdk.WindowHints.MAX_SIZE)
        self.set_transient_for(self.preferences)
        self.get_titlebar().set_decoration_layout('close:')
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)

        self.conflicting_action = None

        # Setup the widgets used in the dialog.
        self.apply_button = self.add_button(_("Apply"), Gtk.ResponseType.OK)
        self.apply_button.get_style_context()\
            .add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)
        self.apply_button.set_tooltip_text(_("Apply the accelerator to this"
                                             " shortcut."))
        self.apply_button.hide()
        self.replace_button = self.add_button(_("Replace"), Gtk.ResponseType.OK)
        self.replace_button.get_style_context().\
            add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)
        self.replace_button.set_tooltip_text(_("Remove this accelerator from where "
                                               "it was used previously and set it for "
                                               "this shortcut."))
        self.replace_button.hide()

        prompt_label = Gtk.Label()
        prompt_label.set_markup(
            _("Enter new shortcut for <b>%s</b>, or press Esc to cancel.")
            % customised_item.title)
        prompt_label.props.wrap = True
        prompt_label.props.margin_bottom = PADDING * 3
        prompt_label.show()
        self.accelerator_label = Gtk.Label()
        self.accelerator_label.props.margin_bottom = PADDING
        self.invalid_label = Gtk.Label()
        self.invalid_label.set_text(
            _("The accelerator you are trying to set might interfere with typing."
              " Try using Control, Shift or Alt with some other key, please."))
        self.invalid_label.props.wrap = True
        self.conflict_label = Gtk.Label()
        self.conflict_label.props.wrap = True

        content_area = self.get_content_area()
        content_area.props.margin = PADDING * 3
        content_area.add(prompt_label)
        content_area.add(self.accelerator_label)
        content_area.add(self.conflict_label)
        content_area.add(self.invalid_label)

    def do_key_press_event(self, event):
        """Handles key press events and detects valid accelerators."""
        keyval = event.keyval
        mask = event.state

        if keyval == Gdk.KEY_Escape:
            self.destroy()
            return

        self.accelerator = Gtk.accelerator_name(keyval, mask)

        accelerator = Gtk.accelerator_get_label(keyval, mask)
        self.accelerator_label.set_markup("<span size='20000'><b>%s</b></span>"
                                          % accelerator)
        valid = Gtk.accelerator_valid(keyval, mask)

        self.conflicting_action = self.app.shortcuts.get_conflicting_action(
            self.customised_item.action_name, keyval, mask)
        if valid and self.conflicting_action:
            title = self.app.shortcuts.titles[self.conflicting_action]
            self.conflict_label.set_markup(
                _("This key combination is already used by <b>%s</b>."
                  " Press Replace to use it for <b>%s</b> instead.")
                % (title, self.customised_item.title))

        # Set visibility according to the booleans set above.
        self.apply_button.set_visible(valid and not bool(self.conflicting_action))
        self.accelerator_label.set_visible(valid)
        self.conflict_label.set_visible(valid and bool(self.conflicting_action))
        self.replace_button.set_visible(valid and bool(self.conflicting_action))
        self.invalid_label.set_visible(not valid)

    def do_response(self, response):
        """Handles the user's response."""
        if response == Gtk.ResponseType.OK:
            if self.conflicting_action:
                # Disable the accelerator in its previous use, set for this action.
                accels = self.app.get_accels_for_action(self.conflicting_action)
                accels.remove(self.accelerator)
                self.app.shortcuts.set(self.conflicting_action, accels)

            # Apply the custom accelerator to the shortcut.
            action = self.customised_item.action_name
            self.app.shortcuts.set(action, [self.accelerator])
            self.app.shortcuts.save()
        self.destroy()


class PluginPreferencesRow(Gtk.ListBoxRow):
    def __init__(self, model, show_builtins=True):
        Gtk.Bin.__init__(self)
        self.app = model.app
        self.plugin_info = model.plugin_info

        self._container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self._container)

        self._title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._title_label = Gtk.Label(self.plugin_info.get_name())
        self._description_label = Gtk.Label()

        description = self.plugin_info.get_description()
        if not description:
            description = _("No description available.")
            self._description_label.set_markup(
                "<span style=\"italic\">%s</span>" % description)
        else:
            self._description_label.set_text(description)

        self.switch = Gtk.Switch()

        # Pack widgets.
        self._title_box.pack_start(self._title_label, True, True, 0)
        self._title_box.pack_start(self._description_label, True, True, 0)
        self._container.pack_start(self._title_box, True, True, 0)
        self._container.pack_end(self.switch, False, False, 0)

        # Widgets' design.
        self._container.props.margin_left = PADDING * 2
        self._container.props.margin_right = PADDING * 2
        self._container.props.margin_top = PADDING
        self._container.props.margin_bottom = PADDING
        self._title_label.props.xalign = 0
        self._description_label.props.xalign = 0
        self._description_label.get_style_context().add_class("dim-label")
        self.switch.props.margin_left = PADDING


class PluginPreferenceModel(GObject.Object):
    """Holds the data of a plugin info for a Gio.ListStore."""
    def __init__(self, app, plugin_info):
        GObject.Object.__init__(self)
        self.app = app
        self.plugin_info = plugin_info


class PluginManagerStore(Gio.ListStore):
    """Stores the models for available plugins."""
    def __init__(self):
        Gio.ListStore.__init__(self)
        self.app = None

    @classmethod
    def new(cls, app):
        obj = PluginManagerStore()
        obj.app = app
        # FIXME
        # For some reason this property cannot be set at construct time
        # with GObject.Object.new.
        obj.set_property("item-type", PluginPreferenceModel)
        obj.reload()
        return obj

    def reload(self):
        self.remove_all()
        plugins = self.app.plugin_manager.engine.get_plugin_list()
        for plugin_info in sorted(plugins, key=PluginManagerStore._cmp):
            model = PluginPreferenceModel(self.app, plugin_info)
            self.append(model)

    @staticmethod
    def _cmp(plugin_info_a):
        if PluginManager.get_plugin_type(plugin_info_a) == PluginType.SYSTEM:
            return -1
        return 1


class PluginsBox(Gtk.ListBox):

    def __init__(self, list_store, show_builtins=True):
        Gtk.ListBox.__init__(self)
        self.app = list_store.app
        self.show_builtins = show_builtins
        self.list_store = list_store
        self.title_size_group = None
        self.switch_size_group = None

        self.set_header_func(self._add_header_func, None)
        self.bind_model(self.list_store, self._create_widget_func, None)

        self.props.margin = PADDING * 3

        # Activate the plugins' switches for plugins that are already loaded.
        loaded_plugins = self.app.plugin_manager.engine.get_loaded_plugins()
        for module_name in loaded_plugins:
            row = self.get_row(module_name)
            if row is not None:
                row.switch.set_active(True)

        self.app.plugin_manager.engine.connect("load-plugin",
                                               self.__load_plugin_cb)
        self.app.plugin_manager.engine.connect("unload-plugin",
                                               self.__unload_plugin_cb)

    def get_row(self, module_name):
        """Gets the PluginPreferencesRow linked to a given module name."""
        for row in self.get_children():
            if row.plugin_info.get_module_name() == module_name:
                return row
        return None

    def _create_widget_func(self, item, unused_user_data):
        row = PluginPreferencesRow(item)
        row.switch.connect("notify::active", self.__switch_active_cb,
                           row.plugin_info)
        return row

    def __switch_active_cb(self, switch, unused_pspec, plugin_info):
        engine = self.app.plugin_manager.engine
        if switch.get_active():
            if not engine.load_plugin(plugin_info):
                stack = self.app.gui.preferences_dialog.stack
                preferences_page = stack.get_child_by_name("plugins")
                msg = _("Unable to load the plugin '{module_name}'").format(
                    module_name=plugin_info.get_module_name())
                preferences_page.show_infobar(msg, Gtk.MessageType.WARNING)
                switch.set_active(False)
        else:
            dependant_plugins = self._get_dependant_plugins(plugin_info)
            for row in self.get_children():
                if row.plugin_info in dependant_plugins:
                    row.switch.set_active(False)
            self.app.plugin_manager.engine.unload_plugin(plugin_info)
        if self.app.gui.preferences_dialog is None:
            return
        page = self.app.gui.preferences_dialog.stack.get_child_by_name("plugins")
        self.app.gui.preferences_dialog.stack.set_property("visible-child", page)

    def _get_dependant_plugins(self, plugin_info):
        dependant_plugins = []
        module_name = plugin_info.get_module_name()
        plugins = self.app.plugin_manager.plugins
        for plugin_info in plugins:
            if plugin_info.is_hidden() or not plugin_info.is_loaded():
                continue
            if not self.show_builtins and plugin_info.is_builtin():
                continue
            if plugin_info.has_dependency(module_name):
                dependant_plugins.append(plugin_info)
        return dependant_plugins

    def __load_plugin_cb(self, engine, plugin_info):
        row = self.get_row(plugin_info.get_module_name())
        if row is not None:
            row.switch.set_active(True)

    def __unload_plugin_cb(self, engine, plugin_info):
        row = self.get_row(plugin_info.get_module_name())
        if row is not None:
            row.switch.set_active(False)

    def _add_header_func(self, row, before, unused_user_data):
        """Adds a header for a new section in the model."""
        row_plugin_type = PluginManager.get_plugin_type(row.plugin_info)
        if before is not None:
            bef_plugin_type = PluginManager.get_plugin_type(before.plugin_info)
        else:
            bef_plugin_type = None
        if row.get_index() == 0 and row_plugin_type == PluginType.SYSTEM:
            self._set_header(row, _("System plugins"))
        elif (row_plugin_type == PluginType.USER and
                (bef_plugin_type == PluginType.SYSTEM or bef_plugin_type is None)):
            self._set_header(row, _("User plugins"))

    def _set_header(self, row, group_title):
        header = Gtk.Label()
        header.set_use_markup(True)

        header.set_markup("<b>%s</b>" % group_title)
        header.props.margin_top = PADDING * 3
        header.props.margin_bottom = PADDING
        header.props.margin_left = PADDING * 2
        header.props.margin_right = PADDING * 2
        header.props.xalign = 0
        alter_style_class("group_title", header, "font-size: small;")
        header.get_style_context().add_class("group_title")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(header)
        box.get_style_context().add_class("background")
        box.show_all()
        row.set_header(box)


class PluginPreferencesPage(Gtk.ScrolledWindow):
    """The page that displays the list of available plugins."""

    INFOBAR_TIMEOUT_SECONDS = 5

    def __init__(self, app):
        Gtk.ScrolledWindow.__init__(self)
        list_store = PluginManagerStore.new(app)

        viewport = Gtk.Viewport()
        self._wrapper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        plugins_box = PluginsBox(list_store)
        viewport.add(self._wrapper_box)

        self._infobar_revealer = Gtk.Revealer()
        self._infobar = Gtk.InfoBar()
        fix_infobar(self._infobar)
        self._infobar_label = Gtk.Label()
        self._setup_infobar()

        self.add_with_viewport(viewport)
        self.set_min_content_height(500)
        self.set_min_content_width(600)

        self._wrapper_box.pack_start(self._infobar_revealer, False, False, 0)
        self._wrapper_box.pack_start(plugins_box, False, False, 0)

        # Helpers
        self._infobar_timer = None

    def _setup_infobar(self):
        self._infobar_revealer.add(self._infobar)
        self._infobar_label.set_line_wrap(True)
        self._infobar.get_content_area().add(self._infobar_label)

    def show_infobar(self, text, message_type, auto_hide=True):
        """Sets a text and a message type to the infobar to display it."""
        self._infobar.set_message_type(message_type)
        self._infobar_label.set_text(text)
        self._infobar_revealer.set_reveal_child(True)
        if auto_hide:
            if self._infobar_timer is not None:
                self._infobar_timer.cancel()
            self._infobar_timer = Timer(self.INFOBAR_TIMEOUT_SECONDS,
                                        self.hide_infobar)
            self._infobar_timer.start()

    def hide_infobar(self):
        """Hides the info bar."""
        self._infobar_revealer.set_reveal_child(False)
        self._infobar_timer = None
