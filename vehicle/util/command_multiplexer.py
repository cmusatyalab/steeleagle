import inspect
# Protocol imports
from google.protobuf import any_pb2
from python_bindings import driver_service_pb2
from python_bindings import mission_service_pb2
from python_bindings import control_pb2 as control_proto

class CommandMultiplexer:
    '''
    Reads messages from the Swarm Controller and relays
    them to the corresponding stubs.
    '''
    def __init__(self, driver_stub, mission_stub, mode, logger):
        self._driver_stub = driver_stub
        self._mission_stub = mission_stub
        # Control mode must be modified when the Swarm
        # Controller starts a mission or resumes remote
        # operation; this reference will affect other
        # background services reading the same object
        self._control_mode = mode
        self._logger = logger
        self._call_table = self._gen_call_table()

    def _gen_call_table(self):
        '''
        Creates an association between descriptors and their associated
        stub call for clean multiplexing of commands.
        '''
        call_table = {}
        
        driver_symbols = inspect.getmembers(driver_service_pb2)
        for name, obj in driver_symbols:
            if inspect.isclass(obj) and "Request" in name:
                f_name = name.replace("Request", "")
                call_table[name] = (
                        "driver_service_pb2",
                        eval(f"self._driver_stub.{f_name}") 
                        )
        mission_symbols = inspect.getmembers(mission_service_pb2)
        for name, obj in mission_symbols:
            if inspect.isclass(obj) and "Request" in name:
                f_name = name.replace("Request", "")
                call_table[name] = (
                        "mission_service_pb2",
                        eval(f"self._mission_stub.{f_name}")
                        )
        return call_table

    def _switch_mode(self, package, name):
        '''
        Handles switching the control mode when a mission start/stop
        or a driver command is received.
        '''
        if package == "mission_service_pb2":
            # Handle mission stop and start
            if "Start" in name:
                self._logger.info("Switching mode to LOCAL control")
                self._control_mode.switch_mode(control_proto.ControlMode.LOCAL)
            elif "Stop" in name:
                self._logger.info("Switching mode to REMOTE control")
                self._control_mode.switch_mode(control_proto.ControlMode.REMOTE)
        elif package == "driver_service_pb2" and \
                self._control_mode.get_mode() != control_proto.ControlMode.REMOTE:
            # If we ever get a direct driver control, override the mission
            self._logger.info("Switching mode to REMOTE control")
            self._control_mode.switch_mode(control_proto.ControlMode.REMOTE)

    async def __call__(self, message):
        '''
        Multiplexes a ControlRequest message between the driver
        and mission stubs.
        '''
        # Message is expected to be a ControlRequest 
        control_request = control_proto.ControlRequest()
        control_request.ParseFromString(message)
        self._logger.log_proto(control_request)
        control_message = request.control_message
        # Get the message name from the type URL
        name = control_message.getTypeUrl().split('.')[-1]     
        if name in self._call_table:
            pkg, func = self._call_table[name]
            # Unpack the Any request into the right message
            request = getattr(pkg, name)()
            control_message.Unpack(request)
            # Call the corresponding function and switch mode
            self._switch_mode(pkg, name)
            response = await func(request)
            self._logger.log_proto(response)
            return response
        else:
            self._logger.error("Could not parse object!")
            raise TypeError("Command has unknown type!")
