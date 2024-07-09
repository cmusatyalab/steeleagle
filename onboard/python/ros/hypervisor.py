import argparse
import asyncio
from onboard.python.ros.supervisor import Supervisor
from rclpy.node import Node
import rclpy

class Hypervisor(Node):
    
    # init
    def __init__(self, hyper_args):
        super().__init__('hypervisor_node')
        
        # Initialize lists
        self.cloudlet_list = []
        self.drone_list = []
        self.supervisor_list = []
        
        # Set the lists based on args
        self.drones_list = list(hyper_args.drones_list)
        self.supervisors_list = list(hyper_args.supervisors_list)
        self.mission_list = list(hyper_args.missions_list)
    
    
    # assign mission to the supervisor
    def patch_mission():
        return
        
        
def main(args = None):
    # parse the args
    parser = argparse.ArgumentParser(description='Hypervisor arguments')
    parser.add_argument('--drones_list', type=str, default='default_value',
                        help='A custom parameter not related to ROS')
    parser.add_argument('--supervisors_list', type=str, default='default_value',
                        help='A custom parameter not related to ROS')
    parser.add_argument('--missions_list', type=str, default='default_value',
                        help='A custom parameter not related to ROS')
    
    # First, parse the arguments to separate custom arguments from ROS arguments
    hyper_args, node_args = parser.parse_known_args()

    
    # hypervisor node init
    rclpy.init(args=node_args)
    # Create an instance of the Hypervisor node
    hypervisor_node = Hypervisor(hyper_args)
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