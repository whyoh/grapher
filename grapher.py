#!/usr/bin/python
# generate a graph, solve for physics, render with clutter

import networkx
from numpy import array as vector
from numpy.linalg import norm
from random import uniform
from gi.repository import Gtk, GooCanvas, GObject
from datetime import datetime


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

        # GooCanvas-based UI
        self.canvas = GooCanvas.Canvas(has_tooltip=True)
        self.canvas.set_property('background-color-rgb', 0xe8e8e8)
        self.stage = self.canvas.get_root_item()
        self.window = Gtk.Window()
        self.window.set_resizable(False)
        self.window.add(self.canvas)
        self.canvas.set_size_request(self.width, self.height)
        self.window.connect('destroy', Gtk.main_quit)
        self.window.show_all()
        self.create_actors()
        GObject.idle_add(self.step)

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
        for n in self.graph.node:
            self.graph.node[n]['actor'].props.height = self.graph.node[n][
                'actor'].props.width = self.blobsize * self.scale

    def create(self):
        self.last = datetime.now()
        self.frame = 0
        self.unpinnedframe = 0
        self.graph = networkx.random_regular_graph(3, 26)  # nice test graph
        self.centre()
        for n in self.graph.node:
            for m in self.graph[n]:
                if m > n:
                    continue
                self.graph[n][m]['strength'] = self.default_strength
            # set item physical attributes
            self.graph.node[n]['mass'] = self.default_mass
            self.graph.node[n]['charge'] = self.default_charge

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

    def step(self):
        # apply physics to update velocities
        for n in self.graph.node:
            if self.graph.node[n]['actor'] is self.pin:
                continue
            force = vector([0., 0.])
            for m in self.graph.node:
                if m == n:
                    continue

                # ## CRITICAL SPEED SECTION ###
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
                self.graph.node[n]['actor'].props.fill_color_rgba = 0xcc333380
            else:
                self.graph.node[n]['velocity'] += dampdv
                self.graph.node[n]['actor'].props.fill_color_rgba = 0x33333380
            self.graph.node[n]['velocity'] += force * massy
        # update positions
        for n in self.graph.node:
            if self.graph.node[n]['actor'] is not self.pin:
                self.graph.node[n]['position'] += self.graph.node[n]['velocity'] * self.stepsize
        if not self.pin:
            self.align()
        bs = self.scale * self.blobsize / 2.

        for n in self.graph.node:
            self.graph.node[n]['actor'].props.x = self.scale * self.graph.node[n]['position'][0] - self.left - bs
            self.graph.node[n]['actor'].props.y = self.scale * self.graph.node[n]['position'][1] - self.top - bs
            for m in self.graph[n]:
                if m > n:
                    continue
                # overwriting the 'data' property directly leaks memory (bgo 669661)
                self.graph[n][m]['actor'].set_property('data', " ".join([
                    "M", str(self.graph.node[n]['actor'].props.x + bs), str(self.graph.node[n]['actor'].props.y + bs),
                    "L", str(self.graph.node[m]['actor'].props.x + bs), str(self.graph.node[m]['actor'].props.y + bs)]))

        # reset every five hundred un-pinned frames
        self.frame += 1
        if not self.pin:
            self.unpinnedframe += 1
        if self.unpinnedframe == 500:
            elapsed = datetime.now() - self.last
            print self.frame / elapsed.total_seconds()
            self.destroy_actors()
            self.create()
        return True


g = Graph()
Gtk.main()
