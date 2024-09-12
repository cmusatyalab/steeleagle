class Service:
    def __init__(self, name):
        self.name = name

    def start(self):
        raise NotImplementedError("start method not implemented")

    def stop(self):
        raise NotImplementedError("stop method not implemented")

    def restart(self):
        self.stop()
        self.start()