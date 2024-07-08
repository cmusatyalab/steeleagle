import asyncio
from onboard.python.supervisor import Supervisor
from rclpy.node import Node
import rclpy

class Hypervisor(Node):
    def __init__(self, args):
        super().__init__('hypervisor_node')
        
        # Initialize lists
        self.cloudlet_list = []
        self.drone_list = []
        self.supervisor_list = []
        
        # Set the lists based on args
        self.drone_list = list(args.drone_list)
        self.supervisor_args_list = list(args.supervisor_args_list)
        
        # Create and run supervisor instances
        for i in range(len(self.drone_list)):
            curr_args = self.supervisor_args_list[i]
            curr_supervisor = Supervisor(curr_args)
            self.supervisor_list.append(curr_supervisor)
            # Run the _main coroutine of the supervisor instance
            asyncio.run(curr_supervisor._main())
        
def main(args=None):
    rclpy.init(args=args)
    
    # Define or get your args appropriately
    supervisor_args = SomeArgs()  
    
    # Create an instance of the Hypervisor node
    hypervisor_node = Hypervisor(supervisor_args)
    
    try:
        rclpy.spin(hypervisor_node)
    except KeyboardInterrupt:
        pass
    finally:
        # Destroy the node explicitly
        hypervisor_node.destroy_node()
        # Shutdown rclpy
        rclpy.shutdown()

if __name__ == '__main__':
    main()