#!/usr/bin/env python3
"""
Example usage of the airspace control system with comprehensive logging
"""

import logging
from logger_config import setup_airspace_logging
from airspace_control_engine import AirspaceControlEngine
import airspace_region as asr

def main():
    # Initialize logging system
    loggers = setup_airspace_logging(log_level=logging.DEBUG, log_dir="airspace_logs")
    
    print("Airspace Control System starting...")
    print("Logs will be written to:")
    print("  - airspace_logs/airspace_control.log (main application log)")
    print("  - airspace_logs/airspace_security_YYYYMMDD.log (security/audit log)")
    print("  - airspace_logs/airspace_performance.log (performance metrics)")
    print("  - Console output for real-time monitoring")
    print()
    
    # Example airspace boundaries (lat, lon corners)
    # Simple rectangular area
    corners = [
        (50.7829, -73.9654),  # Top left (near Central Park, NYC)
        (40.7489, -73.9654),  # Bottom left  
        (40.7489, -63.9254),  # Bottom right
        (50.7829, -63.9254)   # Top right
    ]
    
    # Initialize the airspace control engine
    engine = AirspaceControlEngine(corners, min_alt=0,      # Ground level
        max_alt=400,    # 400m altitude limit
        alt_partitions=4,   # 4 altitude layers (0-100m, 100-200m, 200-300m, 300-400m)
        lat_partitions=3,   # 3 latitude divisions
        lon_partitions=3)
    
    
    print(f"Created airspace with {len(engine.region_map)} regions")
    
    # Example drone operations
    test_drone_operations(engine)

def test_drone_operations(engine: AirspaceControlEngine):
    """Demonstrate typical drone operations with logging"""
    
    logger = logging.getLogger('airspace.demo')
    
    # Register some drones with different priorities
    engine.set_priority(drone_id=1001, new_priority=5)  # Normal priority
    engine.set_priority(drone_id=1002, new_priority=10) # High priority (emergency)
    engine.set_priority(drone_id=1003, new_priority=1)  # Low priority (cargo)
    
    # Get some regions for testing
    region_ids = list(engine.region_map.keys())
    if len(region_ids) < 3:
        logger.error("Not enough regions created for testing")
        return
    
    region1 = engine.get_region_from_id(region_ids[0])
    region2 = engine.get_region_from_id(region_ids[1]) 
    region3 = engine.get_region_from_id(region_ids[2])
    
    logger.info("=== Starting drone operation simulation ===")
    
    # Scenario 1: Normal reservation and occupancy
    logger.info("--- Scenario 1: Normal operations ---")
    success = engine.reserve_region(1001, region1)
    logger.info(f"Drone 1001 reservation: {'SUCCESS' if success else 'FAILED'}")
    
    if success:
        success = engine.add_occupant(1001, region1)
        logger.info(f"Drone 1001 occupancy: {'SUCCESS' if success else 'FAILED'}")
        
        # Simulate some flight time
        import time
        time.sleep(1)
        
        success = engine.remove_occupant(1001, region1)
        logger.info(f"Drone 1001 exit: {'SUCCESS' if success else 'FAILED'}")
    
    # Scenario 2: Conflict resolution
    logger.info("--- Scenario 2: Priority conflict ---")
    
    # Low priority drone gets a region
    engine.reserve_region(1003, region2)
    logger.info("Low priority drone 1003 reserved region")
    
    # High priority drone tries to take it
    # Note: Current implementation doesn't handle priority override
    # This would show up as a conflict in logs
    success = engine.reserve_region(1002, region2)
    logger.info(f"High priority drone 1002 override attempt: {'SUCCESS' if success else 'FAILED'}")
    
    # Scenario 3: Unauthorized access attempt
    logger.info("--- Scenario 3: Security violation ---")
    
    # Try to occupy a region without reserving it first
    success = engine.add_occupant(1001, region3)
    logger.info(f"Unauthorized occupancy attempt: {'BLOCKED' if not success else 'ALLOWED'}")
    
    # Scenario 4: No-fly zone establishment
    logger.info("--- Scenario 4: Emergency no-fly zone ---")
    engine.mark_no_fly(region3)
    
    # Try to reserve the no-fly region
    success = engine.reserve_region(1001, region3)
    logger.info(f"Reservation in no-fly zone: {'BLOCKED' if not success else 'ALLOWED'}")
    
    logger.info("=== Drone operation simulation complete ===")
    
    # Print final region status
    print("\nFinal region status:")
    for region_id, region in engine.region_map.items():
        status, owner, priority = engine.query_region(region)
        print(f"  {region_id}: {status.name} (owner: {owner}, priority: {priority})")

def log_system_health():
    """Example of periodic system health logging"""
    
    perf_logger = logging.getLogger('airspace.performance')
    
    # This would typically be called periodically
    perf_logger.info("System health check - all systems operational")
    perf_logger.info("Active regions: 36, Reserved: 2, Occupied: 1, No-fly: 1")
    
    # Example metrics you might want to track:
    # - Total regions vs occupied regions
    # - Average reservation time
    # - Conflict frequency
    # - Response times
    # - Memory usage
    # - Database connection health

if __name__ == "__main__":
    try:
        main()
        log_system_health()
    except Exception as e:
        # Make sure critical errors are logged
        logger = logging.getLogger('airspace.engine')
        logger.critical(f"System failure: {e}", exc_info=True)
        raise