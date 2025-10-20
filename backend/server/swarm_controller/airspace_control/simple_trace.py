#!/usr/bin/env python3
"""
Concurrent trace with 3 drones moving through a 2x2x2 airspace.
Each drone moves through a sequence of regions, with >1 s delay between actions
to ensure distinct timesteps for visualization.
"""

import sys
import time
import asyncio
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from airspace_control_engine import AirspaceControlEngine
from airspace_visualizer import AirspaceVisualizer
from playback_parser import PlaybackEngine
from logger_config import setup_airspace_logging


# ------------------------------------------------------------
# Drone movement coroutine
# ------------------------------------------------------------
async def move_drone_through_region(engine, drone_id, positions):
    """Move one drone through a list of (lat, lon, alt) positions with explicit sim timesteps."""
    for step_num, (lat, lon, alt) in enumerate(positions, start=1):

        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            print(f"  Found region {region.region_id}")

            if engine.reserve_region(drone_id, region):
                await asyncio.sleep(1.1)

                if engine.add_occupant(drone_id, region):
                    await asyncio.sleep(1.1)

                    if engine.remove_occupant(drone_id, region):
                        await asyncio.sleep(1.1)
        else:
            print("  ERROR: No region found at position!")

    print(f"\nDrone {drone_id} complete.\n")



# ------------------------------------------------------------
# Main concurrent trace
# ------------------------------------------------------------
async def run_concurrent_trace():
    """Run a 3-drone concurrent trace with proper timing."""

    setup_airspace_logging(log_level=logging.INFO, log_dir="airspace_logs")

    # Define a simple 2x2x2 airspace
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
# Visualization after trace
# ------------------------------------------------------------
def create_visualization():
    """Parse logs and create visualization frames."""
    print("\n=== Creating Visualization ===")

    parser = PlaybackEngine()
    parser.read_file_to_mem('airspace_logs/airspace_control.log')
    parser.parse_log_file()

    visualizer = AirspaceVisualizer("parsed_regions.json", "parsed_tx.json")
    print(f"\nTotal timesteps: {visualizer.last_t + 1}")

    # Save sample frames
    frames_to_save = [0, 5, 10, 15, 20, 25, 30, visualizer.last_t]
    for frame in frames_to_save:
        if frame <= visualizer.last_t:
            filename = f"timed_frame_{frame:03d}.png"
            visualizer.render_timestep(frame, save_filename=filename)
            print(f"Saved {filename}")
    
    visualizer.render_animated()


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(run_concurrent_trace())
    create_visualization()
