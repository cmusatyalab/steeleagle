# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

class ComputeStub():


    def processResults(self, result_wrapper):
        pass


    def startStreaming(self, drone, model, sample_rate):
        pass


    def stopStreaming(self):
        pass


    def switchModel(self, model):
        pass


    def sendFrame(self, frame):
        pass


    def getResults(self, engine_key):
        pass
    

    def clearResults(self, engine_key):
        pass

