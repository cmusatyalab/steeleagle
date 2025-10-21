"""
Region splitting trace demonstrating dynamic airspace subdivision.
Starts with a coarse 2x2x2 grid, then progressively splits regions to create
finer-grained control areas. Drones hold positions near regions being split
to show the dynamic nature of the segmentation.
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
# Drone holding pattern
# ------------------------------------------------------------
async def drone_hold_position(engine, drone_id, position, hold_duration=10.0):
    """
    Drone moves to a position and holds while splits occur nearby.
    
    Args:
        engine: AirspaceControlEngine instance
        drone_id: Unique identifier for the drone
        position: Single (lat, lon, alt) tuple
        hold_duration: Time to hold position (seconds)
    """
    lat, lon, alt = position
    print(f"\nDrone {drone_id} moving to holding position: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
    
    region = engine.get_region_from_point(lat, lon, alt)
    if region:
        print(f"  Found region {region.region_id}")
        
        if engine.reserve_region(drone_id, region):
            print(f"  ✓ Reserved region")
            await asyncio.sleep(1.1)
            
            if engine.add_occupant(drone_id, region):
                print(f"  ✓ Entered region - HOLDING POSITION")
                await asyncio.sleep(1.1)
                
                # Hold position while splits occur
                for i in range(int(hold_duration)):
                    engine.renew_region(drone_id, region)
                    if i % 3 == 0:
                        print(f"    Drone {drone_id} holding (t+{i+1}s)...")
                    await asyncio.sleep(1.1)
                
                # Exit after holding
                if engine.remove_occupant(drone_id, region):
                    print(f"  ✓ Exited region")
                    await asyncio.sleep(1.1)
    
    print(f"Drone {drone_id} completed holding pattern\n")

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
    """Execute trace demonstrating region splitting with drones holding nearby."""
    
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
    
    await asyncio.sleep(2.0)
    
    # Register drones
    engine.set_priority(drone_id=1, new_priority=5)
    engine.set_priority(drone_id=2, new_priority=4)
    
    print("\nRegistered drones: 1 (priority 5), 2 (priority 4)\n")
    
    # Phase 1: Drones move to holding positions
    print("\n" + "="*60)
    print("PHASE 1: Drones move to holding positions")
    print("="*60)
    
    # Positions adjacent to regions that will be split
    holding_positions = {
        1: (37.7775, -122.4175, 50),   # NE, low
        2: (37.7725, -122.4125, 150),  # SW, high
    }
    
    print("Drones moving to holding positions...")
    
    # Move drones to positions using proper order: reserve -> enter
    for drone_id, (lat, lon, alt) in holding_positions.items():
        print(f"\nDrone {drone_id} moving to: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            # Step 1: Reserve the region
            if engine.reserve_region(drone_id, region):
                print(f"  Reserved region {region.region_id}")
                await asyncio.sleep(1.1)
                
                # Step 2: Enter region (no previous to exit)
                if engine.add_occupant(drone_id, region):
                    print(f"  Drone {drone_id} now holding in region {region.region_id}")
                    await asyncio.sleep(1.1)
    
    print("\nBoth drones are now holding positions")
    await asyncio.sleep(2.0)
    
    # Phase 2: Altitude split - while drones hold
    print("\n" + "="*60)
    print("PHASE 2: Altitude split (Vertical division)")
    print("Drones are holding in adjacent regions")
    print("="*60)
    
    # Renew leases before split
    for drone_id, (lat, lon, alt) in holding_positions.items():
        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            engine.renew_region(drone_id, region)
    await asyncio.sleep(1.1)
    
    alt_split_sequence = [
        (37.7750, -122.4150, 100, "altitude", 2),   # Center, mid altitude
    ]
    
    await perform_region_splits(engine, alt_split_sequence)
    print(f"\nAfter altitude split: {len(engine.region_map)} regions")
    
    # Renew leases after split
    for drone_id, (lat, lon, alt) in holding_positions.items():
        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            engine.renew_region(drone_id, region)
    await asyncio.sleep(2.0)
    
    # Phase 3: Drones move into newly created split regions
    print("\n" + "="*60)
    print("PHASE 3: Drones move into newly created regions")
    print("="*60)
    
    # New positions in the split regions (center area that was just split)
    # The center was split by altitude, so we have lower and upper halves
    new_positions = {
        1: (37.7750, -122.4150, 75),   # Center, lower half of split (0-100m split into 0-50, 50-100)
        2: (37.7750, -122.4150, 125),  # Center, upper half of split (100-200m split into 100-150, 150-200)
    }
    
    print("\nDrones moving to newly created regions from the split...")
    
    # Move drones into the new split regions using proper order
    for drone_id, (lat, lon, alt) in new_positions.items():
        print(f"\nDrone {drone_id} moving to split region: ({lat:.4f}, {lon:.4f}, {alt:.0f}m)")
        next_region = engine.get_region_from_point(lat, lon, alt)
        if next_region:
            print(f"  Found region {next_region.region_id} (created from split)")
            
            # Step 1: Reserve the new region
            if engine.reserve_region(drone_id, next_region):
                print(f"  Reserved region {next_region.region_id}")
                await asyncio.sleep(1.1)
                
                # Step 2: Exit old region and enter new (simultaneously)
                old_position = holding_positions[drone_id]
                old_region = engine.get_region_from_point(*old_position)
                if old_region:
                    engine.remove_occupant(drone_id, old_region)
                    print(f"  Exited region {old_region.region_id}")
                
                if engine.add_occupant(drone_id, next_region):
                    print(f"  Drone {drone_id} now in newly created region")
                    await asyncio.sleep(1.1)
    
    print("\nBoth drones are now occupying the newly split regions")
    
    # Hold briefly to show occupancy
    for _ in range(3):
        for drone_id, (lat, lon, alt) in new_positions.items():
            region = engine.get_region_from_point(lat, lon, alt)
            if region:
                engine.renew_region(drone_id, region)
        await asyncio.sleep(1.1)
    
    # Phase 4: Drones exit
    print("\n" + "="*60)
    print("PHASE 6: Drones exiting")
    print("="*60)
    
    for drone_id, (lat, lon, alt) in new_positions.items():
        region = engine.get_region_from_point(lat, lon, alt)
        if region:
            if engine.remove_occupant(drone_id, region):
                print(f"  Drone {drone_id} exited region {region.region_id}")
                await asyncio.sleep(1.1)
    
    print("\n" + "="*60)
    print("AIRSPACE SEGMENTATION COMPLETE")
    print(f"Final airspace: {len(engine.region_map)} regions")
    print(f"Started with: 8 regions (2x2x2)")
    print(f"Altitude split created: {len(engine.region_map) - 8} additional region")
    print("\nDemonstrated:")
    print(" Altitude split (Vertical division)")
    print("\nDrones held positions in adjacent regions during split")
    print("="*60)
    
    await asyncio.sleep(2.0)
    return engine
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
    
    await asyncio.sleep(2.0)
    
    # Phase 1: Show initial coarse grid
    print("\n" + "="*60)
    print("PHASE 1: Initial coarse segmentation")
    print("="*60)
    print(f"Current regions: {len(engine.region_map)}")
    print("Airspace is divided into 8 large cubic regions")
    await asyncio.sleep(3.0)
    
    # Phase 2: Latitude split - divide north-south
    print("\n" + "="*60)
    print("PHASE 2: Latitude splitting (North-South division)")
    print("="*60)
    
    lat_split_sequence = [
        (37.7775, -122.4175, 50, "latitude", 2),   # NE corner, lower altitude
    ]
    
    print("Splitting one region along latitude axis...")
    await perform_region_splits(engine, lat_split_sequence)
    print(f"\nAfter latitude split: {len(engine.region_map)} regions")
    await asyncio.sleep(3.0)
    
    # Phase 3: Longitude split - divide east-west
    print("\n" + "="*60)
    print("PHASE 3: Longitude splitting (East-West division)")
    print("="*60)
    
    lon_split_sequence = [
        (37.7725, -122.4125, 100, "longitude", 2),  # SW corner, mid altitude
    ]
    
    print("Splitting one region along longitude axis...")
    await perform_region_splits(engine, lon_split_sequence)
    print(f"\nAfter longitude split: {len(engine.region_map)} regions")
    await asyncio.sleep(3.0)
    
    # Phase 4: Altitude split - divide vertically
    print("\n" + "="*60)
    print("PHASE 4: Altitude splitting (Vertical division)")
    print("="*60)
    
    alt_split_sequence = [
        (37.7725, -122.4175, 150, "altitude", 2),  # SE corner, upper altitude
    ]
    
    print("Splitting one region along altitude axis...")
    await perform_region_splits(engine, alt_split_sequence)
    print(f"\nAfter altitude split: {len(engine.region_map)} regions")
    await asyncio.sleep(3.0)
    
    # Phase 5: Additional split demonstration
    print("\n" + "="*60)
    print("PHASE 5: Additional segmentation")
    print("="*60)
    
    fine_split_sequence = [
        (37.7775, -122.4175, 150, "latitude", 2),    # NE corner, upper altitude - simple 2-way split
    ]
    
    print("Creating additional regions for demonstration...")
    await perform_region_splits(engine, fine_split_sequence)
    print(f"\nAfter additional split: {len(engine.region_map)} regions")
    await asyncio.sleep(3.0)
    
    print("\n" + "="*60)
    print("AIRSPACE SEGMENTATION COMPLETE")
    print(f"Final airspace: {len(engine.region_map)} regions")
    print(f"Started with: 8 regions (2x2x2)")
    print(f"Progressive refinement created: {len(engine.region_map) - 8} additional regions")
    print("\nDemonstrated split types:")
    print(" Latitude splits (North-South division)")
    print(" Longitude splits (East-West division)")
    print("  Altitude splits (Vertical division)")
    print("="*60)
    
    await asyncio.sleep(2.0)
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
    print("REGION SPLITTING WITH DRONE OPERATIONS")
    print("Drones hold positions while airspace is subdivided by altitude")
    print("="*60 + "\n")
    
    asyncio.run(run_split_trace())
    create_visualization()