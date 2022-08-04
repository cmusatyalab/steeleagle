import customtkinter
import tkinter
from tkintermapview import TkinterMapView
from PIL import Image, ImageTk

customtkinter.set_default_color_theme("blue")


class App(customtkinter.CTk):

    APP_NAME = "Command and Control Interface"
    WIDTH = 1800
    HEIGHT = 1000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(App.APP_NAME)
        self.geometry(str(App.WIDTH) + "x" + str(App.HEIGHT))
        self.minsize(App.WIDTH, App.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", self.on_closing)
        self.bind("<Command-w>", self.on_closing)
        self.createcommand('tk::mac::Quit', self.on_closing)

        self.drone_list = ["NONE AVAILABLE"]
        
        customtkinter.set_appearance_mode("Dark")
        customtkinter.set_default_color_theme("green")

        # ============ create CTkFrames ============

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=20)
        self.grid_rowconfigure(0, weight=1)

        self.frame_left_top = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_left_top.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.frame_left_bot = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_left_bot.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        self.frame_right = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_right.grid(row=0, column=1, rowspan=3, pady=5, padx=5, sticky="nsew")

        # ============ frame_left ============
        
        self.frame_left_top.grid_columnconfigure(0, weight=1)
        self.frame_left_bot.grid_columnconfigure(0, weight=1)
       
        self.title = customtkinter.CTkLabel(master=self.frame_left_top,
                                              text="Available Drones",
                                              text_font=("Roboto Medium", -24))  # font name and size in px
        self.title.grid(row=0, column=0, pady=10, padx=10, sticky="w")

        self.drone_dropdown = customtkinter.CTkOptionMenu(master=self.frame_left_top,
                                                          values=self.drone_list,
                                                          height=40) 
        self.drone_dropdown.grid(row=1, column=0, pady=20, padx=15, sticky="nsew")
        
        self.button_connect = customtkinter.CTkButton(master=self.frame_left_top,
                                                   text="Connect",
                                                   width=150, 
                                                   height=65,
                                                   fg_color=None,
                                                   border_color="gray",
                                                   border_width=3,
                                                   text_font=("Roboto Medium", 13))
        
        self.button_connect.grid(row=2, column=0, pady=10, padx=150, sticky="nsew")
        self.button_connect.configure(state=tkinter.DISABLED)


        self.control_panel = customtkinter.CTkLabel(master=self.frame_left_bot,
                                              text="NO DRONE CONNECTED",
                                              text_font=("Roboto Medium", -18))  # font name and size in px
        self.control_panel.grid(row=0, column=0, pady=10, padx=10, sticky="nsew")

        image = Image.open("/home/mbala/Downloads/NoImage.jpg").resize((500, 400))
        self.stream_image = ImageTk.PhotoImage(image)

        self.image_label = tkinter.Label(master=self.frame_left_bot, image=self.stream_image)
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
        
        self.button_send = customtkinter.CTkButton(master=self.frame_left_bot,
                                                   text="Fly Mission",
                                                   width=150, 
                                                   height=65,
                                                   fg_color=None,
                                                   border_color="gray",
                                                   border_width=3,
                                                   text_font=("Roboto Medium", 13))

        self.button_send.grid(row=5, column=0, pady=5, padx=28, sticky="w")
        self.button_send.configure(state=tkinter.DISABLED)
        
        self.button_kill = customtkinter.CTkButton(master=self.frame_left_bot,
                                                   text="Kill", 
                                                   width=150,
                                                   height=65, 
                                                   fg_color=None,
                                                   border_color="gray",
                                                   border_width=3,
                                                   text_font=("Roboto Medium", 13))

        self.button_kill.grid(row=5, column=0, pady=5, padx=28, sticky="e")
        self.button_kill.configure(state=tkinter.DISABLED)
        
        # ============ frame_right ============

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
        self.entry.entry.bind("<Return>", self.search_event)

        self.button_search = customtkinter.CTkButton(master=self.frame_right,
                                                text="Search",
                                                width=90,
                                                command=self.search_event)
        self.button_search.grid(row=0, column=2, sticky="we", padx=(12, 12), pady=12)

        # Set up the map
        self.map_widget.set_address("Pittsburgh")
        self.map_widget.set_zoom(13)
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    def search_event(self, event=None):
        self.map_widget.set_address(self.entry.get())

    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.mainloop()


if __name__ == "__main__":
    app = App()
    app.start()
