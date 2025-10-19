from airspace_region import RegionStatus
import airspace_region
from datetime import datetime, timezone
from enum import Enum
import json
import re
import sys

TIME_IDX = 0
CALLER_IDX = 1
LOGLEVEL_IDX = 2
METHOD_IDX = 3
DATA_IDX = 4

class TransactionType(Enum):
    DESTROY = 0
    CREATE = 1
    SPLIT_LAT = 2
    SPLIT_LON = 3
    SPLIT_ALT = 4
    JOIN_LAT = 5
    JOIN_LON = 6
    JOIN_ALT = 7
    STATUS_CHANGE = 8
    OWNER_CHANGE = 9
    OCCUPANT_CHANGE = 10

class RegionState():
    def __init__(self, start_t, min_alt, max_alt, corners, status, owner, occupant):
        self.start_t = start_t
        self.end_t = -1
        self.min_alt = min_alt
        self.max_alt = max_alt
        self.corners = corners
        self.status = status
        self.owner = owner
        self.occupant = occupant

    def is_current_state(self):
        return self.end_t == -1

    def set_end_t(self, end_t):
        self.end_t = end_t

class RegionStateEncoder(json.JSONEncoder):
    def default(self, obj):
        if (type(obj) == RegionState):
            return {
                "start_t": obj.start_t,
                "end_t": obj.end_t,
                "min_alt": obj.min_alt,
                "max_alt": obj.max_alt,
                "corners": obj.corners,
                "status": obj.status,
                "owner": obj.owner,
                "occupant": obj.occupant
            }
        else:
            return obj.name

class AirspaceTransaction():
    def __init__(self, target_cid, transaction_type):
        self.cid = target_cid
        self.tx_type = transaction_type

class AirspaceTransactionEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) == AirspaceTransaction:
            return {
                "cid": obj.cid,
                "tx_type": obj.tx_type.name
            }

class PlaybackEngine():
    def __init__(self):
        self.actions_by_tstep = [] # list of transactions tied to t=x
        self.regions = {} # cid -> list[RegionState]

    def read_file_to_mem(self, filename):
        with open(filename, 'r') as f:
            print(f"Opened {filename} for parsing...")
            self.raw_data = []
            lines = f.readlines()
            for line in lines:
                split_line = line.strip().split('|')
                cleaned_line = []
                for entry in split_line:
                    cleaned_line.append(entry.strip())
                self.raw_data.append(cleaned_line)
            print(f"Read {len(self.raw_data)} lines from log file into memory for parsing...")

    def parse_log_file(self):
        i = 0
        data_len = len(self.raw_data)
        while i < data_len:
            curr_line = self.raw_data[i]
            match = re.search(r'create_airspace', curr_line[METHOD_IDX])
            if match is not None:
                self.extract_starttime(curr_line)
                self.extract_endtime(self.raw_data[-1])
                self.prepopulate_tx_list()
                self.extract_grid_minmax_alt(curr_line)
                self.extract_airspace_corners(curr_line)
                break
            i += 1
        while i < data_len:
            self.parse_line(self.raw_data[i])
            i += 1
        self.export_regions_json()
        self.export_transactions_json()
        
    
    def export_regions_json(self):
        fname = "parsed_regions.json"
        try:
            with open(fname, 'w') as jf:
                json.dump(self.regions, jf, indent=4, ensure_ascii=False, cls=RegionStateEncoder)
            print(f"Exported regions structure to json file {fname}...")
        except:
            print(f"Error exporting regions structure to json file {fname}...")

    def export_transactions_json(self):
        fname = "parsed_tx.json"
        try:
            indexed_tx = []
            for index, value in enumerate(self.actions_by_tstep):
                indexed_tx.append({"t_step": index, "transactions": value})
            with open(fname, 'w') as jf:
                json.dump(indexed_tx, jf, indent=4, ensure_ascii=False, cls=AirspaceTransactionEncoder)
            print(f"Exported transactions record to json file {fname}...")
        except:
            print(f"Error exposting transactions record to json file {fname}...")

    def prepopulate_tx_list(self):
        slots = (self.end_time - self.start_time) / 1000
        for i in range(int(slots + 1)):
            self.actions_by_tstep.append([])

    def extract_starttime(self, line):
        self.start_time = convert_dtg_to_epoch(line[TIME_IDX])

    def extract_endtime(self, line):
        self.end_time = convert_dtg_to_epoch(line[TIME_IDX])

    def extract_epoch_time(self, line_seg):
        return convert_dtg_to_epoch(line_seg)

    def extract_grid_minmax_alt(self, line):
        ''' Assumes only non-negative values for altitude '''
        split_line = line[DATA_IDX].split(", ")
        alt_seg = find_segment(r'altitude', split_line)
        if alt_seg is not None:
            self.min_alt, self.max_alt = parse_minmax_alt(alt_seg)
        else:
            print("Failed to extract min and max alt values from origin line...")
            return
    
    def extract_airspace_corners(self, line):
        data_line = line[DATA_IDX]
        if find_segment(r'corners', data_line) is None:
            print(data_line)
            print("Failed to extract corners from origin line...")
            return
        self.corners = parse_coordinate_sequence(data_line)

    def parse_line(self, line):
        t_stamp = self.produce_relative_timestamp(line[TIME_IDX])
        method = line[METHOD_IDX]
        if find_segment(r'init', method):
            if find_segment(r'geohash precision', line[DATA_IDX]):
                return
            self.extract_region_creation(t_stamp, line[DATA_IDX])
        elif find_segment(r'split_by', method):
            if find_segment(r'lat', method):
                self.extract_region_split(t_stamp, line[DATA_IDX], TransactionType.SPLIT_LAT)
            elif find_segment(r'lon', method):
                self.extract_region_split(t_stamp, line[DATA_IDX], TransactionType.SPLIT_LON)
            else:
                self.extract_region_split(t_stamp, line[DATA_IDX], TransactionType.SPLIT_ALT)
        elif find_segment(r'update', method):
            if find_segment(r'owner', method):
                self.extract_owner_update(t_stamp, line[DATA_IDX])
            elif find_segment(r'status', method):
                self.extract_status_update(t_stamp, line[DATA_IDX])
        elif find_segment(r'occupant', method):
            if find_segment(r'UNAUTH', line[DATA_IDX]):
                return
            elif find_segment(r'add', method):
                self.extract_occupant_update(t_stamp, line[DATA_IDX], True)
            else:
                self.extract_occupant_update(t_stamp, line[DATA_IDX], False)

    def produce_relative_timestamp(self, time_seg):
        e_time = self.extract_epoch_time(time_seg)
        return int((e_time - self.start_time) / 1000)
    
    def extract_region_creation(self, rel_timestamp, data_seg):
        cid_split = data_seg.split(" >> ")
        cid = regex_format_int_unsigned(cid_split[0])
        range_seg, corner_seg = cid_split[1].split("corners: ")
        alt_seg = range_seg.split("alt=")[1]
        min_alt, max_alt = parse_minmax_alt(alt_seg)
        corners = parse_coordinate_sequence(corner_seg)
        r_state = RegionState(rel_timestamp, min_alt, max_alt, corners,
                              airspace_region.RegionStatus.FREE, -1, -1)
        self.regions[cid] = [r_state]
        self.actions_by_tstep[rel_timestamp].append(
            AirspaceTransaction(cid, TransactionType.CREATE))
        

    def extract_region_split(self, rel_timestamp, data_seg, split_type):
        cid_split = data_seg.split(" >> ")
        cid = regex_format_int_unsigned(cid_split[0])
        self.regions[cid][-1].set_end_t(rel_timestamp)
        self.actions_by_tstep[rel_timestamp].append(
            AirspaceTransaction(cid, split_type)
        )

    def extract_owner_update(self, rel_timestamp, data_seg):
        split_line = data_seg.split(" >> ")
        cid = regex_format_int_unsigned(split_line[0])
        drone_seg = split_line[1].split("->")[1].split("(")[0]
        drone_id = regex_format_int_unsigned(drone_seg)
        self.regions[cid][-1].set_end_t(rel_timestamp)
        prev_state = self.regions[cid][-1]
        if drone_id >= 0:
            self.regions[cid].append(RegionState(rel_timestamp, prev_state.min_alt,
                prev_state.max_alt, prev_state.corners, prev_state.status, drone_id, prev_state.occupant))
        else:
            self.regions[cid].append(RegionState(rel_timestamp, prev_state.min_alt,
                prev_state.max_alt, prev_state.corners, prev_state.status, -1, prev_state.occupant))
        self.actions_by_tstep[rel_timestamp].append(AirspaceTransaction(cid, TransactionType.OWNER_CHANGE))

    def extract_status_update(self, rel_timestamp, data_seg):
        split_line = data_seg.split(" >> ")
        cid = regex_format_int_unsigned(split_line[0])
        status_seg = split_line[1].split("->")[1]
        status = None
        if find_segment('FREE', status_seg):
            status = RegionStatus.FREE
        elif find_segment('RESTRICTED', status_seg):
            if find_segment('ALLOCATED', status_seg):
                status = RegionStatus.RESTRICTED_ALLOCATED
            elif find_segment('AVAILABLE', status_seg):
                status = RegionStatus.RESTRICTED_AVAILABLE
            else:
                status = RegionStatus.RESTRICTED_OCCUPIED
        elif find_segment('ALLOCATED', status_seg):
            status = RegionStatus.ALLOCATED
        elif find_segment('OCCUPIED', status_seg):
            status = RegionStatus.OCCUPIED
        else:
            status = RegionStatus.NOFLY
        
        self.regions[cid][-1].set_end_t(rel_timestamp)
        prev_state = self.regions[cid][-1]
        self.regions[cid].append(RegionState(rel_timestamp, prev_state.min_alt,
            prev_state.max_alt, prev_state.corners, status, prev_state.owner,
            prev_state.occupant))
        self.actions_by_tstep[rel_timestamp].append(AirspaceTransaction(cid, TransactionType.STATUS_CHANGE))
        
    def extract_occupant_update(self, rel_timestamp, data_seg, add_flag):
        split_line = data_seg.split(" /\\ ")
        drone_id = regex_format_int_unsigned(split_line[0])
        cid_seg = split_line[1].split("]")[1]
        cid = regex_format_int_unsigned(cid_seg)

        self.regions[cid][-1].set_end_t(rel_timestamp)
        prev_state = self.regions[cid][-1]
        if (add_flag):
            self.regions[cid].append(RegionState(rel_timestamp, prev_state.min_alt,
                prev_state.max_alt, prev_state.corners, prev_state.status, prev_state.owner,
                drone_id))
        else:
            self.regions[cid].append(RegionState(rel_timestamp, prev_state.min_alt,
            prev_state.max_alt, prev_state.corners, prev_state.status, prev_state.owner,
            -1))
        
        self.actions_by_tstep[rel_timestamp].append(AirspaceTransaction(cid, TransactionType.OCCUPANT_CHANGE))


def find_segment(keyword, line_items):
    if type(line_items) == str:
        match = re.search(rf'{keyword}', line_items)
        if match is not None:
            return line_items
        else:
            return None
    for item in line_items:
        match = re.search(rf'{keyword}', item)
        if match is not None:
            return item

def regex_format_float_unsigned(target_string):
    return float(re.sub(r'[^0-9.]', '', target_string))

def regex_format_float_signed(target_string):
    return float(re.sub(r'[^0-9.-]', '', target_string))

def regex_format_int_unsigned(target_string):
    val = re.sub(r'[^0-9]', '', target_string)
    if len(val) == 0:
        return -1
    return int(val)

def regex_format_int_signed(target_string):
    val = re.sub(r'[^0-9-]', '', target_string)
    if len(val) == 0:
        return -1
    return int(val)

def parse_2d_coordinate(target_string):
    components = target_string.split(",")
    lat = regex_format_float_signed(components[0])
    lon = regex_format_float_signed(components[1])
    return (lat, lon)

def parse_3d_coordinate(target_string):
    components = target_string.split(",")
    lat = regex_format_float_signed(components[0])
    lon = regex_format_float_signed(components[1])
    alt = regex_format_float_signed(components[2])
    return (lat, lon, alt)

def parse_coordinate_sequence(target_string):
    coords = re.findall(r'\(([^()]*)\)', target_string)
    coord_list = []
    if (len(coords[0].split(",")) == 2):
        for item in coords:
            coord_list.append(parse_2d_coordinate(item))
    else:
        for item in coords:
            coord_list.append(parse_3d_coordinate(item))
    return coord_list

def parse_minmax_alt(alt_seg):
    raw_vals = alt_seg.split("<->")
    min_alt = regex_format_float_unsigned(raw_vals[0])
    max_alt = regex_format_float_unsigned(raw_vals[1])
    return (min_alt, max_alt)

def convert_dtg_to_epoch(dtg_string):
    dtg_format = "%Y-%m-%d %H:%M:%S"
    dt_obj = datetime.strptime(dtg_string, dtg_format)
    epoch_time = dt_obj.timestamp()
    return epoch_time

def convert_epoch_to_dtg(epoch_value):
    return datetime.fromtimestamp(epoch_value, tz=timezone.utc)

if __name__ == "__main__":
    pe = PlaybackEngine()
    if len(sys.argv) > 1:
        pe.read_file_to_mem(sys.argv[1])
    else:
        pe.read_file_to_mem('airspace_logs/airspace_control.log')
    pe.parse_log_file()