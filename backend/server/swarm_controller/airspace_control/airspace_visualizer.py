import json
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import animation
import numpy as np
import PIL
import sys

from airspace_region import RegionStatus

class AirspaceVisualizer():
    def __init__(self, region_fname, tx_fname):
        self.read_json_files(region_fname, tx_fname)
        self.extract_region_volumes()
        self.extract_region_timebounds()
        self.extract_active_regions()
        self.extract_voxel_dims_lists()
        self.extract_region_status_dicts()
        self.init_render_objs()
        self.calculate_voxels()
    
    def read_json_files(self, region_fname, tx_fname):
        with open(region_fname, 'r') as file:
            self.region_data = json.load(file)
        with open(tx_fname, 'r') as file:
            self.tx_data = json.load(file)

    def extract_region_volumes(self):
        self.region_volumes = []
        for key in self.region_data.keys():
            self.region_volumes.append(self.produce_volume_corners(self.region_data[key][0])) # single item list w/ dict

    def extract_region_timebounds(self):
        self.last_t = -1
        self.region_times = [(-1, -1) for i in range(len(self.region_volumes))]
        for steps in self.tx_data:
            curr_step = steps['t_step']
            if curr_step > self.last_t:
                self.last_t = curr_step
            for tx in steps['transactions']:
                region_idx = tx['cid']
                if 'CREATE' in tx['tx_type']:
                    self.region_times[region_idx] = (curr_step, self.region_times[region_idx][1])
                if 'SPLIT' in tx['tx_type']:
                    self.region_times[region_idx] = (self.region_times[region_idx][0], curr_step)            

    def extract_active_regions(self):
        self.active_regions_by_tstep = []
        for i in range(self.last_t + 1):
            self.active_regions_by_tstep.append(self.select_regions_timestep(i))

    def select_regions_timestep(self, timestep):
        active_reg = []
        for i in range(len(self.region_times)):
            r_times = self.region_times[i]
            if timestep >= r_times[0] and (timestep < r_times[1] or r_times[1] == -1): # -1 if active at log end
                active_reg.append(i)
        return active_reg

    def extract_voxel_dims_lists(self):
        self.voxel_dims_by_tstep = []
        for i in range(self.last_t + 1):
            self.voxel_dims_by_tstep.append(self.produce_voxel_dims_timestep(i))

    def produce_voxel_dims_timestep(self, timestep):
        lat_set = set()
        lon_set = set()
        alt_set = set()
        active_reg = self.active_regions_by_tstep[timestep]
        for id in active_reg:
            region = self.region_volumes[id]
            a = region[0] # low top left
            b = region[6] # hi bot right
            lat_set.update([a[0], b[0]])
            lon_set.update([a[1], b[1]])
            alt_set.update([a[2], b[2]])
        lat_list = list(lat_set)
        lon_list = list(lon_set)
        alt_list = list(alt_set)
        lat_list.sort()
        lon_list.sort()
        alt_list.sort()
        result = (lat_list, lon_list, alt_list)
        return result

    # low level then high level, top left, bottom left, bottom right, top right
    def produce_volume_corners(self, r_data):
        min_alt = r_data['min_alt']
        max_alt = r_data['max_alt']
        corners = r_data['corners']
        lo = []
        hi = []
        for c in corners:
            lo.append((c[0], c[1], min_alt))
            hi.append((c[0], c[1], max_alt))
        lo.extend(hi)
        return lo
    
    def extract_region_status_dicts(self):
        self.status_lookup_table = {}
        for i in range(self.last_t + 1):
            self.status_lookup_table[i] = {}
        for key in self.region_data.keys():
            ikey = int(key)
            state_list = self.region_data[key]
            for entry in state_list:
                start_t = entry['start_t']
                end_t = entry['end_t']
                status = entry['status']
                if end_t == -1:
                    end_t = self.last_t + 1
                if start_t == end_t:
                    self.status_lookup_table[start_t][ikey] = status
                for i in range(start_t, end_t):
                    self.status_lookup_table[i][ikey] = status

    def init_render_objs(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(projection='3d')
        self.ax.set(xlabel='Lat', ylabel='Lon', zlabel='Alt')

    def render(self, save_filename=None):
        self.init_render_objs()
        plt.show()
        if save_filename is not None:
            self.anim_plt.save(f'{save_filename}', writer='pillow')

    def render_timestep(self, timestep, save_filename=None):
        self.update_plot(timestep)
        if save_filename is not None:
            plt.savefig(save_filename)

    def render_animated(self):
        self.init_render_objs()
        self.anim_plt = animation.FuncAnimation(self.fig, self.update_plot, frames=self.last_t+1, interval=1000, blit=False)
        plt.show()

    def update_plot(self, frame_id):
        self.ax.clear()
        self.ax.set(xlabel='Lat', ylabel='Lon', zlabel='Alt')
        self.load_voxels_timestep(frame_id)
        self.ax.set_title(f'Timestep: {frame_id}')
    
    def calculate_voxels(self):
        self.voxel_components = [[] for i in range(self.last_t + 1)]
        for i in range(self.last_t + 1):
            self.calculate_voxels_timestep(i)

    def calculate_voxels_timestep(self, timestep):
        x, y, z = self.voxel_dims_by_tstep[timestep]
        xv, yv, zv = np.meshgrid(x, y, z)
        filled = np.ones((len(x) - 1, len(y) - 1, len(z) - 1), dtype=int)
        colors = np.zeros(filled.shape + (4,))
        x_len = len(x) - 1
        y_len = len(y) - 1
        z_len = len(z) - 1
        
        for i in range(x_len):
            for j in range(y_len):
                for k in range(z_len):
                    vol_id = self.match_volume_to_id(timestep, x[i], x[i+1], y[j], y[j+1], z[k], z[k+1])
                    # Handle case where no matching region is found
                    if vol_id is None:
                        color_val = [0.5, 0.5, 0.5, 0.3]  # Gray/transparent for unknown
                    else:
                        vol_status = self.status_lookup_table[timestep].get(vol_id, 'FREE')
                        if 'FREE' in vol_status:
                            color_val = [0, 0, 0, 0]
                        elif 'ALLOCATED' in vol_status:
                            color_val = [1, 0, 0, 1]
                        elif 'OCCUPIED' in vol_status:
                            color_val = [0, 1, 0, 1]
                        else:
                            color_val = [1, 1, 1, 1]
                    colors[i][j][k] = color_val
        self.voxel_components[timestep] = (xv, yv, zv, filled, colors)

    def match_volume_to_id(self, t, lat0, lat1, lon0, lon1, alt0, alt1):
        search_space = self.active_regions_by_tstep[t]
        c1 = (lat0, lon0, alt0)
        c2 = (lat1, lon1, alt1)
        
        # Try exact match first
        for id in search_space:
            cand_vol = self.region_volumes[id]
            if c1 in cand_vol and c2 in cand_vol:
                return id
        
        # If no exact match, find region that contains the voxel center
        center_lat = (lat0 + lat1) / 2
        center_lon = (lon0 + lon1) / 2
        center_alt = (alt0 + alt1) / 2
        
        for id in search_space:
            cand_vol = self.region_volumes[id]
            min_lat = min(c[0] for c in cand_vol)
            max_lat = max(c[0] for c in cand_vol)
            min_lon = min(c[1] for c in cand_vol)
            max_lon = max(c[1] for c in cand_vol)
            min_alt = min(c[2] for c in cand_vol)
            max_alt = max(c[2] for c in cand_vol)
            
            if (min_lat <= center_lat <= max_lat and
                min_lon <= center_lon <= max_lon and
                min_alt <= center_alt <= max_alt):
                return id
        
        return None

    def load_voxels_timestep(self, timestep):
        xv, yv, zv, filled, colors = self.voxel_components[timestep]
        self.ax.voxels(xv, yv, zv, filled, facecolors=colors, edgecolors='k')

if __name__ == "__main__":
    # Assumes regions json in first arg, txs in second arg
    if len(sys.argv) == 3:
        av = AirspaceVisualizer(sys.argv[1], sys.argv[2])
    else:
        av = AirspaceVisualizer("parsed_regions.json", "parsed_tx.json")
    av.render_timestep(0)
    av.render_animated()