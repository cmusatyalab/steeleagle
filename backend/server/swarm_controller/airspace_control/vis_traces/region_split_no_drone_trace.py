"""
Region splitting trace demonstrating dynamic airspace subdivision.
Starts with a coarse 2x2x2 grid, then progressively splits regions to create
finer-grained control areas. Shows all three split types (latitude, longitude, altitude).
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
    """Execute trace demonstrating progressive airspace segmentation."""
    
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
    
    # Phase 1: Show initial coarse grid
    print("\n" + "="*60)
    print("PHASE 1: Initial coarse segmentation")
    print("="*60)
    print(f"Current regions: {len(engine.region_map)}")
    print("Airspace is divided into 8 large cubic regions")
    await asyncio.sleep(2.0)
    
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
    print(" Altitude splits (Vertical division)")
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
    print("AIRSPACE SEGMENTATION DEMONSTRATION")
    print("Showing progressive region splitting across all three axes")
    print("="*60 + "\n")
    
    asyncio.run(run_split_trace())
    create_visualization()