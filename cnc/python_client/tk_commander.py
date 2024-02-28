# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import customtkinter
import tkinter
from tkinter import filedialog as fd, simpledialog, messagebox
from tkintermapview import TkinterMapView
from PIL import Image, ImageTk
from queue import Queue
import logging
from cnc_protocol import cnc_pb2
import subprocess
import redis
import numpy as np
import cv2
import time
import argparse
import os
from threading import Thread
from dotenv import dotenv_values
import zmq
import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

COMMANDER_ID = os.uname()[1]
WEBSOCKET_PORT = 9099
DEFAULT_SOURCE_NAME = 'telemetry'
SECRETS = None

class TKCommander(customtkinter.CTk):

    APP_NAME = "Command and Control Interface"
    WIDTH = 1800
    HEIGHT = 1000
    KEYLIST = ['w', 'a', 's', 'd', 'Left', 'Right', 'Up', 'Down', 't', 'l']
    MAG_STATE = ['Calibrated', 'Calibration Recommended', 'Calibration Required!', 'unused', 'Magnetic Perturbation!!']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = os.uname()[1]
        self._source_name = DEFAULT_SOURCE_NAME
        self.frames_processed = 0
        self.server = SECRETS["CLOUDLET"]
        self.user = SECRETS["SCP_USER"]

        self.r = redis.Redis(host=SECRETS["REDIS"], port=SECRETS["REDIS_PORT"], username=SECRETS["REDIS_USER"], password=SECRETS["REDIS_AUTH"],decode_responses=True)
        self.r2 = redis.Redis(host=SECRETS["REDIS"], port=SECRETS["REDIS_PORT"], username=SECRETS["REDIS_USER"], password=SECRETS["REDIS_AUTH"])
        self.r.ping()
        self.subscriber = self.r2.pubsub(ignore_subscribe_messages=True)
        self.subscriber.psubscribe('imagery.*')

        self.ctx = zmq.Context()
        self.zmq = self.ctx.socket(zmq.REQ)
        self.zmq.connect(f'tcp://{SECRETS["ZMQ"]}:{SECRETS["ZMQ_PORT"]}')

        self.title(TKCommander.APP_NAME)
        self.geometry(str(TKCommander.WIDTH) + "x" + str(TKCommander.HEIGHT))
        self.minsize(TKCommander.WIDTH, TKCommander.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", self.on_closing)
        self.bind("<Command-w>", self.on_closing)
        self.bind("<KeyPress>", self.update_keyboard_press)
        self.createcommand('tk::mac::Quit', self.on_closing)

        self.drone_dict = {}
        self.selected_drone_name = None
        self.connected_drone = None
        self.connected_marker = None
        self.connected_flightplan = None
        self.command_queue = Queue()
        self.manual = True

        self.keyboard_state = {k : 0 for k in TKCommander.KEYLIST}
        
        customtkinter.set_appearance_mode("system")
        customtkinter.set_default_color_theme("blue")

        # Configure spacing and frames of UI
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.frame_stream = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_stream.grid(row=0, column=1, rowspan=3, pady=5, padx=5, sticky="nsew")
        
        self.frame_sidebar = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_sidebar.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        self.frame_map = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_map.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Configure and add UI elements to available drones frame
        self.frame_stream.grid_columnconfigure(0, weight=1)
        self.frame_sidebar.grid_columnconfigure(0, weight=3)
        self.frame_sidebar.grid_columnconfigure(1, weight=1)

        self.frame_actions = customtkinter.CTkFrame(master=self.frame_sidebar, corner_radius=0)
        self.frame_actions.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.frame_actions.grid_columnconfigure(0, weight=1)

        self.frame_status = customtkinter.CTkFrame(master=self.frame_sidebar, corner_radius=0)
        self.frame_status.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.frame_status.grid_columnconfigure(0, weight=1)
       
        self.title = customtkinter.CTkLabel(master=self.frame_actions,
                                              text="Available Drones",
                                              font=("Roboto Medium", -24))  # font name and size in px
        self.title.grid(row=0, column=0, pady=10, padx=10, sticky="nsew")

        self.drone_dropdown = customtkinter.CTkComboBox(master=self.frame_actions,
                                                values=["No Selection"],
                                                command=self.on_selection_changed_event,
                                                height=40,
                                                font=("Roboto Medium", 14),
                                                dropdown_font=("Roboto Medium", 18),
                                                justify="center",
                                                hover=True)
        self.drone_dropdown.grid(row=1, column=0, pady=(10,5), padx=15, sticky="nsew")
        
        self.button_connect = customtkinter.CTkButton(master=self.frame_actions,
                                                   text="Connect",
                                                   height=40,
                                                   command=self.on_connect_pressed,
                                                   text_color="black",
                                                   font=("Roboto Medium", 13),
                                                   border_width=3,
                                                   border_color="black",
                                                   fg_color="#4F4642",
                                                   hover_color="#807873",)
        
        self.button_connect.grid(row=2, column=0, pady=(0,20), padx=15, sticky="nsew")
        self.button_connect.configure(state=tkinter.DISABLED)

        # Configure and add UI elements to control panel frame
        self.control_panel_text = customtkinter.CTkLabel(master=self.frame_stream,
                                              text="NO DRONE CONNECTED",
                                              font=("Roboto Medium", 32))  # font name and size in px
        self.control_panel_text.grid(row=0, column=0, pady=100, padx=10, sticky="nsew")

        image = Image.open("images/NoImage.jpg").resize((640,480))
        self.no_image = ImageTk.PhotoImage(image)
        #  https://www.flaticon.com/free-icons/helipad Helipad icons created by Freepik - Flaticon
        self.rth_icon = ImageTk.PhotoImage(Image.open("images/helipad.png").resize((48,48)))
        #  https://www.flaticon.com/free-icons/drone title="drone icons">Drone icons created by ultimatearm - Flaticon
        self.manual_icon = ImageTk.PhotoImage(Image.open("images/rc.png").resize((48,48)))
        #  https://www.flaticon.com/free-icons/map title="map icons">Map icons created by ultimatearm - Flaticon
        self.script_icon = ImageTk.PhotoImage(Image.open("images/maps.png").resize((48,48)))
        #  https://www.flaticon.com/free-icons/drone title="drone icons">Drone icons created by Freepik - Flaticon
        self.drone_icon = ImageTk.PhotoImage(Image.open( "images/uav.png").resize((35, 35)))


        self.image_label = tkinter.Label(master=self.frame_stream, image=self.no_image)
        self.image_label.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.image_label.grid(row=1, column=0, pady=5, padx=5)
        
        self.keyboard_help = customtkinter.CTkTextbox(master=self.frame_stream,
                                          font=("Roboto Medium", 24),
                                          fg_color='transparent')  # font name and size in px
        self.keyboard_help.grid(row=2, column=0, pady=10, padx=10, sticky="nsew")
        self.keyboard_help.insert("0.0", "---Manual Flight Controls---\nWASD: Pitch/Roll\nArrow Keys: Yaw/Altitude\nT: Takeoff\nL: Land")
        self.keyboard_help.configure(state="disabled")

        self.man = customtkinter.CTkLabel(master=self.frame_status,
                                          text="MANUAL CONTROL ACTIVE",
                                          font=("Roboto Bold", 13),
                                          text_color="black",
                                          fg_color="green")  # font name and size in px
        self.man.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")

        self.info = customtkinter.CTkTextbox(master=self.frame_status,
                                          font=("Roboto Medium", 12),
                                          fg_color="white",text_color="black")  # font name and size in px
        self.info.grid(row=2, column=0, pady=5, padx=10, sticky="nsew")
        self.info.insert("0.0", "Status: NONE")
        self.info.configure(state="disabled")

        self.button_fly = customtkinter.CTkButton(master=self.frame_actions,
                                                   text="Fly Mission",
                                                   width=150, 
                                                   height=65,
                                                   command=self.on_fly_mission_pressed,
                                                   text_color="black",
                                                   font=("Roboto Medium", 13),
                                                   border_width=3,
                                                   border_color="black",
                                                   image=self.script_icon)

        self.button_fly.grid(row=6, column=0, pady=5, padx=28, sticky="w")
        self.button_fly.configure(state=tkinter.DISABLED)
        
        self.button_rth = customtkinter.CTkButton(master=self.frame_actions,
                                                   text="Return Home", 
                                                   width=150,
                                                   height=65, 
                                                   fg_color="#f06d35",
                                                   hover_color="#c95a2a",
                                                   command=self.on_return_home_pressed,
                                                   text_color="black",
                                                   font=("Roboto Medium", 13),
                                                   border_width=3,
                                                   border_color="black",
                                                   image=self.rth_icon)

        self.button_rth.grid(row=7, column=0, pady=5, padx=28, sticky="e")
        self.button_rth.configure(state=tkinter.DISABLED)
        
        self.button_kill = customtkinter.CTkButton(master=self.frame_actions,
                                                   text="Manual Ctrl", 
                                                   width=150,
                                                   height=65, 
                                                   fg_color="#52e831",
                                                   hover_color="#49cf2b",
                                                   command=self.on_kill_mission_pressed,
                                                   text_color="black",
                                                   font=("Roboto Medium", 13),
                                                   border_width=3,
                                                   border_color="black",
                                                   image=self.manual_icon)

        self.button_kill.grid(row=6, column=0, pady=5, padx=28, sticky="e")
        self.button_kill.configure(state=tkinter.DISABLED)
        
        # Configure and add elements to map frame
        self.frame_map.grid_rowconfigure(1, weight=1)
        self.frame_map.grid_rowconfigure(0, weight=0)
        self.frame_map.grid_columnconfigure(0, weight=0)
        self.frame_map.grid_columnconfigure(1, weight=1)
        self.frame_map.grid_columnconfigure(2, weight=0)





# create markers
        self.map_widget = TkinterMapView(self.frame_map, corner_radius=0)
        self.map_widget.grid(row=0, rowspan=3, column=0, columnspan=3, sticky="nswe", padx=(5, 5), pady=(5, 5))

        self.map_option_menu = customtkinter.CTkOptionMenu(self.frame_map, values=["OpenStreetMap", "Google (Street)", "Google (Satellite)"],
                                                                       command=self.change_map)
        self.map_option_menu.set("Google (Satellite)")
        self.map_option_menu.grid(row=0, column=2, padx=(15, 15), pady=(20, 0))

        # Set up the map
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        self.map_widget.set_address("Mill 19")
        self.map_widget.set_zoom(19)
        self.last_map_update = time.time()
    
    # Events for handling changes to the available drone list

    def on_drone_list_changed_event(self, telemetry, event=None):
        self.drone_dict = self.retrieve_drones()
        if len(self.drone_dict) == 0:
            if self.drone_dropdown.get() != "No Selection":
                self.drone_dropdown.configure(values=["No Selection"])
                self.drone_dropdown.set("No Selection")
            self.on_disconnect_event()
        else:
            self.connected_drone = telemetry
            self.drone_dropdown.configure(values=self.drone_dict)
            self.on_update_event()

    def on_selection_changed_event(self, event=None):
        if len(self.drone_dict) > 0:
            if self.drone_dropdown.get() != self.selected_drone_name:
                self.toggle_connect_button(True)
                self.selected_drone_name = self.drone_dropdown.get()
        else:
            self.toggle_connect_button(False)
        

    def toggle_connect_button(self, on):
        if on:
            self.button_connect.configure(state=tkinter.NORMAL)
        else:
            self.button_connect.configure(state=tkinter.DISABLED)

    def on_connect_pressed(self, event=None):
        lat = float(self.connected_drone["latitude"])
        long = float(self.connected_drone["longitude"])
        self.connected_marker = self.map_widget.set_marker( lat if lat >= 500 else 0,
                long if long >= 500 else 0,
                text=self.selected_drone_name,
                text_color="#00efff",
                font=("Roboto Medium", 13),
                marker_color_circle="#065b8c",
                marker_color_outside="#00efff",
                icon=self.drone_icon)
        self.on_connect_event()
        self.toggle_connect_button(False)
        self.toggle_manual(True)


    # Events for handling the control panel

    def on_disconnect_event(self):
        self.connected_drone = None
        self.button_kill.configure(state=tkinter.DISABLED)
        self.button_fly.configure(state=tkinter.DISABLED)
        self.control_panel_text.configure(text="NO DRONE CONNECTED")
        self.info.configure(state=tkinter.NORMAL)
        self.info.delete("0.0", "end")
        self.info.insert("0.0", "Status: NONE")
        self.info.configure(state=tkinter.DISABLED)
        self.image_label.configure(image=self.no_image)
        if self.connected_marker != None:
            self.connected_marker.delete()
            self.connected_marker = None

    def on_connect_event(self):
        self.button_kill.configure(state=tkinter.NORMAL)
        self.button_fly.configure(state=tkinter.NORMAL)
        self.button_rth.configure(state=tkinter.NORMAL)
        self.control_panel_text.configure(text="{0} Connected".format(self.selected_drone_name))
        self.on_update_event()

    def on_update_event(self, event=None):
        if self.connected_marker is not None:
            self.connected_marker.set_position(float(self.connected_drone["latitude"]), float(self.connected_drone["longitude"]))
            if(time.time() - self.last_map_update > 1):
                self.last_map_update = time.time()
                self.map_widget.set_position(float(self.connected_drone["latitude"]), float(self.connected_drone["longitude"]))
                #Image.rotate is counter-clockwise, so negate the bearing
                self.drone_icon = ImageTk.PhotoImage(Image.open( "images/uav.png").resize((35, 35)).rotate(-int(self.connected_drone["bearing"])))
                self.connected_marker.change_icon(self.drone_icon)

            self.info.configure(state=tkinter.NORMAL)
            self.info.delete("0.0", "end")
            self.info.insert("0.0", "Last Update: {6}\nLocation: ({0}, {1})\nAltitude: {2}m\nRSSI: {3}\nMag: {4}\nBattery: {5}%".format(round(float(self.connected_drone["latitude"]), 5),
                    round(float(self.connected_drone["longitude"]), 5), round(float(self.connected_drone["altitude"]), 2), self.connected_drone["rssi"],
                    self.MAG_STATE[int(self.connected_drone["mag"])], self.connected_drone["battery"], self.connected_drone["last_update"]))
            self.info.configure(state=tkinter.DISABLED)


    def on_frame_update_event(self, byteframe, event=None):
        try:
            np_data = np.frombuffer(byteframe, dtype=np.uint8)
            img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img).resize((640,480))
            self.image = ImageTk.PhotoImage(img)
            self.image_label.configure(image=self.image)
        except Exception as e:
            logger.error(e)

    def on_fly_mission_pressed(self, event=None):
        filetypes = (
            ('Mission files', '*.ms'),
        )

        filepath = fd.askopenfilename(
            title='Open a file',
            initialdir='../../hermes/',
            filetypes=filetypes)
        filename = filepath.split('/')[-1]
        if filename:
            logger.info("Selected file: " + filename)
            # TODO: Make SCP destination configurable
            answer = messagebox.askokcancel("Warning","By clicking OK, the drone will start flying your mission. Please ensure that the drone is safely away" +
                    " from people and that the PIC is ready to takeover in case of failure.")
            if answer:
                self.button_fly.configure(state=tkinter.DISABLED)
                self.button_kill.configure(state=tkinter.NORMAL)
                self.button_rth.configure(state=tkinter.NORMAL)
                self.toggle_manual(False)
                SCP_URL = f"{self.user}@{self.server}:~/steeleagle/cnc/server/steeleagle-vol/scripts/" + filename
                FLIGHT_URL = f"http://{self.server}:8080/scripts/" + filename
                try:
                    subprocess.run(["scp", filepath, SCP_URL], check=True)
                    logger.info("Sent file {0} to the cloudlet".format(filename))
                    req = cnc_pb2.Extras()
                    req.cmd.script_url = FLIGHT_URL
                    req.commander_id = COMMANDER_ID
                    req.cmd.for_drone_id = self.selected_drone_name
                    self.command_queue.put_nowait(req)
                    messagebox.showinfo("Upload Complete","Flight script uploaded to server.")
                except subprocess.CalledProcessError as cpe:
                    logger.error(cpe)

    def on_kill_mission_pressed(self, event=None):
        self.button_fly.configure(state=tkinter.NORMAL)
        self.button_kill.configure(state=tkinter.DISABLED)
        self.button_rth.configure(state=tkinter.NORMAL)
        req = cnc_pb2.Extras()
        req.cmd.halt = True
        req.commander_id = COMMANDER_ID
        req.cmd.for_drone_id = self.selected_drone_name
        self.command_queue.put_nowait(req)
        self.toggle_manual(True)

    def on_return_home_pressed(self, event=None):
        self.button_fly.configure(state=tkinter.DISABLED)
        self.button_kill.configure(state=tkinter.NORMAL)
        self.button_rth.configure(state=tkinter.DISABLED)
        self.toggle_manual(False)

        req = cnc_pb2.Extras()
        req.cmd.rth = True
        req.cmd.manual = False
        req.commander_id = COMMANDER_ID
        req.cmd.for_drone_id = self.selected_drone_name
        self.command_queue.put_nowait(req)
        self.man.configure(text="RETURNING HOME - CONNECTION LOST", text_color="black", fg_color="red")

    # Events for handling the search bar

    def on_search_pressed(self, event=None):
        self.map_widget.set_address(self.entry.get())

    # Keyboard

    def update_keyboard_press(self, event):
        keypress = event.keysym
        print("Key pressed: " + keypress)
        if keypress not in self.keyboard_state.keys():
            return
        else:
            self.keyboard_state[keypress] = time.time() * 1000

    def active(self, char):
        return time.time() * 1000 - self.keyboard_state[char] < 50

    def axis(self, left, right):
        return 25 * (int(self.active(left)) - int(self.active(right)))

    def image_subscriber(self,):
        while True:
            message = self.subscriber.get_message( timeout=0.1)
            if message:
                # {message['channel'].split(b'.')[-1]}") 
                # b'imagery.<drone>'
                self.frames_processed += 1
                if self.selected_drone_name != None and bytes(self.selected_drone_name, encoding='utf-8') == message['channel'].split(b'.')[-1]:
                    self.image_label.after(1, self.on_frame_update_event(message['data']))

    def retrieve_drones(self):
        l=[]
        for k in self.r.keys("telemetry.*"):
            l.append(k.split(".")[-1])
        return l

    def update_telemetry(self,):
        telemetry = {}
        while True:
            if self.selected_drone_name is not None:
                results = self.r.xrevrange(f"telemetry.{self.selected_drone_name}", "+", "-", 1)
                telemetry = results[0][1]
                telemetry["last_update"] = datetime.datetime.strftime(datetime.datetime.fromtimestamp(int(results[0][0].split("-")[0])/1000), "%d-%b-%Y %H:%M:%S")
            self.on_drone_list_changed_event(telemetry)
            time.sleep(0.1)

    def command_handler(self):
        while True:
            try:
                req = self.command_queue.get_nowait()
            except:
                req = None
                if self.selected_drone_name != None:
                    if self.manual:
                        req = cnc_pb2.Extras()
                        req.commander_id = COMMANDER_ID
                        req.cmd.for_drone_id = self.selected_drone_name
                        req.cmd.manual = True
                        if self.active('t'):
                            logger.debug("Takeoff triggered")
                            req.cmd.takeoff = True
                        elif self.active('l'):
                            logger.debug("Landing triggered")
                            req.cmd.land = True
                        else:
                            req.cmd.pcmd.yaw = self.axis('Right', 'Left')
                            req.cmd.pcmd.pitch = self.axis('w', 's')
                            req.cmd.pcmd.roll = self.axis('d', 'a')
                            req.cmd.pcmd.gaz = self.axis('Up', 'Down')
                            req.cmd.pcmd.gimbal_pitch = self.axis('r', 'f')
                            logger.debug(f"PCMD: {req.cmd.pcmd.yaw}, {req.cmd.pcmd.pitch}, {req.cmd.pcmd.roll}, {req.cmd.pcmd.gaz} {req.cmd.pcmd.gimbal_pitch}")
            if req is not None:
                self.zmq.send(req.SerializeToString())
                rep = self.zmq.recv()
                logger.debug(f"Received {rep} for the following request: {req}")
            time.sleep(0.1)

    # Cleanup and start events

    def toggle_manual(self, val):
        self.manual = val
        if self.manual:
            self.man.configure(text="MANUAL CONTROL ACTIVE", text_color="black", fg_color="green")
            self.button_kill.configure(state=tkinter.DISABLED)
        else:
            self.man.configure(text="AUTONOMOUS CONTROL ACTIVE", text_color="black", fg_color="orange")
            self.button_kill.configure(state=tkinter.NORMAL)
    
    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.mainloop()

    def change_map(self, new_map: str):
        if new_map == "OpenStreetMap":
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        elif new_map == "Google (Street)":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif new_map == "Google (Satellite)":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--loglevel', default='INFO', help='Set the log level')
    parser.add_argument('-e', '--env', default='.env', help='.env file to load [default: .env]')
    
    args = parser.parse_args()
    SECRETS = dotenv_values(args.env)
    logging.basicConfig(format="%(levelname)s: %(message)s", level=args.loglevel)
    UI = TKCommander() # Must initialize the UI in the thread in which it will run
    subscriber = Thread(target=UI.image_subscriber, daemon=True)
    telem = Thread(target=UI.update_telemetry, daemon=True)
    cmd_handler = Thread(target=UI.command_handler, daemon=True)
    subscriber.start()
    telem.start()
    cmd_handler.start()
    UI.start()