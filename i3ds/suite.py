################################################################################
###
###   Copyright 2019 SINTEF AS
###
###   This Source Code Form is subject to the terms of the Mozilla
###   Public License, v. 2.0. If a copy of the MPL was not distributed
###   with this file, You can obtain one at https://mozilla.org/MPL/2.0/
###
################################################################################

from i3ds.sensors import Factory

class Aggregator(object):

    def __init__(self, name, cast = None):
        self.name = name

    def __get__(self, obj, obj_type):

        if obj is None: return self

        i = obj.sensors.keys()

        return dict(zip(i, [getattr(obj.sensors[x], self.name) for x in i]))

class Suite(object):

    node = Aggregator("node")
    state = Aggregator("state")
    temperature = Aggregator("temperature")
    period = Aggregator("period")
    batch_size = Aggregator("batch_size")
    batch_count = Aggregator("batch_count")

    def __init__(self):
        self._factory = Factory()
        self.sensors = {}
        self.modes = {}
        self.current_mode = None

    def __getattr__(self, name):
        if name in self.sensors:
            return self.sensors[name]
        elif name in self.modes:
            return self.modes[name]
        else:
            return super().__getattr__(name)

    def add_sensor(self, node, cls, name):

        if name in self.sensors:
            raise ValueError("Name {} is already in use".format(node))

        if node in self.node.values():
            raise ValueError("Node {} is already in use".format(node))

        self.sensors[name] = self._factory.create(node, cls)

    def add_mode(self, name, enter, leave):

        if name in self.modes:
            raise ValueError("Name {} is already in use".format(node))

        self.modes[name] = Mode(self, enter, leave)

    def activate(self):
        for sensor in self.sensors.values():
            sensor.activate()

    def deactivate(self):
        for sensor in self.sensors.values():
            sensor.deactivate()

class Command(object):

    def __init__(self, suite, sensor, command, args = None):
        if args is None:
            args = {}
        assert(type(args) == dict)
        self.sensor = getattr(suite, sensor)
        self.command = getattr(self.sensor, command)
        self.args = args

    def __call__(self):
        self.command(**self.args)

class Mode(object):

    def __init__(self, suite, enter, leave):
        self.suite = suite
        self.enter_commands = [Command(suite, *config) for config in enter]
        self.leave_commands = [Command(suite, *config) for config in leave]

    def enter(self):
        if self.suite.current_mode:
            self.suite.current_mode.leave()
        for command in self.enter_commands:
            command()
        self.suite.current_mode = self

    def leave(self):
        assert(self.suite.current_mode == self)
        for command in self.leave_commands:
            command()
        self.suite.current_mode = None

def load_setup(filename):

    import json

    with open(filename) as fp:

        setup = json.load(fp)
        suite = Suite()

        for item in setup["sensors"]:
            suite.add_sensor(*item)

        for item in setup["modes"]:
            suite.add_mode(**item)

        return suite
