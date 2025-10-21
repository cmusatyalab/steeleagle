"""
Concurrent trace with 3 drones moving through a 2x2x2 airspace.
Each drone moves through a sequence of regions, with >1 s delay between actions
to ensure distinct timesteps for visualization.

Movement order: reserve next region -> exit previous + enter new (simultaneously)
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
# Drone movement coroutine
# ------------------------------------------------------------
async def move_drone_through_region(engine, drone_id, positions):
    """
    Move one drone through a list of (lat, lon, alt) positions.
    
    Order of operations:
    1. Reserve the next region
    2. Remove from previous region (if exists)
    3. Add to new region (appears simultaneous with step 2)
    """
    current_region = None
    
    for step_num, (lat, lon, alt) in enumerate(positions, start=1):
        print(f"\nDrone {drone_id} - Waypoint {step_num}: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        
        next_region = engine.get_region_from_point(lat, lon, alt)
        if next_region:
            print(f"  Found region {next_region.region_id}")

            # Step 1: Reserve the next region
            if engine.reserve_region(drone_id, next_region):
                print(f"    Reserved region {next_region.region_id}")
                await asyncio.sleep(1.1)
                
                # Step 2 & 3: Exit previous and enter new (simultaneously)
                if current_region:
                    engine.remove_occupant(drone_id, current_region)
                    print(f"    Exited region {current_region.region_id}")
                
                if engine.add_occupant(drone_id, next_region):
                    print(f"    Entered region {next_region.region_id}")
                    await asyncio.sleep(1.1)
                    
                    # Update current region tracker
                    current_region = next_region
            else:
                print(f"   Failed to reserve region")
        else:
            print("   ERROR: No region found at position!")

    # Clean up: exit final region
    if current_region:
        engine.remove_occupant(drone_id, current_region)
        print(f"    Exited final region {current_region.region_id}")
        await asyncio.sleep(1.1)

    print(f"\nDrone {drone_id} complete.\n")
    
# ------------------------------------------------------------
# Main concurrent trace
# ------------------------------------------------------------

async def run_movement_trace():
    
    setup_airspace_logging(log_level=logging.INFO, log_dir="airspace_logs")

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

    print(f"Created airspace with {len(engine.region_map)} regions (2x2x2 grid)")

    # Give system a moment to initialize
    await asyncio.sleep(1.0)

    # Register three drones with different priorities
    engine.set_priority(drone_id=1, new_priority=5)
    engine.set_priority(drone_id=2, new_priority=4)
    engine.set_priority(drone_id=3, new_priority=3)

    print("\nRegistered drones 1, 2, and 3.\n")

    # Define position sequences for each drone
    drone_paths = {
        1: [
            (37.7750, -122.4150, 50),
            (37.7750, -122.4150, 150),
            (37.7775, -122.4175, 150),
        ],
        2: [
            (37.7725, -122.4125, 50),
            (37.7725, -122.4175, 100),
            (37.7775, -122.4175, 150),
        ],
        3: [
            (37.7775, -122.4125, 50),
            (37.7750, -122.4125, 100),
            (37.7725, -122.4125, 150),
        ],
    }

    # Run drones concurrently
    tasks = [
        asyncio.create_task(move_drone_through_region(engine, drone_id, positions))
        for drone_id, positions in drone_paths.items()
    ]

    await asyncio.gather(*tasks)

    print("\n=== All drone movements complete ===")
    await asyncio.sleep(1.0)
    return engine

# ------------------------------------------------------------
# Visualization Playback after trace
# ------------------------------------------------------------

def create_visualization():
    """Parse logs and create visualization frames."""
    print("\n=== Creating Visualization ===")

    parser = PlaybackEngine()
    parser.read_file_to_mem('airspace_logs/airspace_control.log')
    parser.parse_log_file()

    visualizer = AirspaceVisualizer("parsed_regions.json", "parsed_tx.json")
    print(f"\nTotal timesteps: {visualizer.last_t + 1}")
    
    visualizer.render_animated()
    
# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("BASIC DRONE MOVEMENT TRACE")
    print("="*60 + "\n")
    
    asyncio.run(run_movement_trace())
    create_visualization()