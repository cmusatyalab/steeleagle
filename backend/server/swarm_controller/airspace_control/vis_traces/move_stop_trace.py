"""
Move-stop trace demonstrating drones that move to a destination and stop permanently.
Uses a 2x2x2 airspace with 2 drones that each fly to a single location,
occupy it, and remain stationary .
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
async def move_stop_drone(engine, drone_id, position, stop_duration=5.0):
    """
    Move drone to a single position and stop permanently.
    
    Args:
        engine: AirspaceControlEngine instance
        drone_id: Unique identifier for the drone
        position: Single (lat, lon, alt) tuple
        stop_duration: Time to occupy the region (seconds)
    """
    lat, lon, alt = position
    print(f"\nDrone {drone_id}: Moving to ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
    
    region = engine.get_region_from_point(lat, lon, alt)
    if region:
        print(f"  Found region {region.region_id}")
        
        # Reserve the region
        if engine.reserve_region(drone_id, region):
            print(f"  Drone {drone_id} reserved region {region.region_id}")
            await asyncio.sleep(1.1)
            
            # Enter and occupy the region
            if engine.add_occupant(drone_id, region):
                print(f"  Drone {drone_id} entered region {region.region_id}")
                await asyncio.sleep(1.1)
                
                # Stop and hold position permanently
                print(f"  Drone {drone_id} STOPPED - holding position indefinitely")
                for i in range(int(stop_duration)):
                    # Renew lease periodically while stopped
                    engine.renew_region(drone_id, region)
                    print(f"    Drone {drone_id} still holding (t+{i+1}s)")
                    await asyncio.sleep(1.1)
                
                print(f"  Drone {drone_id} remains stopped in region {region.region_id}")
            else:
                print(f"  ERROR: Drone {drone_id} failed to enter region!")
        else:
            print(f"  ERROR: Drone {drone_id} failed to reserve region!")
    else:
        print(f"  ERROR: No region found at position ({lat:.4f}, {lon:.4f}, {alt:.0f}m)!")
    
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
    
    # Define single destination for each drone - they will stop and remain there
    # Drone 1: Stops at northeast, low altitude
    # Drone 2: Stops at southwest, high altitude
    drone_destinations = {
        1: (37.7775, -122.4175, 50),   # NE, low - FINAL STOP
        2: (37.7725, -122.4125, 150),  # SW, high - FINAL STOP
    }
    
    print("\n=== Starting drone movements ===")
    print("Each drone will move to its destination and STOP permanently\n")
    
    # Run drones concurrently - each moves to one position and stops
    tasks = [
        asyncio.create_task(move_stop_drone(engine, drone_id, position, stop_duration=5.0))
        for drone_id, position in drone_destinations.items()
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
    
    # Save frames at key intervals
    frames_to_save = [0]
    for frame in range(visualizer.last_t):
        if frame % 5 == 0:
            frames_to_save.append(frame)
    frames_to_save.append(visualizer.last_t)
    
    for frame in frames_to_save:
        if frame <= visualizer.last_t:
            filename = f"move_stop_frame_{frame:03d}.png"
            visualizer.render_timestep(frame, save_filename=filename)
            print(f"Saved {filename}")
    
    print("\n=== Rendering animation ===")
    visualizer.render_animated()

# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    print("="*60)
    print("MOVE-STOP TRACE")
    print("="*60)
    
    asyncio.run(run_move_stop_trace())
    create_visualization()