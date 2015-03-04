#!/usr/bin/python
# generate a graph, solve for physics, render with sub-class
from __future__ import print_function
from numpy import dot
from datetime import datetime
from vispy import gloo, app
from graph import Graph


class GlooGrapher(Graph, app.Canvas):
    def __init__(self, **kwargs):
        import numpy
        Graph.__init__(self, **kwargs)
        for keyword in ['track_energy', 'auto_correct']:
            if keyword in kwargs:
                del kwargs[keyword]
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
            clear_color='black', depth_test=False, blend=True, blend_func=('src_alpha', 'one_minus_src_alpha'))

    def on_resize(self, event):
        self.width, self.height = event.size
        gloo.set_viewport(0, 0, self.width, self.height)

    def on_draw(self, event):
        _ = event  # shut up pycharm - function prototype defined by OpenGL
        gloo.clear(color=True, depth=True)
        self.line_program.draw('lines', self.index)
        self.circle_program.draw('points')

    @staticmethod
    def on_close(event):
        _ = event
        app.quit()
        exit(0)

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
            speed = dot(node['velocity'], node['velocity']) / 100.
            if speed > 1:
                speed = 1
            data['a_bg_color'][0] = 1. if speed == 1 else speed
            data['a_bg_color'][1] = 0. if speed == 1 else 0.5 if speed < 0.0002 else speed
            data['a_bg_color'][2] = 0. if speed == 1 else 1. if speed < 0.0002 else speed
            data['a_bg_color'][2] = 0. if speed == 1 else speed
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
        if self.unpinnedframe % 100 == 0:
            print(self.totalEnergy)
        if self.unpinnedframe == 500:
            elapsed = datetime.now() - self.last
            print(self.frame / elapsed.total_seconds())
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


g = GlooGrapher(track_energy=True, auto_correct=False)
g.run()
