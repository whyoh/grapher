grapher
=======

physical model of a network of connected nodes.  for cool/useful visualisations and better neighbour/relevance calculations.

written in python using numpy and networkx libraries.

also requires Gtk, GooCanvas, GObject and Gio from gi.repository.  so it's pretty much linux/gnome only at the moment.

alternatively, use the from-goo-to-gloo branch - that uses vispy instead and works on mac and linux (and probably windows too, if anyone cares).

to do
-----
* turn this list into issues
* turn the non-graphics part into a 'physics-enabled' subclass of the networkx graph class
* turn graphic part into 'with-graphics' subclass of that
* experiments with scipy ODE solvers (in progress)
* energy, momentum and angular momentum corrections (in progress)
* use networkx cluster/distance tools to create hierarchy of graphs
* general performance overhaul (e.g. a specialised library for core maths written in C/OpenCL)
* allow number of dimensions selection in class (currently 2 only)
* get backend running on other platforms: windows, mac, android, javascript (browser)
* make alternative graphics front-ends: clutter, openscenegraph, raphaël etc
