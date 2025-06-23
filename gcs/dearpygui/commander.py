import dearpygui.dearpygui as dpg

import yaml
import redis
import zmq
import time
import webbrowser
import random
import os

#TODO: Get these from redis
TYPES = ["ANAFI", "ANAFI USA", "ANAFI Ai", "ModalAi Seeker", "ModalAi Starling"]
STATUSES = ["offline", "idle", "TrackingTask", "PatrolTask"]
STATUS_COLORS = [(255,0,0), (0,255,255), (200,0,200), (200,0,200)]

with open('config.yaml', 'r') as conf:
    SECRETS = yaml.safe_load(conf)

def connect_redis():
    red = redis.Redis(
        host=SECRETS['redis']['host'],
        port=SECRETS['redis']['port'],
        username=SECRETS['redis']['user'],
        password=SECRETS['redis']['pass'],
        decode_responses=True,
    )
    return red

def connect_zmq():
    ctx = zmq.Context()
    z = ctx.socket(zmq.REQ)
    z.connect(f"tcp://{SECRETS['zmq']['host']}:{SECRETS['zmq']['port']}")
    return z


def get_drones(threshold=999999):
    l = {}
    red = connect_redis()
    for k in red.keys("telemetry.*"):
        latest_entry = red.xrevrange(f"{k}", "+", "-", 1)
        last_update = (int(latest_entry[0][0].split("-")[0])/1000)
        if time.time() - last_update <  threshold * 60: # minutes -> seconds
            l[f"{k.split('.')[-1]}"] = f"**{k.split('.')[-1]}** " 

    return sorted(l)

def _log_interaction(sender, app_data, user_data):
    current = dpg.get_value("status_bar_text")
    dpg.set_value("status_bar_text", f"sender: {sender}\tapp_data: {app_data}\tuser_data: {user_data}\n{current}")

def _log(arbitrary):
    current = dpg.get_value("status_bar_text")
    dpg.set_value("status_bar_text", f"{arbitrary}\n{current}")


def _select_all(sender, app_data, user_data):
    selections.clear()
    for item in dronelist:
        selections.append(f'{item}_selectable')
        dpg.set_value(f'{item}_selectable', True)
    _log_interaction(sender, app_data, selections)

def _select_none(sender, app_data, user_data):
    selections.clear()
    for item in dronelist:
        dpg.set_value(f'{item}_selectable', False)
    _log_interaction(sender, app_data, selections)

def _selection(sender, app_data, user_data):
    if sender not in selections:
        selections.append(sender)
        dpg.set_value(sender, True)
    else:
        selections.remove(sender)
        dpg.set_value(sender, False)
    print(f'Sender: {sender}  Currrent Selection:{selections}')
    _log_interaction(sender, app_data, selections)

def _hyperlink(text, address):
    b = dpg.add_button(label=text, callback=lambda:webbrowser.open(address))

def _add_card(label='Card', model="ANAFI", status="offline", tag_prefix="Card"):
    with dpg.table(tag=f'{tag_prefix}_table', row_background=False, resizable=False, header_row=False, borders_innerH=True,  borders_outerH=True, borders_innerV=True, borders_outerV=True):
        dpg.add_table_column(no_resize=True, init_width_or_weight=0.25)            
        dpg.add_table_column()

        with dpg.table_row():
            dpg.add_checkbox(tag=f'{tag_prefix}_selectable', indent=4)
            dpg.configure_item(f'{tag_prefix}_selectable', callback=_selection, user_data=selections)
            dpg.add_text(f'{label}', )
            dpg.add_table_cell()

        with dpg.table_row():
            #dpg.add_table_cell()
            dpg.add_text('Model')
            dpg.add_text(f'{model}')

        with dpg.table_row():
            #dpg.add_table_cell()
            dpg.add_text('Batt')
            dpg.add_text(f'{random.randint(0,100)}%',)

        with dpg.table_row():
            dpg.add_text('Status')
            dpg.add_text(STATUSES[status], color=STATUS_COLORS[status],)

def _help(message):
    last_item = dpg.last_item()
    group = dpg.add_group(horizontal=True)
    dpg.move_item(last_item, parent=group)
    dpg.capture_next_item(lambda s: dpg.move_item(s, parent=group))
    t = dpg.add_text("[?]", color=[128, 128, 128])
    with dpg.tooltip(t):
        dpg.add_text(message)

def _key_handler(sender, data):
    print(f"sender: {sender} data: {data}")
    type=dpg.get_item_info(sender)["type"]
    if type=="mvAppItemType::mvKeyDownHandler":
        match data[0]:
            case 68:
                vel = dpg.get_value("roll_slider")
                _log(f"Roll+ {vel} m/s")
            case 65:
                vel = dpg.get_value("roll_slider")
                _log(f"Roll- {vel} m/s")
            case 87:
                vel = dpg.get_value("pitch_slider")
                _log(f"Pitch+ {vel} m/s")
            case 83:
                vel = dpg.get_value("pitch_slider")
                _log(f"Pitch- {vel} m/s")
            case _:
                _log(f"Key pressed: {data}")

def update_dronelist():
    dronelist = get_drones(dpg.get_value("active_slider"))
    dpg.delete_item(item='dronelist_group', children_only=True, )
    for item in dronelist:
        dpg.add_selectable(parent='dronelist_group', label=item, tag=f'{item}_selectable', indent=10)
        dpg.configure_item(f'{item}_selectable', callback=_selection, user_data=selections)

def update_imagery():
    if dpg.get_item_alias(dpg.get_value("imagery_tabbar")) == "detection_tab":
        width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/detected/latest.jpg")
        dpg.set_value("texture_detection", data)
    elif dpg.get_item_alias(dpg.get_value("imagery_tabbar")) == "avoidance_tab":
        width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/moa/latest.jpg")
        dpg.set_value("texture_moa", data)
    elif dpg.get_item_alias(dpg.get_value("imagery_tabbar")) == "hsv_tab":
        width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/detected/hsv.jpg")
        dpg.set_value("texture_hsv", data)
    else:
        for d in get_drones():
            if dpg.get_item_alias(dpg.get_value("imagery_tabbar")) == f"{d}_tab":
                width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/raw/{d}/latest.jpg")
                dpg.set_value(f"texture_{d}", data)
                #dpg.configure_item(f"texture_{d}", width=width, height=height, default_value=data)
                #dpg.configure_item(f"latest_{d}", texture_tag=f"texture_{d}")


def arm_disarm(sender, app_data, user_data):
    _log_interaction(sender, app_data, user_data)
    if app_data:
        dpg.set_value("manual_control_label", "Manual Control Enabled")
        dpg.configure_item("manual_control_label", color=(0,255,0))
    else:
        dpg.set_value("manual_control_label", "Manual Control Disabled")
        dpg.configure_item("manual_control_label", color=(255,0,0))


def set_mission(sender, app_data, user_data):
    _log_interaction(sender, app_data, user_data)
    dpg.set_value("selected_dsl_path", app_data["file_name"])
    dpg.configure_item("selected_dsl_path", color=(235, 128, 52))

def set_scope(sender, app_data, user_data):
    _log_interaction(sender, app_data, user_data)
    dpg.set_value("selected_kml_path", app_data["file_name"])
    dpg.configure_item("selected_kml_path", color=(235, 128, 52))

def save_init():
    dpg.save_init_file('dpg.ini')
    _log("Saved window positions to dpg.ini.")

dronelist = get_drones()

dpg.create_context()
with dpg.font_registry(tag='font_registry'):
    for filename in os.listdir('Fonts'):
        if filename.endswith((".ttf","otf")):
            font = dpg.add_font(f"Fonts/{filename}", 16)
dpg.bind_font(font)


with dpg.theme(tag="global_theme") as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (12, 12, 12), category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1 , category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 10 , category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1 , category=dpg.mvThemeCat_Core)
dpg.bind_theme(global_theme)

dpg.create_viewport(title='SteelEagle Commander', min_height=720, min_width=1280)

with dpg.viewport_menu_bar():
    with dpg.menu(label="Preferences"):
        dpg.add_menu_item(label="Font Registry", callback=lambda:dpg.show_tool(dpg.mvTool_Font))
        dpg.add_menu_item(label="Style Editor", callback=lambda:dpg.show_tool(dpg.mvTool_Style))
    with dpg.menu(label="Help"):
        dpg.add_menu_item(label="Show Metrics", callback=lambda:dpg.show_tool(dpg.mvTool_Metrics))
        dpg.add_menu_item(label="Show Item Registry", callback=lambda:dpg.show_tool(dpg.mvTool_ItemRegistry))

with dpg.handler_registry(show=True, tag="keyboard_handler"):
    k_press = dpg.add_key_down_handler(key=dpg.mvKey_A, callback=_key_handler)
    k_press = dpg.add_key_down_handler(key=dpg.mvKey_W, callback=_key_handler)
    k_press = dpg.add_key_down_handler(key=dpg.mvKey_S, callback=_key_handler)
    k_press = dpg.add_key_down_handler(key=dpg.mvKey_D, callback=_key_handler)


selections = []
with dpg.window(tag='drone_list', label="Available Drones", pos=[400,100], menubar=True, autosize=True, no_close=True, no_resize=True):
    with dpg.menu_bar():
        with dpg.menu(label="Selection"):
            dpg.add_menu_item(label="Select All", callback=_select_all)
            dpg.add_menu_item(label="Select None", callback=_select_none)

    for item in dronelist:
        _add_card(label=item, tag_prefix=item, model=random.choice(TYPES), status=random.randint(0,len(STATUSES)-1))

with dpg.window(tag='control_pane', label="Control Pane", autosize=True, no_close=True, no_resize=True):
    dpg.add_checkbox(tag="arm_checkbox", label="Arm Swarm?", callback=arm_disarm)
    dpg.add_text(tag="manual_control_label", default_value="Manual Control Disabled", color=(255,0,0))
    _help("When armed, manual commands can be sent to all selected drones.")
    dpg.add_separator()
    dpg.add_separator()
    dpg.add_text(tag="autonomous_header", default_value="Autonomous Control", color=(168, 52, 235))
    with dpg.file_dialog(
        directory_selector=False, modal=True, show=False, callback=set_mission, tag="dsl_dialog",
        cancel_callback=_log_interaction, width=700 ,height=400):
            dpg.add_file_extension(".dsl", color=(0, 255, 0, 255))
    with dpg.file_dialog(
        directory_selector=False, modal=True, show=False, callback=set_scope, tag="kml_dialog",
        cancel_callback=_log_interaction, width=700 ,height=400):
            dpg.add_file_extension(".kml", color=(0, 255, 0, 255))
    dpg.add_text(tag="selected_dsl_path", default_value="No mission selected.")
    dpg.add_button(label="Select Mission Script...", width=200,callback=lambda: dpg.show_item("dsl_dialog"))
    dpg.add_text(tag="selected_kml_path", default_value="No scope selected.")
    dpg.add_button(label="Select Scope...", width=200,callback=lambda: dpg.show_item("kml_dialog"))

    dpg.add_separator()
    dpg.add_spacer(height=50)
    dpg.add_button(tag="autonomous_button", label="Fly Mission", width=200, callback=_log_interaction)
    _help("Fly the selected drones with the selected mission/scope.")
    dpg.add_button(tag="halt_button", label="Halt All", width=200, callback=_log_interaction)
    _help("Instruct selected drones to immediately hover.")
    dpg.add_button(tag="rth_button", label="Return Home", width=200, callback=_log_interaction)
    _help("Instruct selected drones to return to their last home location.")
    dpg.add_spacer(height=50)
    #sliders for manual control
    with dpg.group(horizontal=True):
        dpg.add_slider_int(tag="yaw_slider", default_value=45, vertical=True, min_value=0, max_value=180, clamped=True, format='%.1f\ndeg/s', width=40, height=100, callback=_log_interaction)
        dpg.add_slider_float(tag="pitch_slider", default_value=1.0, vertical=True, min_value=0.0, max_value=5.0, clamped=True, format='%.1f\nm/s', width=30, height=100, callback=_log_interaction)
        dpg.add_slider_float(tag="roll_slider", default_value=1.0, vertical=True, min_value=0.0, max_value=5.0, clamped=True, format='%.1f\nm/s', width=30, height=100, callback=_log_interaction)
        dpg.add_slider_float(tag="thrust_slider", default_value=1.0, vertical=True, min_value=0.0, max_value=5.0, clamped=True, format='%.1f\nm/s', width=30, height=100, callback=_log_interaction)
        dpg.add_slider_int(tag="gimbal_slider", default_value=45, vertical=True, min_value=0, max_value=180, clamped=True, format='%.1f\ndeg/s', width=40, height=100, callback=_log_interaction)
    with dpg.group(horizontal=True):
        dpg.add_text("Yaw")
        dpg.add_text("Pitch")
        dpg.add_text("Roll")
        dpg.add_text("Thrust")
        dpg.add_text("Gimbal")

with dpg.window(tag='main_window', autosize=True, no_resize=True, on_close=save_init):
    dpg.add_spacer(height=20)
    # load initial images into texture registry
    with dpg.texture_registry(show=False):
        width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/detected/latest.jpg")
        dpg.add_raw_texture(width=width, height=height, default_value=data, tag="texture_detection")
        width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/moa/latest.jpg")
        dpg.add_raw_texture(width=width, height=height, default_value=data, tag="texture_moa")
        width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/detected/hsv.jpg")
        dpg.add_raw_texture(width=width, height=height, default_value=data, tag="texture_hsv")
        for d in get_drones():
            width, height, channels, data = dpg.load_image(f"{SECRETS['image_vol']}/raw/{d}/latest.jpg")
            dpg.add_raw_texture(width=width, height=height, default_value=data, tag=f"texture_{d}")

    with dpg.tab_bar(tag="page_tabbar"):
        with dpg.tab(tag="overview_tab", label="Live Imagery"):
            with dpg.tab_bar(tag="imagery_tabbar"):
                for d in get_drones():
                    with dpg.tab(tag=f"{d}_tab", label=f"{d}"):
                        dpg.add_image(tag=f"latest_{d}", texture_tag=f"texture_{d}")  
                with dpg.tab(tag="detection_tab", label="Object Dection"):
                    dpg.add_image(tag="latest_detection", texture_tag="texture_detection", width=1280, height=720)
                with dpg.tab(tag="avoidance_tab", label="Obstacle Avoidance"):
                    dpg.add_image(tag="latest_moa", texture_tag="texture_moa", width=1280, height=720)
                with dpg.tab(tag="hsv_tab", label="HSV Filter"):
                    dpg.add_image(tag="latest_hsv", texture_tag="texture_hsv", width=1280, height=720)
            """ with dpg.group(tag="map_group"):
                def toggle_layer2(sender):
                    show_value = dpg.get_value(sender)
                    dpg.configure_item("layer2", show=show_value)

                dpg.add_checkbox(label="show layer", callback=toggle_layer2, default_value=True)
                with dpg.drawlist(width=300, height=300):
                        with dpg.draw_layer():
                            dpg.draw_line((10, 10), (100, 100), color=(255, 0, 0, 255), thickness=1)
                            dpg.draw_text((0, 0), "Origin", color=(250, 250, 250, 255), size=15)
                            dpg.draw_arrow((50, 70), (100, 65), color=(0, 200, 255), thickness=1, size=10)

                        with dpg.draw_layer(tag="layer2"):
                            dpg.draw_line((10, 60), (100, 160), color=(255, 0, 0, 255), thickness=1)
                            dpg.draw_arrow((50, 120), (100, 115), color=(0, 200, 255), thickness=1, size=10) 
            """
        with dpg.tab(tag="planning_tab",label="Mission Planning"):
            with dpg.group(tag="planning_group",):
                dpg.add_input_text(label="Mission DSL", multiline=True, )
                with dpg.node_editor( minimap=True, minimap_location=dpg.mvNodeMiniMap_Location_BottomRight):
                    with dpg.node(label="Node 1"):
                        with dpg.node_attribute(label="Node A1"):
                            dpg.add_input_float(label="F1", width=150)

                        with dpg.node_attribute(label="Node A2", attribute_type=dpg.mvNode_Attr_Output):
                            dpg.add_input_float(label="F2", width=150)

                    with dpg.node(label="Node 2"):
                        with dpg.node_attribute(label="Node A3"):
                            dpg.add_input_float(label="F3", width=200)

                        with dpg.node_attribute(label="Node A4", attribute_type=dpg.mvNode_Attr_Output):
                            dpg.add_input_float(label="F4", width=200)

with dpg.window(tag="log", label="Logging", min_size=[500,100], no_close=True, no_resize=True, horizontal_scrollbar=True):
    dpg.add_text(tag="status_bar_text", label="log messages", wrap=500)

dpg.setup_dearpygui()
dpg.set_primary_window('main_window', True)
dpg.configure_app(init_file="dpg.ini")
dpg.show_viewport()

# below replaces, start_dearpygui()
last_imagery_update = time.time()
while dpg.is_dearpygui_running():
    t0 = time.time()
    update_imagery()
    t1 = time.time()
    #_log(f"Updating imagery took {t1-t0}")
    dpg.render_dearpygui_frame()

dpg.destroy_context()