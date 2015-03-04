__author__ = 'whyoh'
from graph import Graph

class GooGrapher(Graph):
    def __init__(self, width, height):
        from gi.repository import Gtk, GooCanvas, GObject

        Graph.__init__(self)
        canvas = GooCanvas.Canvas(has_tooltip=True)
        self.stage = canvas.get_root_item()
        canvas.set_property('background-color-rgb', 0xe8e8e8)
        window = Gtk.Window()
        window.set_resizable(False)
        window.add(canvas)
        canvas.set_size_request(width, height)
        window.connect('destroy', Gtk.main_quit)
        window.show_all()
        GObject.idle_add(self.step)

    def destroy_actors(self):
        for n in self.graph.node:
            for m in self.graph[n]:
                if m > n:
                    continue
                if 'actor' in self.graph[n][m]:
                    self.stage.remove_child(self.stage.find_child(self.graph[n][m]['actor']))
                    del self.graph[n][m]['actor']
            if 'actor' in self.graph.node[n]:
                self.stage.remove_child(self.stage.find_child(self.graph.node[n]['actor']))
                del self.graph.node[n]['actor']

    def create_actors(self):
        from gi.repository import GooCanvas
        for n in self.graph.node:
            for m in self.graph[n]:
                if m > n:
                    continue
                # including tooltips causes a memory leak when actors are destroyed (bgo 669688)
                self.graph[n][m]['actor'] = GooCanvas.CanvasPath(parent=self.stage, stroke_color_rgba=0x11111180,
                                                                 line_width=0.75, title='link')
            # create visualisation actor
            self.graph.node[n]['actor'] = GooCanvas.CanvasEllipse(parent=self.stage, fill_color_rgba=0x33333380,
                                                                  line_width=0, title="node", height=self.blobsize,
                                                                  width=self.blobsize)
            self.graph.node[n]['actor'].connect("button-press-event", self.button)
            self.graph.node[n]['actor'].connect("motion-notify-event", self.drag)
            self.graph.node[n]['actor'].connect("button-release-event", self.unpin)
            self.graph.node[n]['actor'].connect("grab-broken-event", self.unpin)

    def set_actor_size(self, size):
        for n in self.graph.node:
            self.graph.node[n]['actor'].props.height =\
                self.graph.node[n]['actor'].props.width = size

    def button(self, item, target, event):
        _ = target, event  # shut up pycharm - function prototype defined by Gtk
        self.pin = item
        item.props.fill_color_rgba = 0x3333cc80
        for n in self.graph.node:
            if self.graph.node[n]['actor'] is item:
                self.pinned = n
                break

    def drag(self, item, target, event):
        _ = target  # shut up pycharm - function prototype defined by Gtk
        if not self.pin or item != self.pin:
            return
        x, item.props.x, item.props.y = event.get_root_coords()
        bs = self.scale * self.blobsize / 2.
        item.props.x -= bs
        item.props.y -= bs
        self.graph.node[self.pinned]['position'][0] = (item.props.x + self.left + bs) / self.scale
        self.graph.node[self.pinned]['position'][1] = (item.props.y + self.top + bs) / self.scale

    def unpin(self, item, target, event):
        _ = item, target, event  # shut up pycharm - function prototype defined by Gtk
        self.pin.props.fill_color_rgba = 0x33333380
        self.pin = None
        self.unpinnedframe = min(250, self.unpinnedframe)

    @staticmethod
    def run():
        from gi.repository import Gtk
        Gtk.main()
