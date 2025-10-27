"""
Single drone no-fly zone trace demonstrating a drone attempting to enter
a region marked as no-fly and being blocked.

Scenario:
- One drone attempts to fly through a planned route
- A region in the path is marked as NO-FLY
- Drone detects the no-fly zone and is unable to proceed
- Drone stops at the last safe position

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
# Drone movement with no-fly detection
# ------------------------------------------------------------
async def move_drone_with_nofly_check(engine, drone_id, positions, hold_duration=10.0):
    """
    Move drone through positions, checking for no-fly zones.
    
    Order of operations for each waypoint:
    1. Check if next region is a no-fly zone
    2. If safe: Reserve the region
    3. If safe: Exit previous + Enter new
    4. If no-fly: Stop at current position
    
    Args:
        engine: AirspaceControlEngine instance
        drone_id: Unique identifier for the drone
        positions: List of (lat, lon, alt) tuples
        hold_duration: Time to hold at final safe position
    """
    current_region = None
    
    for step_num, (lat, lon, alt) in enumerate(positions, start=1):
        is_final_position = (step_num == len(positions))
        
        print(f"\nDrone {drone_id} - Waypoint {step_num}/{len(positions)}: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        
        next_region = engine.get_region_from_point(lat, lon, alt)
        if next_region:
            print(f"  Found region {next_region.region_id}")
            
            # Step 1: Check for no-fly zone
            region_status = next_region.get_status()
            if region_status == asr.RegionStatus.NOFLY:
                print(f"  Region {next_region.region_id} is marked as NO-FLY")
                
                # Stop at current safe position
                if current_region:
                    print(f"  Stopping at safe position in region {current_region.region_id}")
                    for i in range(int(hold_duration)):
                        engine.renew_region(drone_id, current_region)
                        if i % 2 == 0:
                            print(f"    Drone {drone_id} holding at safe position (t+{i+1}s)")
                        await asyncio.sleep(1.1)
                else:
                    print(f"  Drone {drone_id} has no safe position - mission aborted")
                
                print(f"\n=== Drone {drone_id} STOPPED - No-fly zone blocked path ===\n")
                return False
            
            # Step 2: Reserve the region (safe to proceed)
            if engine.reserve_region(drone_id, next_region):
                print(f"  Reserved region {next_region.region_id}")
                await asyncio.sleep(2)
                
                # Step 3: Exit previous and enter new
                if current_region:
                    engine.remove_occupant(drone_id, current_region)
                    print(f"  Exited region {current_region.region_id}")
                
                if engine.add_occupant(drone_id, next_region):
                    print(f"  Entered region {next_region.region_id}")
                    await asyncio.sleep(1.1)
                    
                    current_region = next_region
                    
                    # If final position, hold there
                    if is_final_position:
                        print(f"  Drone {drone_id} reached destination - holding position")
                        for i in range(int(hold_duration)):
                            engine.renew_region(drone_id, next_region)
                            if i % 2 == 0:
                                print(f"    Drone {drone_id} at destination (t+{i+1}s)")
                            await asyncio.sleep(1.1)
                else:
                    print(f"  ERROR: Failed to enter region!")
                    return False
            else:
                print(f"  ERROR: Reservation failed!")
                return False
        else:
            print(f"  ERROR: No region found at position!")
            return False
    
    print(f"\n=== Drone {drone_id} completed - Reached destination ===\n")
    return True

# ------------------------------------------------------------
# Main no-fly trace
# ------------------------------------------------------------

async def run_single_drone_nofly_trace():
    """Execute trace demonstrating single drone encountering no-fly zone."""
    
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
    print(f"SINGLE DRONE NO-FLY ZONE SCENARIO")
    print(f"{'='*60}")
    print(f"Airspace: {len(engine.region_map)} regions (2x2x2 grid)")
    
    await asyncio.sleep(1.0)
    
    # Register drone
    engine.set_priority(drone_id=1, new_priority=5)
    
    print("\nRegistered Drone 1 (priority 5)")
    
    # Define flight path
    drone_path = [
        (37.7775, -122.4175, 50),   # Start: NE, low
        (37.7750, -122.4150, 50),   # Waypoint 2: Center, low (will be NO-FLY)
        (37.7725, -122.4125, 50),   # Destination: SW, low (won't reach)
    ]
    
    print("\nPlanned flight path:")
    for i, pos in enumerate(drone_path, 1):
        marker = " <- NO-FLY ZONE" if i == 2 else ""
        print(f"  {i}. ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.0f}m){marker}")
    
    # Mark the center region as NO-FLY before drone starts
    print(f"\n{'='*60}")
    print(f"ESTABLISHING NO-FLY ZONE")
    print(f"{'='*60}")
    
    nofly_region = engine.get_region_from_point(37.7750, -122.4150, 50)
    if nofly_region:
        print(f"Target region: {nofly_region.region_id} (c_id: {nofly_region.c_id})")
        if engine.mark_no_fly(nofly_region):
            nofly_region.update_status(asr.RegionStatus.NOFLY)
            print(f"Region {nofly_region.region_id} marked as NO-FLY ZONE (RED)")
            await asyncio.sleep(1.1)
    
    print(f"\n{'='*60}")
    print(f"Starting drone flight...")
    print(f"Drone will attempt to fly through no-fly zone")
    print(f"{'='*60}\n")
    
    await asyncio.sleep(2.0)
    
    # Fly the drone
    reached_destination = await move_drone_with_nofly_check(engine, 1, drone_path, hold_duration=5.0)
    
    print(f"\n{'='*60}")
    print(f"SCENARIO COMPLETE")
    print(f"{'='*60}")
    if reached_destination:
        print(f"  Drone 1: REACHED DESTINATION (unexpected!)")
    else:
        print(f"  Drone 1: BLOCKED by no-fly zone")
        print(f"  No-fly zone successfully prevented unauthorized entry")
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
    
    print("\nColor legend:")
    print("  RED = NO-FLY zone")
    print("  BLUE = ALLOCATED (reserved)")
    print("  GREEN = OCCUPIED (drone present)")
    
    
    print("\n=== Rendering animation ===")
    visualizer.render_animated(1500)

# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "="*60)
    print("SINGLE DRONE NO-FLY ZONE TRACE")
    print("Demonstrating no-fly zone detection and avoidance")
    print("="*60 + "\n")
    
    asyncio.run(run_single_drone_nofly_trace())
    create_visualization()