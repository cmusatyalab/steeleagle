"""
Region splitting trace demonstrating dynamic airspace subdivision.
Starts with a coarse 2x2x2 grid, then splits specific regions.
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
# Drone flight coroutine with validation
# ------------------------------------------------------------
async def fly_drone_with_validation(engine, drone_id, positions, hold_time=2.0):
    """
    Fly drone through positions with position validation.
    
    Args:
        engine: AirspaceControlEngine instance
        drone_id: Unique identifier for the drone
        positions: List of (lat, lon, alt) tuples
        hold_time: Time to hold at each position
    """
    for step_num, (lat, lon, alt) in enumerate(positions, start=1):
        print(f"\nDrone {drone_id} - Waypoint {step_num}: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        
        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            if engine.reserve_region(drone_id, region):
                await asyncio.sleep(1.1)
                
                if engine.add_occupant(drone_id, region):
                    await asyncio.sleep(1.1)
                    
                    # Hold position with periodic renewals (no validation)
                    for _ in range(int(hold_time)):
                        engine.renew_region(drone_id, region)
                        await asyncio.sleep(1.1)
                    
                    if engine.remove_occupant(drone_id, region):
                        await asyncio.sleep(1.1)
        else:
            print(f"  ERROR: No region found at ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
    
    print(f"\nDrone {drone_id} flight complete\n")

# ------------------------------------------------------------
# Region splitting operations
# ------------------------------------------------------------
async def perform_region_splits(engine, split_sequence):
    """
    Execute a sequence of region splits.
    
    Args:
        engine: AirspaceControlEngine instance
        split_sequence: List of (lat, lon, alt, split_type, num_segments) tuples
    """
    for idx, (lat, lon, alt, split_type, num_segments) in enumerate(split_sequence, start=1):
        print(f"\n=== Split Operation {idx} ===")
        print(f"Target position: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        print(f"Split type: {split_type}, segments: {num_segments}")
        
        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            print(f"Found region {region.region_id} (c_id: {region.c_id})")
            
            # Check if region is available for splitting
            if region.get_owner() is None:
                print(f"Region is free - proceeding with split")
                
                # Perform the appropriate split
                if split_type == "latitude":
                    new_regions = engine.split_by_latitude(region, num_segments, is_set_up=False)
                elif split_type == "longitude":
                    new_regions = engine.split_by_longitude(region, num_segments, is_set_up=False)
                elif split_type == "altitude":
                    new_regions = engine.split_by_altitude(region, num_segments, is_set_up=False)
                else:
                    print(f"ERROR: Unknown split type '{split_type}'")
                    continue
                
                print(f"Split complete - created {len(new_regions)} new regions")
                for new_region in new_regions:
                    print(f"  New region: {new_region.region_id} (c_id: {new_region.c_id})")
            else:
                print(f"WARNING: Region occupied by drone {region.get_owner()} - cannot split")
        else:
            print(f"ERROR: No region found at split location")
        
        # Wait before next split
        await asyncio.sleep(2.0)

# ------------------------------------------------------------
# Main splitting trace
# ------------------------------------------------------------

async def run_split_trace():
    
    setup_airspace_logging(log_level=logging.INFO, log_dir="airspace_logs")
    
    # Start with coarse 2x2x2 grid
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
    print(f"INITIAL AIRSPACE: {len(engine.region_map)} regions (2x2x2 grid)")
    print(f"{'='*60}")
    
    await asyncio.sleep(1.0)
    
    # Register drones
    engine.set_priority(drone_id=1, new_priority=5)
    engine.set_priority(drone_id=2, new_priority=4)
    engine.set_priority(drone_id=3, new_priority=3)
    
    print("\nRegistered drones: 1 (priority 5), 2 (priority 4), 3 (priority 3)\n")
    
    # Phase 1: Initial drone movements in coarse grid
    print("\n" + "="*60)
    print("PHASE 1: Initial flights in coarse grid")
    print("="*60)
    
    phase1_paths = {
        1: [
            (37.7775, -122.4175, 50),   # NE, low
        ],
        2: [
            (37.7725, -122.4125, 150),  # SW, high
        ],
    }
    
    tasks = [
        asyncio.create_task(fly_drone_with_validation(engine, d_id, positions, hold_time=2.0))
        for d_id, positions in phase1_paths.items()
    ]
    await asyncio.gather(*tasks)
    
    # Phase 2: Split regions to create finer grid
    print("\n" + "="*60)
    print("PHASE 2: Dynamic region splitting")
    print("="*60)
    
    # Define splits: (lat, lon, alt, split_type, num_segments)
    split_sequence = [
        # Split a lower-altitude region by latitude
        (37.7750, -122.4150, 50, "latitude", 2),
        
        # Split a mid-altitude region by longitude  
        (37.7750, -122.4150, 100, "longitude", 2),
        
        # Split an upper-altitude region by altitude
        (37.7750, -122.4150, 150, "altitude", 2),
    ]
    
    await perform_region_splits(engine, split_sequence)
    
    print(f"\nAFTER SPLITS: {len(engine.region_map)} total regions")
    
    # Phase 3: Fly drones through newly created finer regions
    print("\n" + "="*60)
    print("PHASE 3: Flights through subdivided airspace")
    print("="*60)
    
    phase3_paths = {
        1: [
            (37.7760, -122.4160, 50),   # In split latitude region (north half)
            (37.7740, -122.4160, 50),   # In split latitude region (south half)
        ],
        2: [
            (37.7750, -122.4140, 100),  # In split longitude region (west half)
            (37.7750, -122.4160, 100),  # In split longitude region (east half)
        ],
        3: [
            (37.7750, -122.4150, 125),  # In split altitude region (lower half)
            (37.7750, -122.4150, 175),  # In split altitude region (upper half)
        ],
    }
    
    tasks = [
        asyncio.create_task(fly_drone_with_validation(engine, d_id, positions, hold_time=2.0))
        for d_id, positions in phase3_paths.items()
    ]
    await asyncio.gather(*tasks)
    
    print("\n" + "="*60)
    print("TRACE COMPLETE")
    print(f"Final airspace: {len(engine.region_map)} regions")
    print("="*60)
    
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
    
    # Save key frames
    frames_to_save = [0]  # Initial state
    
    # Add frames at regular intervals
    for frame in range(visualizer.last_t):
        if frame % 5 == 0:
            frames_to_save.append(frame)
    
    frames_to_save.append(visualizer.last_t)  # Final state
    
    for frame in frames_to_save:
        if frame <= visualizer.last_t:
            filename = f"split_frame_{frame:03d}.png"
            visualizer.render_timestep(frame, save_filename=filename)
            print(f"Saved {filename}")
    
    print("\n=== Rendering animation ===")
    visualizer.render_animated()

# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "="*60)
    print("REGION SPLITTING TRACE")
    print("="*60 + "\n")
    
    asyncio.run(run_split_trace())
    create_visualization()