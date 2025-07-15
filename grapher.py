#!/usr/bin/python
# generate a graph, solve for physics, render with clutter

from random import uniform
from datetime import datetime

import networkx
from numpy import array as vector
from numpy.linalg import norm
import gi
gi.require_version("Gtk", "3.0")
gi.require_version('GooCanvas', '2.0')
from gi.repository import Gtk, GLib, GooCanvas

class graph():
	def __init__(self):
		self.blobsize = 8.
		self.margin = 20.
		self.width = 512
		self.height = 288
		self.left = 0.
		self.top = 0.
		self.pin = None
		self.pinned = None
		self.scale = 1.
		self.minscale = 0.75
		self.maxscale = 2.
		self.canvas = GooCanvas.Canvas(has_tooltip = True)
		self.canvas.set_property('background-color-rgb', 0xe8e8e8)
		self.stage = self.canvas.get_root_item()
		self.window = Gtk.Window()
		self.window.set_resizable(False)
		self.canvas.set_size_request(self.width, self.height)
		self.window.add(self.canvas)
		self.window.connect('destroy', Gtk.main_quit)
		self.window.show_all()
		self.graph = None
		self.create()
		GLib.idle_add(self.step)
	
	def centre(self):
		for n in self.graph.nodes:
			self.graph.nodes[n]['position'] = vector([0., 0.])
			self.graph.nodes[n]['velocity'] = vector([0., 0.])
	
	def align(self):
		maxx = max(self.graph.nodes[n]['position'][0] for n in self.graph.nodes)
		minx = min(self.graph.nodes[n]['position'][0] for n in self.graph.nodes)
		maxy = max(self.graph.nodes[n]['position'][1] for n in self.graph.nodes)
		miny = min(self.graph.nodes[n]['position'][1] for n in self.graph.nodes)
		xscale = (maxx - minx) / (self.width - 2. * self.margin)
		yscale = (maxy - miny) / (self.height - 2. * self.margin)
		if not xscale or not yscale: self.scale = self.maxscale
		elif xscale > yscale: self.scale = 1. / xscale
		else: self.scale = 1. / yscale
		if self.scale < self.minscale: self.scale = self.minscale
		if self.scale > self.maxscale: self.scale = self.maxscale
		self.top += ((self.scale * (maxy + miny) - self.height) / 2. - self.top) / 5.
		self.left += ((self.scale * (maxx + minx) - self.width) / 2. - self.left) / 5.
		for n in self.graph.nodes:
			self.graph.nodes[n]['actor'].props.height = self.graph.nodes[n]['actor'].props.width = self.blobsize * self.scale

	def create(self):
		self.last = datetime.now()
		self.frame = 0
		self.unpinnedframe = 0
		if self.graph:
			for n in self.graph.nodes:
				for m in self.graph[n]:
					if m > n: continue
					if 'actor' in self.graph[n][m]:
						self.stage.remove_child(self.stage.find_child(self.graph[n][m]['actor']))
						del self.graph[n][m]['actor']
				if 'actor' in self.graph.nodes[n]:
					self.stage.remove_child(self.stage.find_child(self.graph.nodes[n]['actor']))
					del self.graph.nodes[n]['actor']
		self.graph = networkx.random_regular_graph(3, 40) # nice test graph
		self.centre()
		self.mindist = 10.
		self.naturallength = 20.
		self.damping = 0.05
		self.spring = 0.05
		self.stepsize = 1.
		for n in self.graph.nodes:
			for m in self.graph[n]:
				if m > n: continue
				self.graph[n][m]['strength'] = 1.
				# including tooltips causes a memory leak when actors are destroyed (bgo 669688)
				self.graph[n][m]['actor'] = GooCanvas.CanvasPath(parent = self.stage, stroke_color_rgba = 0x11111180, line_width = 0.75, title='link')
			# create visualisation actor
			self.graph.nodes[n]['actor'] = GooCanvas.CanvasEllipse(parent = self.stage, fill_color_rgba = 0x33333380, line_width = 0, title = "node", height = self.blobsize, width = self.blobsize)
			self.graph.nodes[n]['actor'].connect("button-press-event", self.button)
			self.graph.nodes[n]['actor'].connect("motion-notify-event", self.drag)
			self.graph.nodes[n]['actor'].connect("button-release-event", self.unpin)
			self.graph.nodes[n]['actor'].connect("grab-broken-event", self.unpin)
			# set item physical attributes
			self.graph.nodes[n]['mass'] = 0.25
			self.graph.nodes[n]['charge'] = 10.
	
	def button(self, item, target, event):
		self.pin = item
		item.props.fill_color_rgba = 0x3333cc80
		for n in self.graph.nodes:
			if self.graph.nodes[n]['actor'] is item:
				self.pinned = n
				break
	
	def drag(self, item, target, event):
		if not self.pin or item != self.pin: return
		item.props.x, item.props.y = event.get_root_coords()
		bs = self.scale * self.blobsize / 2.
		item.props.x -= bs
		item.props.y -= bs
		self.graph.nodes[self.pinned]['position'][0] = (item.props.x + self.left + bs) / self.scale
		self.graph.nodes[self.pinned]['position'][1] = (item.props.y + self.top + bs) / self.scale
	
	def unpin(self, item, target, event):
		self.pin.props.fill_color_rgba = 0x33333380
		self.pin = None
		self.unpinnedframe = min(250, self.unpinnedframe)
	
	def step(self):
		# apply physics to update velocities
		for n in self.graph.nodes:
			if self.graph.nodes[n]['actor'] is self.pin: continue
			force = vector([0., 0.])
			for m in self.graph.nodes:
				if m == n: continue
				
				### CRITICAL SPEED SECTION ###
				direction = self.graph.nodes[n]['position'] - self.graph.nodes[m]['position']
				dist = norm(direction)
				if dist < self.mindist:
					if dist == 0.: direction = vector([uniform(-0.5, 0.5), uniform(-0.5, 0.5)])
					dist = self.mindist
					newdist = norm(direction)
					direction *= dist / newdist
				force += direction * self.graph.nodes[n]['charge'] * self.graph.nodes[m]['charge'] / dist ** 3.
				if m in self.graph[n]: force = force - direction * self.spring * (1. - self.naturallength / dist)

			massy = self.stepsize / self.graph.nodes[n]['mass']
			dampdv = - self.damping * self.graph.nodes[n]['velocity'] * norm(self.graph.nodes[n]['velocity']) * massy
			if norm(dampdv) > norm(self.graph.nodes[n]['velocity']):
				self.graph.nodes[n]['velocity'] = vector([0., 0.])
				self.graph.nodes[n]['actor'].props.fill_color_rgba = 0xcc333380
			else:
				self.graph.nodes[n]['velocity'] += dampdv
				self.graph.nodes[n]['actor'].props.fill_color_rgba = 0x33333380
			self.graph.nodes[n]['velocity'] += force * massy
		# update positions
		for n in self.graph.nodes:
			if self.graph.nodes[n]['actor'] is not self.pin:
				self.graph.nodes[n]['position'] += self.graph.nodes[n]['velocity'] * self.stepsize
		if not self.pin: self.align()
		bs = self.scale * self.blobsize / 2.

		for n in self.graph.nodes:
			self.graph.nodes[n]['actor'].props.x = self.scale * self.graph.nodes[n]['position'][0] - self.left - bs
			self.graph.nodes[n]['actor'].props.y = self.scale * self.graph.nodes[n]['position'][1] - self.top - bs
			for m in self.graph[n]:
				if m > n: continue
				# overwriting the 'data' property directly leaks memory (bgo 669661)
				self.graph[n][m]['actor'].set_property('data', " ".join([
					"M", str(self.graph.nodes[n]['actor'].props.x + bs), str(self.graph.nodes[n]['actor'].props.y + bs),
					"L", str(self.graph.nodes[m]['actor'].props.x + bs), str(self.graph.nodes[m]['actor'].props.y + bs)]))

		# reset every five hundred un-pinned frames
		self.frame += 1
		if not self.pin: self.unpinnedframe += 1
		if self.unpinnedframe == 500:
			elapsed = datetime.now() - self.last
			print(self.frame / elapsed.total_seconds())
			self.create()
		return True

g = graph()
Gtk.main ()
