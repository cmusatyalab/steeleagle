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
import asyncio
import subprocess
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper
import json
import io
import numpy as np
import cv2
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class GUICommanderAdapter(customtkinter.CTk):

    APP_NAME = "Command and Control Interface"
    WIDTH = 1800
    HEIGHT = 1000
    KEYLIST = ['w', 'a', 's', 'd', 'Left', 'Right', 'Up', 'Down', 't', 'l']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.title(GUICommanderAdapter.APP_NAME)
        self.geometry(str(GUICommanderAdapter.WIDTH) + "x" + str(GUICommanderAdapter.HEIGHT))
        self.minsize(GUICommanderAdapter.WIDTH, GUICommanderAdapter.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", self.on_closing)
        self.bind("<Command-w>", self.on_closing)
        self.bind("<KeyPress>", self.update_keyboard_press)
        self.createcommand('tk::mac::Quit', self.on_closing)

        self.drone_dict = {}
        self.connected_drone = None
        self.connected_marker = None
        self.connected_flightplan = None
        self.command_queue = Queue()
        self.manual = True

        self.keyboard_state = {k : 0 for k in GUICommanderAdapter.KEYLIST}
        
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
                                                dropdown_font=("Roboto Medium", 18))
        self.drone_dropdown.grid(row=1, column=0, pady=(10,5), padx=15, sticky="nsew")
        
        self.button_connect = customtkinter.CTkButton(master=self.frame_actions,
                                                   text="Connect",
                                                   height=40,
                                                   command=self.on_connect_pressed,
                                                   font=("Roboto Medium", 13),
                                                   border_width=3,
                                                   border_color="black")
        
        self.button_connect.grid(row=2, column=0, pady=(0,20), padx=15, sticky="nsew")
        self.button_connect.configure(state=tkinter.DISABLED)

        # Configure and add UI elements to control panel frame
        self.control_panel_text = customtkinter.CTkLabel(master=self.frame_stream,
                                              text="NO DRONE CONNECTED",
                                              font=("Roboto Medium", 32))  # font name and size in px
        self.control_panel_text.grid(row=0, column=0, pady=100, padx=10, sticky="nsew")

        image = Image.open("images/NoImage.jpg").resize((640,480))
        self.no_image = ImageTk.PhotoImage(image)

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
                                          font=("Roboto Medium", 18),
                                          fg_color="white")  # font name and size in px
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
                                                   border_color="black")

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
                                                   border_color="black")

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
                                                   border_color="black")

        self.button_kill.grid(row=6, column=0, pady=5, padx=28, sticky="e")
        self.button_kill.configure(state=tkinter.DISABLED)
        
        # Configure and add elements to map frame
        self.frame_map.grid_rowconfigure(1, weight=1)
        self.frame_map.grid_rowconfigure(0, weight=0)
        self.frame_map.grid_columnconfigure(0, weight=0)
        self.frame_map.grid_columnconfigure(1, weight=1)
        self.frame_map.grid_columnconfigure(2, weight=0)


        self.drone_icon = ImageTk.PhotoImage(Image.open( "images/plane_circle_2.png").resize((35, 35)))



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

    def update_drone_dict(self, new_list):
        self.drone_dict = {}
        for item in new_list:
            self.drone_dict[item["name"]] = item
        if self.connected_drone is not None and self.connected_drone["name"] in self.drone_dict.keys():
            self.connected_drone = self.drone_dict[self.connected_drone["name"]]
            self.on_update_event()

    def on_drone_list_changed_event(self, new_list, event=None):
        self.update_drone_dict(new_list)
        if len(self.drone_dict.keys()) == 0:
            if self.drone_dropdown.get() != "No Selection":
                self.drone_dropdown.configure(values=["No Selection"])
                self.drone_dropdown.set("No Selection")
            self.on_disconnect_event()
        else:
            new_values = [d["name"] for d in new_list]
            self.drone_dropdown.configure(values=new_values)

    def on_selection_changed_event(self, event=None):
        if self.connected_drone != None and self.connected_drone["name"] == self.drone_dropdown.get():
            self.toggle_connect_button(False)
        elif len(self.drone_dict.keys()) > 0:
            self.toggle_connect_button(True)
        else:
            self.toggle_connect_button(False)

    def toggle_connect_button(self, on):
        if on:
            self.button_connect.configure(state=tkinter.NORMAL)
        else:
            self.button_connect.configure(state=tkinter.DISABLED)

    def on_connect_pressed(self, event=None):
        self.connected_drone = self.drone_dict[self.drone_dropdown.get()]
        self.connected_marker = self.map_widget.set_marker(self.connected_drone["latitude"],
                self.connected_drone["longitude"],
                text=self.connected_drone["name"],
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
        self.control_panel_text.configure(text="{0} Connected".format(self.connected_drone["name"]))
        self.on_update_event()

    def on_update_event(self, event=None):
        self.connected_marker.set_position(self.connected_drone["latitude"], self.connected_drone["longitude"])
        if(time.time() - self.last_map_update > 1):
            self.last_map_update = time.time()
            self.map_widget.set_position(self.connected_drone["latitude"], self.connected_drone["longitude"])
            #Image.rotate is counter-clockwise, so negate the bearing
            self.drone_icon = ImageTk.PhotoImage(Image.open( "images/plane_circle_2.png").resize((35, 35)).rotate(-self.connected_drone["bearing"]))
            self.connected_marker.change_icon(self.drone_icon)

        self.info.configure(state=tkinter.NORMAL)
        self.info.delete("0.0", "end")
        self.info.insert("0.0", "Location: ({0}, {1})\nAltitude: {2}m\nRSSI: {3}\nMag: {4}\nBattery: {5}%".format(round(self.connected_drone["latitude"], 5),
                round(self.connected_drone["longitude"], 5), round(self.connected_drone["altitude"], 2), self.connected_drone["rssi"],
                self.connected_drone["mag"], self.connected_drone["battery"]))
        self.info.configure(state=tkinter.DISABLED)


    def on_frame_update_event(self, byteframe, event=None):
        try:
            np_data = np.fromstring(byteframe, dtype=np.uint8)
            img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            self.image = ImageTk.PhotoImage(img)
            self.image_label.configure(image=self.image)
        except Exception as e:
            logger.error(e)

    def on_fly_mission_pressed(self, event=None):
        filetypes = (
            ('Dex files', '*.dex'),
        )

        filename = fd.askopenfilename(
            title='Open a file',
            initialdir='../../hermes/src/',
            filetypes=filetypes)

        logger.info("Selected file: " + filename)
        # TODO: Make SCP destination configurable
        answer = messagebox.askokcancel("Warning","By clicking OK, the drone will start flying your mission. Please ensure that the drone is safely away" +
                " from people and that the PIC is ready to takeover in case of failure.")
        if answer:
            self.toggle_manual(False)
            SCP_URL = "teiszler@128.2.212.60:/var/www/html/scripts/" + "mission.dex"
            FLIGHT_URL = "http://128.2.212.60/scripts/" + "mission.dex" 
            subprocess.run(["scp", filename, SCP_URL])
            logger.info("Sent file {0} to the cloudlet".format(filename))
            messagebox.showinfo("Upload Complete","Flight script uploaded to server.")
            command = {"drone": self.connected_drone["name"], "type": "start", "url": FLIGHT_URL}
            self.command_queue.put_nowait(command)
        

    def on_kill_mission_pressed(self, event=None):
        command = {"drone": self.connected_drone["name"], "type": "kill"}
        self.command_queue.put_nowait(command)
        self.toggle_manual(True)

    def on_return_home_pressed(self, event=None):
        self.button_fly.configure(state=tkinter.DISABLED)
        self.button_kill.configure(state=tkinter.DISABLED)
        self.button_rth.configure(state=tkinter.DISABLED)
        self.toggle_manual(False)
        self.man.configure(text="RETURNING HOME - CONNECTION LOST", text_color="black", fg_color="red")
        command = {"drone": self.connected_drone["name"], "type": "rth"}
        self.command_queue.put_nowait(command)

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
            print(f"RATE: {time.time() * 1000 - self.keyboard_state[keypress]}")
            self.keyboard_state[keypress] = time.time() * 1000

    def active(self, char):
        return time.time() * 1000 - self.keyboard_state[char] < 50

    def axis(self, left, right):
        return 25 * (int(self.active(left)) - int(self.active(right)))

    # Gabriel

    def set_up_adapter(self, preprocess, source_name, id, server):
        self.id = id
        self._preprocess = preprocess
        self._source_name = source_name
        self.frames_processed = 0
        self.server = server

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(0.3)
            try:
                command = self.command_queue.get_nowait()
            except:
                command = None

            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append(bytes('Message to CNC', 'utf-8'))

            extras = cnc_pb2.Extras()
            extras.commander_id = self.id
            if command != None:
                extras.cmd.for_drone_id = command["drone"]
                if command["type"] == "kill":
                    extras.cmd.halt = True
                elif command["type"] == "start":
                    extras.cmd.manual = False
                    extras.cmd.script_url = command["url"]
                elif command["type"] == "rth":
                    extras.cmd.manual = False
                    extras.cmd.rth = True
            elif self.connected_drone != None:
                extras.cmd.for_drone_id = self.connected_drone["name"]

            if self.manual and self.connected_drone != None:
                extras.cmd.manual = True
                if self.active('t'):
                    print("Takeoff triggered")
                    extras.cmd.takeoff = True
                elif self.active('l'):
                    print("Landing triggered")
                    extras.cmd.land = True
                else:
                    extras.cmd.pcmd.yaw = self.axis('Right', 'Left')
                    extras.cmd.pcmd.pitch = self.axis('w', 's')
                    extras.cmd.pcmd.roll = self.axis('d', 'a')
                    extras.cmd.pcmd.gaz = self.axis('Up', 'Down')
                    print(f"PCMD: {extras.cmd.pcmd.yaw}, {extras.cmd.pcmd.pitch}, {extras.cmd.pcmd.roll}, {extras.cmd.pcmd.gaz}")

            input_frame.extras.Pack(extras)
            return input_frame

        return [
            ProducerWrapper(producer=producer, source_name=self._source_name)
        ]
           
    def consumer(self, result_wrapper):
        if len(result_wrapper.results) < 1 or len(result_wrapper.results) > 2:
            logger.error('Got %d results from server'.
                    len(result_wrapper.results))
            return
        
        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                self.frames_processed += 1
                payload = result.payload.decode('utf-8')
                try:
                    data = json.loads(payload)
                    self.on_drone_list_changed_event(data)
                except Exception as e:
                    pass
            elif result.payload_type == gabriel_pb2.PayloadType.IMAGE:
                self.frames_processed += 1
                if self.connected_drone != None:
                    self.image_label.after(1, self.on_frame_update_event(result.payload))
            else:
                logger.error("Got result type " + result.payload_type)

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