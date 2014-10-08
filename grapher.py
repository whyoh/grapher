#!/usr/bin/python
# generate a graph, solve for physics, render with sub-class

import networkx
from numpy import array as vector
from numpy.linalg import norm
from random import uniform
from datetime import datetime
from vispy import gloo, app


class Graph():
    def __init__(self):
        # UI settings
        self.blobsize = 8.
        self.margin = 20.
        self.width = 320
        self.height = 240
        self.left = 0.
        self.top = 0.
        self.pin = None
        self.pinned = None
        self.scale = 1.
        self.minscale = 0.75
        self.maxscale = 2.
        self.last = datetime.now()
        self.frame = 0
        self.unpinnedframe = 0

        # physics
        self.mindist = 10.
        self.naturallength = 20.
        self.damping = 0.05
        self.spring = 0.05
        self.stepsize = 1.
        self.default_strength = 1.
        self.default_mass = 0.25
        self.default_charge = 10.

        # the graph
        self.graph = None
        self.create()

    def centre(self):
        for n in self.graph.node:
            self.graph.node[n]['position'] = vector([0., 0.])
            self.graph.node[n]['velocity'] = vector([0., 0.])

    def align(self):
        maxx = max(self.graph.node[n]['position'][0] for n in self.graph.node)
        minx = min(self.graph.node[n]['position'][0] for n in self.graph.node)
        maxy = max(self.graph.node[n]['position'][1] for n in self.graph.node)
        miny = min(self.graph.node[n]['position'][1] for n in self.graph.node)
        xscale = (maxx - minx) / (self.width - 2. * self.margin)
        yscale = (maxy - miny) / (self.height - 2. * self.margin)
        if not xscale or not yscale:
            self.scale = self.maxscale
        elif xscale > yscale:
            self.scale = 1. / xscale
        else:
            self.scale = 1. / yscale
        if self.scale < self.minscale:
            self.scale = self.minscale
        if self.scale > self.maxscale:
            self.scale = self.maxscale
        self.top += ((self.scale * (maxy + miny) - self.height) / 2. - self.top) / 5.
        self.left += ((self.scale * (maxx + minx) - self.width) / 2. - self.left) / 5.

    def create(self):
        self.last = datetime.now()
        self.frame = 0
        self.unpinnedframe = 0
        self.graph = networkx.random_regular_graph(3, 26)  # nice test graph
#        self.graph = networkx.random_regular_graph(3, 16)  # simple test graph
        self.centre()
        for n in self.graph.node:
            for m in self.graph[n]:
                if m > n:
                    continue
                self.graph[n][m]['strength'] = self.default_strength
            # set item physical attributes
            self.graph.node[n]['mass'] = self.default_mass
            self.graph.node[n]['charge'] = self.default_charge

    def step(self):
        # apply physics to update velocities
        for n in self.graph.node:
            force = vector([0., 0.])
            for m in self.graph.node:
                if m == n:
                    continue

                ### CRITICAL SPEED SECTION - expect the code to be a bit convoluted ###
                direction = self.graph.node[n]['position'] - self.graph.node[m]['position']
                dist = norm(direction)
                if dist < self.mindist:
                    if dist == 0.:
                        direction = vector([uniform(-0.5, 0.5), uniform(-0.5, 0.5)])
                    dist = self.mindist
                    newdist = norm(direction)
                    direction *= dist / newdist
                force += direction * self.graph.node[n]['charge'] * self.graph.node[m]['charge'] / dist ** 3.
                if m in self.graph[n]:
                    force -= direction * self.spring * (1. - self.naturallength / dist)

            massy = self.stepsize / self.graph.node[n]['mass']
            dampdv = - self.damping * self.graph.node[n]['velocity'] * norm(self.graph.node[n]['velocity']) * massy
            if norm(dampdv) > norm(self.graph.node[n]['velocity']):
                self.graph.node[n]['velocity'] = vector([0., 0.])
            else:
                self.graph.node[n]['velocity'] += dampdv
            self.graph.node[n]['velocity'] += force * massy
        # update positions
        for n in self.graph.node:
            self.graph.node[n]['position'] += self.graph.node[n]['velocity'] * self.stepsize
        if not self.pin:
            self.align()

        return True


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


class GlooGrapher(Graph, app.Canvas):
    def __init__(self, **kwargs):
        import numpy
        Graph.__init__(self)
        app.Canvas.__init__(self, keys='interactive', **kwargs)
        self.size = self.width, self.height
        self.position = 50, 50

        self.data = None
        self.edges = None
        self.vbo = gloo.VertexBuffer(self.build_vbo_array_from_graph_nodes())
        self.index = gloo.IndexBuffer(self.build_ibo_array_from_graph_edges())
        self.view = numpy.eye(4, dtype=numpy.float32)
        self.model = numpy.eye(4, dtype=numpy.float32)
        self.projection = numpy.eye(4, dtype=numpy.float32)
        self.maxscale *= 4

        self.circle_program = gloo.Program(
            open("circle_vertex.sl").read(),
            open("circle_fragment.sl").read()
        )
        self.circle_program.bind(self.vbo)
        self.circle_program['u_size'] = 1
        self.circle_program['u_antialias'] = 1
        self.circle_program['u_model'] = self.model
        self.circle_program['u_view'] = self.view
        self.circle_program['u_projection'] = self.projection

        self.line_program = gloo.Program(
            open("line_vertex.sl").read(),
            open("line_fragment.sl").read()
        )
        self.line_program.bind(self.vbo)
        self.t = app.Timer(connect=self.on_frame, start=True)
        self.show()

    @staticmethod
    def on_initialize(event):
        _ = event  # shut up pycharm - function prototype defined by OpenGL
        gloo.set_state(
            clear_color='white', depth_test=False, blend=True, blend_func=('src_alpha', 'one_minus_src_alpha'))

    def on_resize(self, event):
        self.width, self.height = event.size
        gloo.set_viewport(0, 0, self.width, self.height)

    def on_draw(self, event):
        _ = event  # shut up pycharm - function prototype defined by OpenGL
        gloo.clear(color=True, depth=True)
        self.line_program.draw('lines', self.index)
        self.circle_program.draw('points')

    def build_vbo_array_from_graph_nodes(self):
        import numpy
        if self.data is None:
            self.data = numpy.zeros(len(self.graph), dtype=[
                ('a_position', numpy.float32, 3),
                ('a_fg_color', numpy.float32, 4),
                ('a_bg_color', numpy.float32, 4),
                ('a_size', numpy.float32, 1),
                ('a_linewidth', numpy.float32, 1),
            ])

        bs = int(self.blobsize * self.scale)

        for n in self.graph.node:
            node = self.graph.node[n]
            data = self.data[n]
            data['a_position'][0] = node['position'][0] / 100.
            data['a_position'][1] = node['position'][1] / 100.
            data['a_size'] = bs
            data['a_bg_color'][0] = 0.75
            data['a_bg_color'][1] = 0.75 if node['velocity'][0] > 0. or node['velocity'][1] > 0. else 1.
            data['a_bg_color'][2] = 0.75
            data['a_bg_color'][3] = 1.

        self.data['a_fg_color'] = 0, 0, 0, 1
        self.data['a_linewidth'] = 1
        return self.data

    def build_ibo_array_from_graph_edges(self):
        import numpy
        if self.edges is None:
            self.edges = numpy.random.randint(
                size=(sum(len(x) for x in self.graph.edge.values()) / 2, 2), low=0, high=len(self.graph)
            ).astype(numpy.uint32)
        index = 0
        for n in self.graph.node:
            for m in self.graph[n]:
                if m > n:
                    continue
                self.edges[index][0] = n
                self.edges[index][1] = m
                index += 1
        return self.edges

    def on_frame(self, event):
        # reset every five hundred un-pinned frames
        self.frame += 1
        if not self.pin:
            self.unpinnedframe += 1
        if self.unpinnedframe == 500:
            elapsed = datetime.now() - self.last
            print self.frame / elapsed.total_seconds()
            self.create()
            self.edges = None
            self.data = None
            self.index = gloo.IndexBuffer(self.build_ibo_array_from_graph_edges())

        self.step()
        self.vbo.set_data(self.build_vbo_array_from_graph_nodes())
        self.update(event)

    @staticmethod
    def run():
        app.run()


g = GlooGrapher()
g.run()
