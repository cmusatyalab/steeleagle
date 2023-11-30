#!/usr/bin/env python3

# Copyright 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
from gabriel_client.websocket_client import WebsocketClient
import logging
import randomname
import os

COMMANDER_ID = randomname.get_name(adj=('age',), noun=('military_army', 'military_navy'))
WEBSOCKET_PORT = 9099
DEFAULT_SOURCE_NAME = 'command'

logger = logging.getLogger(__name__)

def preprocess(frame):
    return frame

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', default='localhost',
        help='Specify address of Steel Eagle CNC server [default: localhost')
    parser.add_argument('-p', '--port', default='9099', help='Specify websocket port [default: 9099]')
    parser.add_argument('-l', '--loglevel', default='INFO', help='Set the log level')
    parser.add_argument('-ng', '--nogui', action='store_true', help='If specified, use the text prompt commander') 
    
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s", level=args.loglevel)
    COMMANDER_ID = os.uname()[1]
    if args.nogui:
        from text_commander_adapter import TextCommanderAdapter
        
        adapter = TextCommanderAdapter(preprocess, DEFAULT_SOURCE_NAME, COMMANDER_ID)
        producer = adapter.get_producer_wrappers()
        consumer = adapter.consumer
    else:

        from gui_commander_adapter import GUICommanderAdapter
        from threading import Thread, Event
        
        def start_ui_thread(funcs, funcSet):
            UI = GUICommanderAdapter() # Must initialize the UI in the thread in which it will run
            UI.set_up_adapter(preprocess, DEFAULT_SOURCE_NAME, COMMANDER_ID, args.server)
            funcs.append(UI.get_producer_wrappers())
            funcs.append(UI.consumer)
            funcSet.set()
            UI.start()

        funcs = [] # Need to get callback functions from the UI thread
        funcSet = Event()
        t = Thread(target=start_ui_thread, args=(funcs, funcSet))
        t.start()
        funcSet.wait(5) # Wait for signal from UI thread that functions are set
        producer, consumer = funcs[0], funcs[1]

    client = WebsocketClient(
        args.server, args.port,
        producer, consumer
    )

    client.launch()
    

if __name__ == '__main__':
    main()
