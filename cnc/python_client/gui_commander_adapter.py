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
from keyboard_controller import KeyboardCtrl


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class GUICommanderAdapter(customtkinter.CTk):

    APP_NAME = "Command and Control Interface"
    WIDTH = 1800
    HEIGHT = 1000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(GUICommanderAdapter.APP_NAME)
        self.geometry(str(GUICommanderAdapter.WIDTH) + "x" + str(GUICommanderAdapter.HEIGHT))
        self.minsize(GUICommanderAdapter.WIDTH, GUICommanderAdapter.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", self.on_closing)
        self.bind("<Command-w>", self.on_closing)
        self.createcommand('tk::mac::Quit', self.on_closing)

        self.control = KeyboardCtrl()

        self.drone_dict = {}
        self.connected_drone = None
        self.connected_marker = None
        self.connected_flightplan = None
        self.command_queue = Queue()
        self.manual = True
        
        customtkinter.set_appearance_mode("system")
        customtkinter.set_default_color_theme("blue")

        # Configure spacing and frames of UI
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=20)
        self.grid_rowconfigure(0, weight=1)

        self.frame_left_top = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_left_top.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.frame_left_bot = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_left_bot.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        self.frame_right = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_right.grid(row=0, column=1, rowspan=3, pady=5, padx=5, sticky="nsew")

        # Configure and add UI elements to available drones frame
        self.frame_left_top.grid_columnconfigure(0, weight=1)
        self.frame_left_bot.grid_columnconfigure(0, weight=1)
       
        self.title = customtkinter.CTkLabel(master=self.frame_left_top,
                                              text="Available Drones",
                                              font=("Roboto Medium", -24))  # font name and size in px
        self.title.grid(row=0, column=0, pady=10, padx=10, sticky="w")

        self.drone_dropdown = customtkinter.CTkComboBox(master=self.frame_left_top,
                                                values=["No Selection"],
                                                command=self.on_selection_changed_event,
                                                height=40,
                                                font=("Roboto Medium", 14),
                                                dropdown_font=("Roboto Medium", 14))
        self.drone_dropdown.grid(row=1, column=0, pady=20, padx=15, sticky="nsew")
        
        self.button_connect = customtkinter.CTkButton(master=self.frame_left_top,
                                                   text="Connect",
                                                   width=150, 
                                                   height=65,
                                                   command=self.on_connect_pressed,
                                                   font=("Roboto Medium", 13))
        
        self.button_connect.grid(row=2, column=0, pady=10, padx=150, sticky="nsew")
        self.button_connect.configure(state=tkinter.DISABLED)

        # Configure and add UI elements to control panel frame
        self.control_panel_text = customtkinter.CTkLabel(master=self.frame_left_bot,
                                              text="NO DRONE CONNECTED",
                                              font=("Roboto Medium", -18))  # font name and size in px
        self.control_panel_text.grid(row=0, column=0, pady=10, padx=10, sticky="nsew")

        image = Image.open("images/NoImage.jpg").resize((500, 400))
        self.no_image = ImageTk.PhotoImage(image)

        self.image_label = tkinter.Label(master=self.frame_left_bot, image=self.no_image)
        self.image_label.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.image_label.grid(row=1, column=0, pady=5, padx=5)
        
        self.man = customtkinter.CTkLabel(master=self.frame_left_bot,
                                          text="MANUAL CONTROL ACTIVE",
                                          font=("Roboto Medium", 13),
                                          text_color="green")  # font name and size in px
        self.man.grid(row=2, column=0, pady=10, padx=10, sticky="nsew")

        self.loc = customtkinter.CTkLabel(master=self.frame_left_bot,
                                          text="Location: NONE",
                                          font=("Roboto Medium", 13))  # font name and size in px
        self.loc.grid(row=2, column=0, pady=10, padx=10, sticky="nsew")

        self.task = customtkinter.CTkLabel(master=self.frame_left_bot,
                                          text="Task: NONE",
                                          font=("Roboto Medium", 13))  # font name and size in px
        self.task.grid(row=3, column=0, pady=10, padx=10, sticky="nsew")

        self.state = customtkinter.CTkLabel(master=self.frame_left_bot,
                                            text="State: DISCONNECTED",
                                            font=("Roboto Medium", 13))  # font name and size in px
        self.state.grid(row=4, column=0, pady=10, padx=10, sticky="nsew")
        
        self.button_fly = customtkinter.CTkButton(master=self.frame_left_bot,
                                                   text="Fly Mission",
                                                   width=150, 
                                                   height=65,
                                                   command=self.on_fly_mission_pressed,
                                                   font=("Roboto Medium", 13))

        self.button_fly.grid(row=5, column=0, pady=5, padx=28, sticky="w")
        self.button_fly.configure(state=tkinter.DISABLED)
        
        self.button_kill = customtkinter.CTkButton(master=self.frame_left_bot,
                                                   text="Kill", 
                                                   width=150,
                                                   height=65, 
                                                   fg_color="#db1a2e",
                                                   hover_color="#a61624",
                                                   command=self.on_kill_mission_pressed,
                                                   font=("Roboto Medium", 13))

        self.button_kill.grid(row=5, column=0, pady=5, padx=28, sticky="e")
        self.button_kill.configure(state=tkinter.DISABLED)
        
        # Configure and add elements to map frame
        self.frame_right.grid_rowconfigure(1, weight=1)
        self.frame_right.grid_rowconfigure(0, weight=0)
        self.frame_right.grid_columnconfigure(0, weight=0)
        self.frame_right.grid_columnconfigure(1, weight=1)
        self.frame_right.grid_columnconfigure(2, weight=0)

        self.map_widget = TkinterMapView(self.frame_right, corner_radius=0)
        self.map_widget.grid(row=1, rowspan=3, column=0, columnspan=3, sticky="nswe", padx=(5, 5), pady=(5, 5))

        self.entry = customtkinter.CTkEntry(master=self.frame_right,
                                            placeholder_text="Search for an address here...")
        self.entry.grid(row=0, column=1,  sticky="we", padx=(12, 12), pady=12)
        self.entry.bind("<Return>", self.on_search_pressed)

        self.button_search = customtkinter.CTkButton(master=self.frame_right,
                                                text="Search",
                                                width=90,
                                                command=self.on_search_pressed)
        self.button_search.grid(row=0, column=2, sticky="we", padx=(12, 12), pady=12)

        # Set up the map
        self.map_widget.set_address("Pittsburgh")
        self.map_widget.set_zoom(13)
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    
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
            if self.drone_dropdown.values != ["No Selection"]:
                self.drone_dropdown.configure(values=["No Selection"])
                self.drone_dropdown.set("No Selection")
            self.on_disconnect_event()
        else:
            new_values = [d["name"] for d in new_list]
            if new_values != self.drone_dropdown.values:
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
                text_color="#1a80ba",
                font=("Roboto Medium", 13),
                marker_color_circle="#065b8c",
                marker_color_outside="#1a80ba",)
        self.on_connect_event()
        self.toggle_connect_button(False)


    # Events for handling the control panel

    def on_disconnect_event(self):
        self.connected_drone = None
        self.button_kill.configure(state=tkinter.DISABLED)
        self.button_fly.configure(state=tkinter.DISABLED)
        self.control_panel_text.configure(text="NO DRONE CONNECTED")
        self.loc.configure(text="Location: NONE")
        self.task.configure(text="Task: NONE")
        self.image_label.configure(image=self.no_image)
        if self.connected_marker != None:
            self.connected_marker.delete()
            self.connected_marker = None

    def on_connect_event(self):
        self.button_kill.configure(state=tkinter.NORMAL)
        self.button_fly.configure(state=tkinter.NORMAL)
        self.control_panel_text.configure(text="{0} Connected".format(self.connected_drone["name"]))
        self.on_update_event()

    def on_update_event(self, event=None):
        self.connected_marker.set_position(self.connected_drone["latitude"], self.connected_drone["longitude"])
        self.loc.configure(text="Location: {0}, {1}, {2}m".format(round(self.connected_drone["latitude"], 5), 
                round(self.connected_drone["longitude"], 5), self.connected_drone["altitude"]))
        self.task.configure(text="Task: {0}".format("Not Implemented"))

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
            SCP_URL = "teiszler@128.2.212.60:/var/www/html/scripts/" + "mission.dex"
            FLIGHT_URL = "http://128.2.212.60/scripts/" + "mission.dex" 
            subprocess.run(["scp", filename, SCP_URL])
            logger.info("Sent file {0} to the cloudlet".format(filename))
            command = {"drone": self.connected_drone["name"], "type": "start", "url": FLIGHT_URL}
            self.command_queue.put_nowait(command)
            self.toggle_manual(False)
        

    def on_kill_mission_pressed(self, event=None):
        command = {"drone": self.connected_drone["name"], "type": "kill"}
        self.command_queue.put_nowait(command)
        self.toggle_manual(True)


    # Events for handling the search bar

    def on_search_pressed(self, event=None):
        self.map_widget.set_address(self.entry.get())


    # Gabriel

    def set_up_adapter(self, preprocess, source_name, id):
        self.id = id
        self._preprocess = preprocess
        self._source_name = source_name
        self.frames_processed = 0

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
                    extras.cmd.script_url = command["url"]
            elif self.connected_drone != None:
                extras.cmd.for_drone_id = self.connected_drone["name"]

            if self.manual:
                if self.control.takeoff():
                    extras.takeoff = True
                if self.control.landing():
                    extras.land = True
                if self.control.has_piloting_cmd():
                    extras.PCMD.yaw = self.control.yaw()
                    extras.PCMD.pitch = self.control.pitch()
                    extras.PCMD.roll = self.control.roll()
                    extras.PCMD.gaz = self.control.throttle()

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
            self.man.configure(text="MANUAL CONTROL ACTIVE", text_color="green")
        else:
            self.man.configure(text="AUTONOMOUS CONTROL ACTIVE", text_color="orange")

    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.mainloop()
