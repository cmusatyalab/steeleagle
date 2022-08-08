import customtkinter
import tkinter
from tkinter import filedialog as fd
from tkintermapview import TkinterMapView
from PIL import Image, ImageTk
from queue import Queue
import logging
from cnc_protocol import cnc_pb2
import asyncio
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper
import json

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

        self.drone_dict = {}
        self.connected_drone = None
        self.connected_marker = None
        self.connected_flightplan = None
        self.command_queue = Queue()
        
        customtkinter.set_appearance_mode("Dark")
        customtkinter.set_default_color_theme("sweetkind")

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
                                              text_font=("Roboto Medium", -24))  # font name and size in px
        self.title.grid(row=0, column=0, pady=10, padx=10, sticky="w")

        self.drone_dropdown = customtkinter.CTkOptionMenu(master=self.frame_left_top,
                                                          values=["No Selection"],
                                                          command=self.on_selection_changed_event,
                                                          height=40,
                                                          text_font=("Roboto Medium", 11))
        self.drone_dropdown.grid(row=1, column=0, pady=20, padx=15, sticky="nsew")
        
        self.button_connect = customtkinter.CTkButton(master=self.frame_left_top,
                                                   text="Connect",
                                                   width=150, 
                                                   height=65,
                                                   command=self.on_connect_pressed,
                                                   text_font=("Roboto Medium", 13))
        
        self.button_connect.grid(row=2, column=0, pady=10, padx=150, sticky="nsew")
        self.button_connect.configure(state=tkinter.DISABLED)

        # Configure and add UI elements to control panel frame
        self.control_panel_text = customtkinter.CTkLabel(master=self.frame_left_bot,
                                              text="NO DRONE CONNECTED",
                                              text_font=("Roboto Medium", -18))  # font name and size in px
        self.control_panel_text.grid(row=0, column=0, pady=10, padx=10, sticky="nsew")

        image = Image.open("images/NoImage.jpg").resize((500, 400))
        self.no_image = ImageTk.PhotoImage(image)

        self.image_label = tkinter.Label(master=self.frame_left_bot, image=self.no_image)
        self.image_label.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.image_label.grid(row=1, column=0, pady=5, padx=5)

        self.loc = customtkinter.CTkLabel(master=self.frame_left_bot,
                                          text="Location: NONE",
                                          text_font=("Roboto Medium", 13))  # font name and size in px
        self.loc.grid(row=2, column=0, pady=10, padx=10, sticky="nsew")

        self.task = customtkinter.CTkLabel(master=self.frame_left_bot,
                                          text="Task: NONE",
                                          text_font=("Roboto Medium", 13))  # font name and size in px
        self.task.grid(row=3, column=0, pady=10, padx=10, sticky="nsew")

        self.state = customtkinter.CTkLabel(master=self.frame_left_bot,
                                            text="State: DISCONNECTED",
                                            text_font=("Roboto Medium", 13))  # font name and size in px
        self.state.grid(row=4, column=0, pady=10, padx=10, sticky="nsew")
        
        self.button_fly = customtkinter.CTkButton(master=self.frame_left_bot,
                                                   text="Fly Mission",
                                                   width=150, 
                                                   height=65,
                                                   command=self.on_fly_mission_pressed,
                                                   text_font=("Roboto Medium", 13))

        self.button_fly.grid(row=5, column=0, pady=5, padx=28, sticky="w")
        self.button_fly.configure(state=tkinter.DISABLED)
        
        self.button_kill = customtkinter.CTkButton(master=self.frame_left_bot,
                                                   text="Kill", 
                                                   width=150,
                                                   height=65, 
                                                   fg_color="#db1a2e",
                                                   hover_color="#a61624",
                                                   command=self.on_kill_mission_pressed,
                                                   text_font=("Roboto Medium", 13))

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
        self.entry.entry.bind("<Return>", self.on_search_pressed)

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
            self.button_connect.configure(state="enable")
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
        self.state.configure(text="State: DISCONNECTED")
        self.image_label.configure(image=self.no_image)
        self.connected_marker.delete()

    def on_connect_event(self):
        self.button_kill.configure(state="enable")
        self.button_fly.configure(state="enable")
        self.control_panel_text.configure(text="{0} Connected".format(self.connected_drone["name"]))
        self.on_update_event()

    def on_update_event(self, event=None):
        self.connected_marker.set_position(self.connected_drone["latitude"], self.connected_drone["longitude"])
        self.loc.configure(text="Location: {0}, {1}, {2}m".format(self.connected_drone["latitude"], 
                self.connected_drone["longitude"], self.connected_drone["altitude"]))
        self.task.configure(text="Task: {0}".format("Not Implemented"))
        self.state.configure(text="State: {0}".format(self.connected_drone["state"]))
        frame = Image.read(self.connected_drone["frame"])
        self.image_label.configure(image=frame)

    def on_fly_mission_pressed(self, event=None):
        filetypes = (
            ('Dex files', '*.dex'),
        )

        filename = fd.askopenfilename(
            title='Open a file',
            initialdir='.',
            filetypes=filetypes)

        print("Selected file: " + filename)
        # TODO: Send a URL to the file

    def on_kill_mission_pressed(self, event=None):
        command = {"drone": self.connected_drone["name"], "type": "kill"}
        self.command_queue.put_nowait(command)


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
            await asyncio.sleep(0.2)
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

            input_frame.extras.Pack(extras)

            return input_frame

        return [
            ProducerWrapper(producer=producer, source_name=self._source_name)
        ]
           
    def consumer(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            logger.error('Got %d results from server'.
                    len(result_wrapper.results))
            return
        
        result = result_wrapper.results[0]
        if result.payload_type != gabriel_pb2.PayloadType.TEXT:
            type_name = gabriel_pb2.PayloadType.Name(result.payload_type)
            logger.error('Got result of type %s', type_name)
            return

        self.frames_processed += 1
        payload = result.payload.decode('utf-8')
        try:
            data = json.loads(payload)
            self.on_drone_list_changed_event(data)
        except:
            print("Response from server: " + payload)


    # Cleanup and start events

    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.mainloop()


