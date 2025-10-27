"""
Priority deconfliction trace demonstrating two drones attempting to reserve
the same region, with the higher priority drone winning.

Scenario:
- Two drones start at different positions
- Both move toward and attempt to reserve the same central region
- Higher priority drone gets the region
- Lower priority drone is blocked and must wait/stop
"""

import sys
import time
import asyncio
import logging
from pathlib import Path

script_dir = Path(__file__).resolve().parent
module_dir = script_dir.parent
sys.path.append(str(module_dir))

from airspace_control_engine import AirspaceControlEngine
from airspace_visualizer import AirspaceVisualizer
from playback_parser import PlaybackEngine
from logger_config import setup_airspace_logging
import airspace_region as asr

# ------------------------------------------------------------
# Drone movement with conflict detection
# ------------------------------------------------------------
async def move_drone_with_conflict(engine, drone_id, positions, stop_duration=10.0):
    """
    Move drone through positions, attempting to reserve each region.
    
    Order of operations for each waypoint:
    1. Attempt to reserve the next region
    2. If successful: Exit previous + Enter new, continue or stop at final
    3. If blocked: Report conflict and stop
    
    Args:
        engine: AirspaceControlEngine instance
        drone_id: Unique identifier for the drone
        positions: List of (lat, lon, alt) tuples
        stop_duration: Time to hold at final position if reached
    """
    current_region = None
    priority = engine.drone_priority_map.get(drone_id, 0)
    
    for step_num, (lat, lon, alt) in enumerate(positions, start=1):
        is_final_position = (step_num == len(positions))
        
        print(f"\nDrone {drone_id} (priority {priority}) - Waypoint {step_num}/{len(positions)}: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        if is_final_position:
            print(f"  [TARGET DESTINATION]")
        
        next_region = engine.get_region_from_point(lat, lon, alt)
        if next_region:
            print(f"  Found region {next_region.region_id}")
            
            # Check current status
            region_owner = next_region.get_owner()
            region_status = next_region.get_status()
            
            if region_owner is not None and region_owner != drone_id:
                owner_priority = engine.drone_priority_map.get(region_owner, 0)
                print(f"  CONFLICT: Region occupied by Drone {region_owner} (priority {owner_priority})")
                
                if priority > owner_priority:
                    print(f"  Drone {drone_id} has higher priority - attempting override")
                else:
                    print(f"  BLOCKED: Drone {drone_id} has lower/equal priority - cannot proceed")
                    print(f"  Drone {drone_id} STOPPING at current position")
                    
                    # Hold at current position if we have one
                    if current_region:
                        print(f"  Holding in region {current_region.region_id}")
                        for i in range(int(stop_duration)):
                            engine.renew_region(drone_id, current_region)
                            if i % 2 == 0:
                                print(f"    Drone {drone_id} blocked - holding (t+{i+1}s)")
                            await asyncio.sleep(1.1)
                    
                    print(f"\n=== Drone {drone_id} BLOCKED - Unable to reach destination ===\n")
                    return False
            
            # Step 1: Attempt to reserve the region
            if engine.reserve_region(drone_id, next_region):
                print(f"  Reserved region {next_region.region_id}")
                await asyncio.sleep(1.1)
                
                # Step 2: Exit previous and enter new
                if current_region:
                    engine.remove_occupant(drone_id, current_region)
                    print(f"  Exited region {current_region.region_id}")
                
                if engine.add_occupant(drone_id, next_region):
                    print(f"  Entered region {next_region.region_id}")
                    await asyncio.sleep(1.1)
                    
                    current_region = next_region
                    
                    # Step 3: If final position, stop and hold
                    if is_final_position:
                        print(f"  Drone {drone_id} reached destination - STOPPING")
                        for i in range(int(stop_duration)):
                            engine.renew_region(drone_id, next_region)
                            if i % 2 == 0:
                                print(f"    Drone {drone_id} holding at destination (t+{i+1}s)")
                            await asyncio.sleep(1.1)
                        print(f"  Drone {drone_id} remains at destination {next_region.region_id}")
                else:
                    print(f"  ERROR: Failed to enter region!")
                    return False
            else:
                print(f"  ERROR: Reservation failed!")
                print(f"  Drone {drone_id} STOPPING at current position")
                
                if current_region:
                    for i in range(int(stop_duration)):
                        engine.renew_region(drone_id, current_region)
                        if i % 2 == 0:
                            print(f"    Drone {drone_id} holding (t+{i+1}s)")
                        await asyncio.sleep(1.1)
                
                return False
        else:
            print(f"  ERROR: No region found at position!")
            return False
    
    print(f"\n=== Drone {drone_id} completed - At destination ===\n")
    return True

# ------------------------------------------------------------
# Main priority deconfliction trace
# ------------------------------------------------------------

async def run_priority_trace():
    """Execute trace demonstrating priority-based deconfliction in restricted airspace."""
    
    setup_airspace_logging(log_level=logging.INFO, log_dir="airspace_logs")
    
    # Define airspace
    corners = [
        (37.7800, -122.4200),
        (37.7700, -122.4200),
        (37.7700, -122.4100),
        (37.7800, -122.4100),
    ]
    
    engine = AirspaceControlEngine(
        region_corners=corners,
        lat_partitions=2,
        lon_partitions=2,
        alt_partitions=2,
        min_alt=0,
        max_alt=200
    )
    
    print(f"\n{'='*60}")
    print(f"PRIORITY DECONFLICTION IN RESTRICTED AIRSPACE")
    print(f"{'='*60}")
    print(f"Airspace: {len(engine.region_map)} regions (2x2x2 grid)")
    
    await asyncio.sleep(1.0)
    
    # Mark the central region as RESTRICTED before drones start
    print("\n" + "="*60)
    print("ESTABLISHING RESTRICTED AIRSPACE")
    print("="*60)
    
    restricted_region = engine.get_region_from_point(37.7750, -122.4150, 50)
    if restricted_region:
        print(f"Target region: {restricted_region.region_id} (c_id: {restricted_region.c_id})")
        if engine.mark_restricted_fly(restricted_region):
            restricted_region.update_status(asr.RegionStatus.RESTRICTED_AVAILABLE)
            print(f"Region {restricted_region.region_id} marked as RESTRICTED")
            print(f"Only authorized/high-priority drones may enter")
            await asyncio.sleep(1.1)
    
    # Register two drones with different priorities
    engine.set_priority(drone_id=1, new_priority=2)  # Higher priority
    engine.set_priority(drone_id=2, new_priority=0)  # Lower priority
    
    print("\nDrone priorities:")
    print("  Drone 1: Priority 5 (HIGHER - authorized for restricted)")
    print("  Drone 2: Priority 3 (LOWER - may be denied)")
    
    # Define paths - both drones converge on the same restricted central region
    drone_paths = {
        1: [
            (37.7775, -122.4175, 50),   # Start: NE, low
            (37.7750, -122.4150, 50),   # Destination: Center, low (RESTRICTED CONFLICT POINT)
        ],
        2: [
            (37.7725, -122.4125, 50),   # Start: SW, low
            (37.7750, -122.4150, 50),   # Destination: Center, low (RESTRICTED CONFLICT POINT)
        ],
    }
    
    print("\nFlight paths (both target the same RESTRICTED region):")
    for drone_id, path in drone_paths.items():
        priority = engine.drone_priority_map[drone_id]
        print(f"\n  Drone {drone_id} (priority {priority}):")
        for i, pos in enumerate(path, 1):
            marker = " <- RESTRICTED CONFLICT ZONE" if i == 2 else ""
            print(f"    {i}. ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.0f}m){marker}")
    
    print(f"\n{'='*60}")
    print(f"Starting concurrent flights...")
    print(f"Both drones will attempt to enter restricted airspace")
    print(f"{'='*60}\n")
    
    await asyncio.sleep(2.0)
    
    # Launch both drones concurrently
    tasks = [
        asyncio.create_task(move_drone_with_conflict(engine, drone_id, path, stop_duration=5.0))
        for drone_id, path in drone_paths.items()
    ]
    
    results = await asyncio.gather(*tasks)
    
    print(f"\n{'='*60}")
    print(f"SCENARIO COMPLETE - Results:")
    print(f"{'='*60}")
    for drone_id, reached_destination in enumerate(results, 1):
        priority = engine.drone_priority_map[drone_id]
        status = "REACHED DESTINATION" if reached_destination else "BLOCKED"
        print(f"  Drone {drone_id} (priority {priority}): {status}")
    
    print(f"\n{'='*60}")
    print(f"Priority system successfully managed restricted airspace")
    print(f"Higher priority drone secured the contested restricted region")
    print(f"{'='*60}")
    
    await asyncio.sleep(1.0)
    return engine

# ------------------------------------------------------------
# Visualization
# ------------------------------------------------------------

def create_visualization():
    """Parse logs and create visualization."""
    print("\n=== Creating Visualization ===")
    
    parser = PlaybackEngine()
    parser.read_file_to_mem('airspace_logs/airspace_control.log')
    parser.parse_log_file()
    
    visualizer = AirspaceVisualizer("parsed_regions.json", "parsed_tx.json")
    print(f"\nTotal timesteps: {visualizer.last_t + 1}")
    
    print("\n=== Rendering animation ===")
    visualizer.render_animated()

# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "="*60)
    print("PRIORITY DECONFLICTION IN RESTRICTED AIRSPACE")
    print("Demonstrating priority-based access to restricted zones")
    print("="*60 + "\n")
    
    asyncio.run(run_priority_trace())
    create_visualization()