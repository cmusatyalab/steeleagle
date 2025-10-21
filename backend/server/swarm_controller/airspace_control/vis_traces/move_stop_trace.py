"""
Move-stop trace demonstrating drones that move to a destination and stop permanently.
Uses a 2x2x2 airspace with 2 drones that each fly to a single location,
occupy it, and remain stationary.

Movement order: reserve region -> enter region -> stop and hold
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

# ------------------------------------------------------------
# Drone move-stop coroutine
# ------------------------------------------------------------
async def move_stop_drone(engine, drone_id, positions, stop_duration=10.0):
    """
    Move drone through positions, stopping at the final destination.
    
    Order of operations for each waypoint:
    1. Reserve the next region
    2. Exit previous region (if exists) + Enter new region
    3. At final position: Hold indefinitely
    
    Args:
        engine: AirspaceControlEngine instance
        drone_id: Unique identifier for the drone
        positions: List of (lat, lon, alt) tuples - will stop at last one
        stop_duration: Time to occupy the final region (seconds)
    """
    current_region = None
    
    for step_num, (lat, lon, alt) in enumerate(positions, start=1):
        is_final_position = (step_num == len(positions))
        
        print(f"\nDrone {drone_id} - Waypoint {step_num}/{len(positions)}: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        if is_final_position:
            print(f"  [FINAL DESTINATION]")
        
        next_region = engine.get_region_from_point(lat, lon, alt)
        if next_region:
            print(f"  Found region {next_region.region_id}")
            
            # Step 1: Reserve the next region
            if engine.reserve_region(drone_id, next_region):
                print(f"  Drone {drone_id} reserved region {next_region.region_id}")
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
                        print(f"  Drone {drone_id} STOPPED - holding position indefinitely")
                        for i in range(int(stop_duration)):
                            engine.renew_region(drone_id, next_region)
                            if i % 2 == 0:
                                print(f"    Drone {drone_id} still holding (t+{i+1}s)")
                            await asyncio.sleep(1.1)
                        print(f"  Drone {drone_id} remains stopped in region {next_region.region_id}")
                else:
                    print(f"  ERROR: Drone {drone_id} failed to enter region!")
                    return
            else:
                print(f"  ERROR: Drone {drone_id} failed to reserve region!")
                return
        else:
            print(f"  ERROR: No region found at position!")
            return
    
    print(f"\n=== Drone {drone_id} completed - STOPPED at final position ===\n")

# ------------------------------------------------------------
# Main move-stop trace
# ------------------------------------------------------------

async def run_move_stop_trace():
    """Execute the move-stop trace with two drones."""
    
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
    
    print(f"\n=== Airspace Initialized ===")
    print(f"Created airspace with {len(engine.region_map)} regions (2x2x2 grid)")
    
    await asyncio.sleep(1.0)
    
    # Register two drones with different priorities
    engine.set_priority(drone_id=1, new_priority=5)
    engine.set_priority(drone_id=2, new_priority=4)
    
    print("\nRegistered drones 1 and 2")
    print("Drone 1 priority: 5 (higher)")
    print("Drone 2 priority: 4 (lower)")
    
    # Define paths for each drone - they will stop at the last position
    # Each drone moves through one intermediate position before stopping
    drone_paths = {
        1: [
            (37.7750, -122.4150, 50),   # Start: Center, low
            (37.7775, -122.4175, 50),   # FINAL STOP: NE, low
        ],
        2: [
            (37.7750, -122.4150, 150),  # Start: Center, high
            (37.7725, -122.4125, 150),  # FINAL STOP: SW, high
        ],
    }
    
    tasks = [
    asyncio.create_task(move_stop_drone(engine, drone_id, path, stop_duration=5.0))
    for drone_id, path in drone_paths.items()  # Changed from 'positions' to 'path'
]
    
    await asyncio.gather(*tasks)
    
    print("\n=== All drone movements complete ===")
    await asyncio.sleep(1.0)
    
    return engine

# ------------------------------------------------------------
# Visualization Playback
# ------------------------------------------------------------

def create_visualization():
    """Parse logs and create visualization frames."""
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
    print("="*60)
    print("MOVE-STOP TRACE")
    print("Demonstrating drones moving to destination and stopping permanently")
    print("="*60)
    
    asyncio.run(run_move_stop_trace())
    create_visualization()