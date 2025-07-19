from python_bindings.

class DriverStubWrapper:
    '''
    Wraps over the different driver stubs so that the underlying driver type
    can be easily swapped out.
    '''
    def __init__(self, driver_type, driver_channel):
        self._type = driver_type
        # Get the stub corresponding to the correct driver type
        driver_stub_import_obj = importlib.import_module(
                f'python_bindings.{self._type}_service_pb2_grpc'
                )
        driver_stub = getattr(
                driver_stub_import_obj, 
                f'{self._type.capitalize()}Stub'
                )(driver_channel)




