################################################################################
###
###   Copyright 2019 SINTEF AS
###
###   This Source Code Form is subject to the terms of the Mozilla
###   Public License, v. 2.0. If a copy of the MPL was not distributed
###   with this file, You can obtain one at https://mozilla.org/MPL/2.0/
###
################################################################################

from time import time
from datetime import datetime
from enum import Enum
from subprocess import Popen, DEVNULL, PIPE
import i3ds_binding as binding

class State(Enum):
    INACTIVE = binding.inactive
    STANDBY = binding.standby
    OPERATIONAL = binding.operational
    FAILURE = binding.failure

class Poller(object):

    def __init__(self, name, cast = None):
        self.name = name
        self.cast = cast

    def __get__(self, obj, obj_type):

        if obj is None: return self

        getter = getattr(obj._client, self.name)

        obj.update()

        if self.cast is None:
            return getter()
        else:
            return self.cast(getter())

class Sensor(object):

    state = Poller("state", lambda x: State(x))
    temperature = Poller("temperature", lambda x: x.kelvin - 273.15)
    period = Poller("period")
    batch_size = Poller("batch_size")
    batch_count = Poller("batch_count")

    def __init__(self, client):
        self._client = client
        self._client.set_timeout(2000)
        self._last = 0.0
        self._record = None
        self._capture = None

    def load(self):
        self._client.load_all()
        self._last = time()

    def update(self):
        if time() - self._last > 1.0:
            self.load()

    def invalidate(self):
        self._last = 0.0

    @property
    def node(self):
        return self._client.node()

    def activate(self):
        self._client.Activate()

    def deactivate(self):
        self._client.Deactivate()

    def start(self):
        self._client.Start()

    def stop(self):
        self._client.Stop()

    def _unique_file(self):
        return "{}_{}".format(self.node, datetime.now().strftime("%Y-%m-%d_%H:%M:%S"))

    def record(self, filename = None):
        if self._record: return

        if filename is None:
            filename = "node_{}.log".format(self._unique_file())

        self._record = Popen(["i3ds_record", "--node", str(self.node), "--output", filename], stdout=DEVNULL, stderr=DEVNULL)

    def record_stop(self):
        if self._record:
            self._record.terminate()
            self._record.wait()
            self._record = None

    def capture(self, **args):
        raise NotImplementedError("Capture not implemented for class {}".format(type(self)))

    def capture_stop(self):
        if self._capture:
            self._capture.terminate()
            self._capture.wait()
            self._capture = None

    def set_sampling(self, period, batch_size = None, batch_count = None):
        if batch_size is None:
            batch_size = self.batch_size
        if batch_count is None:
            batch_count = self.batch_count
        self._client.set_sampling(period, batch_size, batch_count)
        self.invalidate()

class RegionSensor(Sensor):

    region_enabled = Poller("region_enabled")
    region = Poller("region")

    def enable_region(self, region):
        self._client.set_region(True, region)
        self.invalidate()

    def disable_region(self):
        self._client.set_region(False, (0,0,0,0))
        self.invalidate()

class Camera(RegionSensor):

    shutter = Poller("shutter")
    gain = Poller("gain")
    auto_exposure_enabled = Poller("auto_exposure_enabled")
    max_shutter = Poller("max_shutter")
    max_gain = Poller("max_gain")
    flash_enabled = Poller("flash_enabled")
    flash_strength = Poller("flash_strength")
    pattern_enabled = Poller("pattern_enabled")
    pattern_sequence = Poller("pattern_sequence")

    def capture(self, nogui = False, filename = None, format = None, scale = None):
        if self._capture: return

        if filename is None:
            filename = "camera_{}".format(self._unique_file())

        args = ["i3ds_camera_capture", "--node", str(self.node)]

        if nogui: args += ["--nogui"]
        if filename: args += ["--output", filename]
        if format: args += ["--format", format]
        if scale: args += ["--scale", str(scale)]

        self._capture = Popen(args, stdout=DEVNULL, stderr=DEVNULL)

    def set_exposure(self, shutter = None, gain = None):
        if shutter is None:
            shutter = self.shutter
        if gain is None:
            gain = self.gain
        self._client.set_exposure(shutter, gain)
        self.invalidate()

    def enable_auto_exposure(self, max_shutter = None, max_gain = None):
        if max_shutter is None:
            max_shutter = self.max_shutter
        if max_gain is None:
            max_gain = self.max_gain
        self._client.set_auto_exposure(True, max_shutter, max_gain)
        self.invalidate()

    def disable_auto_exposure(self):
        self._client.set_auto_exposure(False, 0, 0)
        self.invalidate()

    def enable_flash(self, strength = None):
        if strength is None:
            strength = 100
        if self.auto_exposure_enabled:
            print("Warning: Flash is not reliable with auto exposure")
        if strength < 0 or strength > 100:
            raise ValueError("Flash strength must be in range [0, 100]")
        self._client.set_flash(True, strength)
        self.invalidate()

    def disable_flash(self):
        self._client.set_flash(False, 0)
        self.invalidate()

    def enable_pattern(self, sequence = None):
        if sequence is None:
            sequence = 1
        if self.auto_exposure_enabled:
            print("Warning: Pattern illumination disables auto exposure")
            self.disable_auto_exposure()
        self._client.set_pattern(True, sequence)
        self.invalidate()

    def disable_pattern(self):
        self._client.set_pattern(False, 0)
        self.invalidate()

class ToFCamera(RegionSensor):

    min_depth = Poller("min_depth")
    max_depth = Poller("max_depth")

    def capture(self, nogui = False, filename = None, format = None, scale = None):
        if self._capture: return

        args = ["i3ds_camera_capture", "--node", str(self.node), "--tof", "1"]

        if filename is None:
            filename = "tof_{}".format(self._unique_file())

        if nogui: args += ["--nogui"]
        if filename: args += ["--output", filename]
        if format: args += ["--format", format]
        if scale: args += ["--scale", str(scale)]

        self._capture = Popen(args, stdout=DEVNULL, stderr=DEVNULL)

    def set_range(self, min_depth = None, max_depth = None):
        if min_depth is None:
            min_depth = self.min_depth
        if max_depth is None:
            max_depth = self.max_depth
        if min_depth > max_depth:
            raise ValueError("Max depth cannot be shorter than min")
        if min_depth < 0:
            raise ValueError("Min depth cannot be negative")
        self._client.set_range(min_depth, max_depth)
        self.invalidate()

class Radar(RegionSensor):
    pass

class LIDAR(RegionSensor):
    pass

class IMU(Sensor):

    def __init__(self, client):
        super().__init__(client)
        self._capture_file = None

    def capture(self, filename = None):

        if self._capture: return

        if filename is None:
            filename = "imu_{}.csv".format(self._unique_file())

        self._capture_file = open(filename, "a")

        args = ["i3ds_imu_capture", "--node", str(self.node)]

        self._capture = Popen(args, stdout=self._capture_file, stderr=DEVNULL)

    def capture_stop(self):
        super().capture_stop()
        if self._capture_file:
            self._capture_file.close()
            self._capture_file = None

class Analog(Sensor):

    def __init__(self, client):
        super().__init__(client)
        self._capture_file = None

    def capture(self, filename = None):

        if self._capture: return

        if filename is None:
            filename = "analog_{}.csv".format(self._unique_file())

        self._capture_file = open(filename, "a")

        args = ["i3ds_analog_capture", "--node", str(self.node)]

        self._capture = Popen(args, stdout=self._capture_file, stderr=DEVNULL)

    def capture_stop(self):
        super().capture_stop()
        if self._capture_file:
            self._capture_file.close()
            self._capture_file = None

class StarTracker(Sensor):
    pass

class Factory(object):

    def __init__(self):

        # Create context and factory from binding.
        self._context = binding.Context.Create()
        self._factory = binding.ClientFactory.Create(self._context)

        # Add new clients classes here as needed.
        self._constructors = {"Camera"      : lambda node: Camera(self._factory.Camera(node)),
                              "ToF"         : lambda node: ToFCamera(self._factory.ToFCamera(node)),
                              "LIDAR"       : lambda node: LIDAR(self._factory.LIDAR(node)),
                              "Radar"       : lambda node: Radar(self._factory.Radar(node)),
                              "StarTracker" : lambda node: StarTracker(self._factory.StarTracker(node)),
                              "IMU"         : lambda node: IMU(self._factory.IMU(node)),
                              "Analog"      : lambda node: Analog(self._factory.Analog(node))}


    def create(self, node, cls):
        if not cls in self._constructors:
            raise ValueError("Class {} is not registered as sensor client".format(cls))

        create = self._constructors[cls]

        return create(node)
