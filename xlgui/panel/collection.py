# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

import gtk, gobject, urllib
from xl import xdg, common
from xlgui import panel, guiutil, menu
from gettext import gettext as _

TRACK_NUM = 300

class CollectionPanel(panel.Panel):
    """
        The collection panel
    """
    gladeinfo = ('collection_panel.glade', 'CollectionPanelWindow')
    orders = (
        ('artist', 'album', 'tracknumber', 'title'),
        ('album', 'tracknumber', 'title'),
        ('genre', 'artist', 'album', 'tracknumber', 'title'),
        ('genre', 'album', 'artist', 'tracknumber', 'title'),
        ('date', 'artist', 'album', 'tracknumber', 'title'),
        ('date', 'album', 'artist', 'tracknumber', 'title'),
        ('artist', 'date', 'album', 'tracknumber', 'title')
    )

    def __init__(self, controller, collection):
        """
            Initializes the collection panel
        """
        panel.Panel.__init__(self, controller)

        self.collection = collection
        self.settings = controller.exaile.settings
        self.use_alphabet = self.settings.get_option('gui/use_alphabet', True)
        self.filter = self.xml.get_widget('collection_search_entry')
        self.choice = self.xml.get_widget('collection_combo_box')

        self.start_count = 0
        self.keyword = ''
        self._setup_tree()
        self._setup_widgets()
        self._setup_images()
        self._connect_events()

        self.menu = menu.CollectionPanelMenu(self, controller.main)
        self.load_tree()

    def _setup_widgets(self):
        """
            Sets up the various widgets to be used in this panel
        """
        self.choice = self.xml.get_widget('collection_combo_box')
        active = self.settings.get_option('gui/collection_active_view', 0)
        self.choice.set_active(active)

        box = self.xml.get_widget('collection_search_box')
        self.filter = guiutil.EntryWithClearButton(self.on_filter_key_release)
        self.filter.connect('activate', self.on_search)
        box.pack_start(self.filter.entry, True, True)
        self.key_id = None

    def on_filter_key_release(self, *e):
        """
            Called when someone releases a key
            Sets up a timer to simulate live-search
        """
        if self.key_id:
            gobject.source_remove(self.key_id)
            self.key_id = None

        self.key_id = gobject.timeout_add(500, self.on_search)

    def _connect_events(self):
        """
            Uses signal_autoconnect to connect the various events
        """
        self.xml.signal_autoconnect({
            'on_collection_combo_box_changed': lambda *e: self.load_tree(),
        })

    def on_search(self, *e):
        """
            Searches tracks and reloads the tree
        """
        self.keyword = unicode(self.filter.get_text(), 'utf-8')
        self.start_count += 1
        self.load_tree()

    def _setup_images(self):
        """
            Sets up the various images that will be used in the tree
        """
        window = gtk.Window()
        self.artist_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path("images/artist.png"))
        self.year_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/year.png'))
        self.album_image = window.render_icon('gtk-cdrom',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.track_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/track.png'))
        self.genre_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/genre.png'))

    def drag_data_received(self, *e):
        """
            stubb
        """
        pass
    
    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        urls = self._get_urls_for(self.get_selected_tracks())
        selection.set_uris(urls)

    def _get_urls_for(self, items):
        """
            Returns the items' URLs
        """
        return [urllib.quote(item.get_loc().encode(common.get_default_encoding()))
            for item in items]

    def _setup_tree(self):
        """
            Sets up the tree widget
        """
        self.tree = guiutil.DragTreeView(self)
        self.tree.set_headers_visible(False)
        container = self.xml.get_widget('CollectionPanel')
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(scroll, True, True)
        container.show_all()

        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        self.tree.append_column(col)
        col.set_cell_data_func(cell, self.track_data_func)

        self.tree.set_row_separator_func(
            lambda m, i: m.get_value(i, 1) is None)

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object, str)
        self.model_blank = gtk.TreeStore(gtk.gdk.Pixbuf, object, str)

    def track_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if object is None: return
        field = model.get_value(iter, 2)

        if field == 'nofield':
            cell.set_property('text', object)
            return

        info = object[field]
        if not info or info == u'': 
            info = _('Unknown')
        cell.set_property('text', info)

    def _find_recursive(self, iter, add):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)        
        while True:
            field = self.model.get_value(iter, 2)
            if self.model.iter_has_child(iter):
                self._find_recursive(iter, add)
            elif field == 'title':
                track = self.model.get_value(iter, 1)
                if not track in add:
                    add.append(track)
            
            iter = self.model.iter_next(iter)
            if not iter: break

    def get_selected_tracks(self):
        """
            Finds all the selected tracks
        """

        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        found = [] 
        for path in paths:
            iter = self.model.get_iter(path)
            field = self.model.get_value(iter, 2)
            if self.model.iter_has_child(iter):
                self._find_recursive(iter, found)
            else:
                track = self.model.get_value(iter, 1)
                if field == 'title':
                    if not track in found:
                        found.append(track)

        return found

    def append_to_playlist(self, item=None, event=None):
        """
            Adds items to the current playlist
        """
        add = self.get_selected_tracks()

        pl = self.controller.main.get_selected_playlist()
        if pl:
            tracks = pl.playlist.get_tracks()
            found = []
            for track in add:
                if not track in tracks:
                    found.append(track)
            pl.playlist.add_tracks(found)

    def button_press(self, widget, event):
        """ 
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        (x, y) = map(int, event.get_coords())
        path = self.tree.get_path_at_pos(x, y)
        if event.type == gtk.gdk._2BUTTON_PRESS:
            (model, paths) = selection.get_selected_rows()

            # check to see if it's a double click on an album
            if len(paths) == 1:
                iter = self.model.get_iter(path[0])
                object = self.model.get_value(iter, 1)
                field = self.model.get_value(iter, 2)

                if field == 'album':
                    self.append_to_playlist()
                    return False

            for path in paths:
                iter = self.model.get_iter(path)
                object = self.model.get_value(iter, 1)
                if self.model.iter_has_child(iter):
                    self.tree.expand_row(path, False)
                else:
                    self.append_to_playlist()

            return False
        elif event.button == 3:
            selection = self.tree.get_selection()
            self.menu.popup(event)

    def load_tree(self):
        """
            Builds the tree
        """
        self.current_start_count = self.start_count
        self.model.clear()
        self.tree.set_model(self.model_blank)

        self.root = None
        self.order = self.orders[self.choice.get_active()]

        self.image_map = {
            "album": self.album_image,
            "artist": self.artist_image,
            "genre": self.genre_image,
            "title": self.track_image,
            "date": self.year_image,
        }

        # save the active view setting
        self.settings['gui/collection_active_view'] = self.choice.get_active()

        tracks = self.collection.search(self.keyword, self.order)

        if self.current_start_count != self.start_count: return
        self.append_tracks(self.root, tracks)

    def append_tracks(self, node, tracks=None, unknown=False,
        expanded_paths=None):
        """
            Adds tracks to the tree in the correct order
        """
        current_tracks = tracks[:TRACK_NUM]
        order_nodes = common.idict()
        order = []
        last_songs = []

        for field in self.order:
            if field == 'tracknumber': continue
            order.append(field)

        for field in order:
            order_nodes[field] = common.idict()

        last_char = None
        if not expanded_paths: expanded_paths = []

        for track in current_tracks:
            parent = node
            last_parent = None
            string = ""
            first = True

            for field in order:
                node_for = order_nodes[field]
                if field == 'tracknumber': continue
                info = track[field]

                # print separators
                if first and info and self.use_alphabet:
                    temp = info.upper()

                    # remove 'the' if it's the artist field
                    if field == 'artist':
                        if temp.find('THE ') == 0:
                            temp = temp[4:]

                    if not temp: first_char = ' '
                    else: first_char = temp[0]

                    if not last_char: # first row, don't add separator
                        last_char = first_char

                    if first_char != last_char:
                        if not first_char.isalpha():
                            first_char = '0-9'
                        if first_char != last_char:
                            last_char = first_char
                            self.model.append(parent, [None, None, None]) 

                if not info or info == u'':
                    if not unknown and first:
                        last_songs.append(track)
                        break
                    info = _('Unknown')
                first = False

                if field == 'title':
                    n = self.model.append(parent, [self.track_image,
                        track, field])
                else:
                    string = '%s - %s' % (string, info)
                    if not string in node_for:
                        parent = self.model.append(parent,
                            [self.image_map[field], track, field])

                        if info == 'tracknumber': info = track
                        node_for[string] = parent
                    else:
                        parent = node_for[string]

                if self.keyword and last_parent:
                    if self.keyword.lower() in common.to_unicode(info).lower():
                        expanded_paths.append(self.model.get_path(
                            last_parent))

                last_parent = parent

        newtracks = tracks[TRACK_NUM:]
        if newtracks:
            gobject.idle_add(self.append_tracks, node, newtracks, unknown,
                expanded_paths)
        else:
            # make sure 'unknown' items end up at the end of the list
            if not unknown and last_songs:
                self.append_tracks(self.root, last_songs, True,
                    expanded_paths)

            self.tree.set_model(self.model)

            for path in expanded_paths:
                self.tree.expand_to_path(path)
