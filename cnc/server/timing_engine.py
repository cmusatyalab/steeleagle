# OpenScout
#   - Distributed Automated Situational Awareness
#
#   Author: Thomas Eiszler <teiszler@andrew.cmu.edu>
#
#   Copyright (C) 2020 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#

from cnc.server.compute_engine import DroneComputeEngine
from cnc.server.command_engine import DroneCommandEngine
import time

#TODO: these timing engines need work as the metrics here are still inherited from OpenRTiST
class TimingCommandEngine(DroneCommandEngine):
    def __init__(self, args):
        super().__init__(args )
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime

    def handle(self, from_client):
        self.t0 = time.time()
        result = super().handle(from_client)
        self.t3 = time.time()

        self.count += 1
        if self.t3 - self.lastprint > 5:
            print("pre {0:.1f} ms, ".format((self.t1 - self.t0) * 1000), end="")
            print("infer {0:.1f} ms, ".format((self.t2 - self.t1) * 1000), end="")
            print("post {0:.1f} ms, ".format((self.t3 - self.t2) * 1000), end="")
            print("wait {0:.1f} ms, ".format((self.t0 - self.lasttime) * 1000), end="")
            print("fps {0:.2f}".format(1.0 / (self.t3 - self.lasttime)))
            print(
                "avg fps: {0:.2f}".format(
                    (self.count - self.lastcount) / (self.t3 - self.lastprint)
                )
            )
            print()
            self.lastcount = self.count
            self.lastprint = self.t3

        self.lasttime = self.t3

        return result

    def infer(self, image):
        self.t1 = time.time()
        results = super().infer(image)
        self.t2 = time.time()

        return results

class TimingComputeEngine(DroneComputeEngine):
    def __init__(self, args):
        super().__init__(args )
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime

    def handle(self, from_client):
        self.t0 = time.time()
        result = super().handle(from_client)
        self.t3 = time.time()

        self.count += 1
        if self.t3 - self.lastprint > 5:
            print("pre {0:.1f} ms, ".format((self.t1 - self.t0) * 1000), end="")
            print("infer {0:.1f} ms, ".format((self.t2 - self.t1) * 1000), end="")
            print("post {0:.1f} ms, ".format((self.t3 - self.t2) * 1000), end="")
            print("wait {0:.1f} ms, ".format((self.t0 - self.lasttime) * 1000), end="")
            print("fps {0:.2f}".format(1.0 / (self.t3 - self.lasttime)))
            print(
                "avg fps: {0:.2f}".format(
                    (self.count - self.lastcount) / (self.t3 - self.lastprint)
                )
            )
            print()
            self.lastcount = self.count
            self.lastprint = self.t3

        self.lasttime = self.t3

        return result

    def inference(self, preprocessed):
        self.t1 = time.time()
        results = super().inference(preprocessed)
        self.t2 = time.time()

        return results
