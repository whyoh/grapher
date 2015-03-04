__author__ = 'whyoh'
from math import pi
from datetime import datetime
from random import uniform
import networkx
from numpy import array as vector
from numpy.linalg import norm

class Graph():
    def __init__(self, track_energy=False, auto_correct=False):
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
        self.maxscale = 3.
        self.last = datetime.now()
        self.frame = 0
        self.unpinnedframe = 0

        # physics
        self.ke = 1. / (4. * pi * 8.854187817620e-12)
        self.mindist = 10.
        self.naturallength = 20.  # metres?
        self.damping = 0.0015  # pCdA/2 from the drag equation
        self.spring = 0.05  # k from spring equation
        self.default_mass = 0.005  # kg?
        self.default_charge = 1.25e-4  # .... coulombs?
        self.shc = 0.71  # J/g.K of graphite
        self.roomTemp = 295.  # Kelvin
        self.default_strength = 1.
        self.stepsize = 0.19  # 0.18 works.  0.19 is pretty.  0.2 is frantic 0.22 goes infinite about 1 in 3
        self.jitter = 0.02  # should be related to temperature?

        self.trackEnergy = track_energy
        self.autoCorrect = auto_correct
        self.energy = {'kinetic': 0., 'electrical': 0., 'spring': 0.}
        self.totalEnergy = 0.
        self.peakEnergy = 0.

        # the graph
        self.graph = networkx.Graph()
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
#        self.graph = networkx.random_regular_graph(3, 36)  # complex test graph
        self.centre()
        for n in self.graph.node:
            for m in self.graph[n]:
                if m > n:
                    continue
                self.graph[n][m]['strength'] = self.default_strength
            # set item physical attributes
            self.graph.node[n]['mass'] = self.default_mass
            self.graph.node[n]['charge'] = self.default_charge
        if self.trackEnergy:
            self.peakEnergy = 0.
            self.totalEnergy = 0.

    def step(self):
        # apply physics to update velocities
        ke = 0.
        ee = 0.
        se = 0.  # strain/spring/string energy (elastic potential)
        too_close = False
        for n in self.graph.node:
            force = vector([0., 0.])
            for m in self.graph.node:
                if m == n:
                    continue

                ### CRITICAL SPEED SECTION - expect the code to be a bit convoluted ###
                offset = vector([uniform(-self.jitter, self.jitter), uniform(-self.jitter, self.jitter)])
                direction = self.graph.node[n]['position'] - self.graph.node[m]['position'] + offset
                dist = norm(direction)
                if dist < self.mindist:
                    too_close = True
                    if dist == 0.:
                        direction = vector([uniform(-0.5, 0.5), uniform(-0.5, 0.5)])
                    dist = self.mindist
                    newdist = norm(direction)
                    direction *= dist / newdist
                force += self.ke * direction * self.graph.node[n]['charge'] * self.graph.node[m]['charge'] / dist ** 3.
                if m in self.graph[n]:
                    force -= direction * self.spring * (1. - self.naturallength / dist)
                if m < n or not self.trackEnergy:
                    continue
                ee += self.graph.node[n]['charge'] * self.graph.node[m]['charge'] / dist
                # calc elastic potential
                stretch = dist - self.naturallength
                se += self.spring * stretch * stretch / 2.

            if self.trackEnergy:
                speed = norm(self.graph.node[n]['velocity'])
                ke += self.graph.node[n]['mass'] * speed * speed / 2.

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

        if self.trackEnergy and not too_close:
            ee *= self.ke
            self.energy = {'kinetic': ke, 'electrical': ee, 'spring': se}
            new_total_energy = ke + ee + se
            if new_total_energy > self.totalEnergy and self.autoCorrect and self.totalEnergy > 0.:
                scaling_factor = (self.totalEnergy / new_total_energy) ** 0.5
                for n in self.graph.node:
                    self.graph.node[n]['velocity'] *= scaling_factor
            else:
                self.totalEnergy = new_total_energy

            if self.totalEnergy > self.peakEnergy:
                self.peakEnergy = self.totalEnergy

        return True
