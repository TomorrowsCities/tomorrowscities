"""Keep one map preview per layer and release superseded widget trees."""

import logging


class MapLayerCache:
    def __init__(self):
        self.entries = {}
        self.retired = []
        self.layers = []

    def get(self, name, key, source, factory, force=False):
        entry = self.entries.get(name)
        if not force and entry is not None and entry[0] == key and entry[1] is source:
            return entry[2]
        widget = factory()
        if entry is not None:
            self.retired.append(entry[2])
        self.entries[name] = (key, source, widget)
        return widget

    def prune(self, active_names):
        for name in list(self.entries):
            if name not in active_names:
                self.retired.append(self.entries.pop(name)[2])

    def release_retired(self):
        visited = set()

        def close_tree(widget):
            if id(widget) in visited:
                return
            visited.add(id(widget))
            for attr in ['layers', 'markers']:
                for child in getattr(widget, attr, ()):
                    close_tree(child)
            icon = getattr(widget, 'icon', None)
            if hasattr(icon, 'close'):
                close_tree(icon)
            try:
                widget.close()
            except Exception:
                logging.getLogger(__name__).exception('Unable to release retired map widget')

        retired, self.retired = self.retired, []
        for widget in retired:
            close_tree(widget)

    def close(self):
        self.prune(set())
        self.layers = []
        self.release_retired()
