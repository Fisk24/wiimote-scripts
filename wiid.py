#!/usr/bin/env python

# test with
# sudo LD_LIBRARY_PATH=<prefix>/lib PYTHONPATH=<prefix>/lib/python2.7/site-packages python ./swig/python/xwiimote_test.py

import errno
from time import sleep
from select import poll, POLLIN
from inspect import getmembers
from pprint import pprint
import xwiimote
import sys, os

'''
try:
    while True:
        lookfor_and_setup_wiimote() <- with its own loop, so that it can keep trying until it finds one
        # Now that we have a wiimote
        handle_events() <- with its own loop so that it handles events continuously. 
        # - Events like xwiimote.EVENT_GONE should return from this function 
        and cause the outer loop to continue, forcing the script to look for wiimotes again.
except KeyboardInterrupt:
    ShutdownCodeHere
'''

# display a constant
print("=== " + xwiimote.NAME_CORE + " ===")

class Daemon():
    def __init__(self, dev_mode):
        self.dev_mode = dev_mode

        self.monitor  = self.setup_monitor()
        self.wiimote  = None
        self.poller   = poll()
        self.bindings = [
                {"name": "Left",  "code":0,  "action": self.send_keys,  "args":["Left"],           "modifier_action":self.send_keys, "modifier_args":["F5"]},
                {"name": "Right", "code":1,  "action": self.send_keys,  "args":["Right"],          "modifier_action":self.dummy,     "modifier_args":[]},

                {"name": "Up",    "code":2,  "action": self.send_keys,  "args":["Up",   "hold"], "action_up":self.send_keys,  "args_up":["Up",   "release"], "modifier_action":self.dummy,     "modifier_args":[]},
                {"name": "Down",  "code":3,  "action": self.send_keys,  "args":["Down", "hold"], "action_up":self.send_keys,  "args_up":["Down", "release"], "modifier_action":self.dummy,     "modifier_args":[]},
                {"name": "A",     "code":4,  "action": self.send_click, "args":["1",    "hold"], "action_up":self.send_click, "args_up":["1",    "release"], "modifier_action":self.send_keys, "modifier_args":["ctrl+w"]}, 

                {"name": "B",     "code":5,  "action": "modifier"},

                {"name": "Plus",  "code":6,  "action": self.send_keys,  "args":["ctrl+Page_Down"], "modifier_action":self.send_keys, "modifier_args":["XF86AudioRaiseVolume"]},
                {"name": "Minus", "code":7,  "action": self.send_keys,  "args":["ctrl+Page_Up"],   "modifier_action":self.send_keys, "modifier_args":["XF86AudioLowerVolume"]},
                {"name": "Home",  "code":8,  "action": self.send_keys,  "args":["ctrl+alt+Down"],  "modifier_action":self.dummy,     "modifier_args":[]},
                {"name": "1",     "code":9,  "action": self.send_click, "args":["2"],              "modifier_action":self.dummy,     "modifier_args":[]},
                {"name": "2",     "code":10, "action": self.send_click, "args":["3"],              "modifier_action":self.dummy,     "modifier_args":[]},
                ]

        '''
        1 – Left click
        2 – Middle click
        3 – Right click
        4 – Scroll wheel up
        5 – Scroll wheel down

        xdotool key --clearmodifiers XF86AudioPlay
        xdotool key --clearmodifiers XF86AudioPrev
        xdotool key --clearmodifiers XF86AudioNext
        xdotool key --clearmodifiers XF86AudioLowerVolume
        xdotool key --clearmodifiers XF86AudioRaiseVolume
        xdotool key --clearmodifiers XF86AudioMute
        '''

        self.modifier_flag = False

        self.main_loop()

    def main_loop(self):
        try:
            while True:
                self.search_for_wiimote()
                self.handle_wiimote()
                if dev_mode:
                    if self.wiimote != None:
                        self.poller.unregister(self.wiimote.get_fd())
                        exit(0)
        except KeyboardInterrupt:
            print("KeyboardInterrupt: Exiting...")
            if self.wiimote != None:
                self.poller.unregister(self.wiimote.get_fd())
                exit(0)

    def handle_key(self, code, state):
        '''
        action: modifier <- define a modifier in one key definition
        if action == modifier:
           active_modifiers.append(code) 

        needs_modifier: 7      <- in another key definition
        if binding["needs_modifier"] in active_modifiers:
            binding["action"](*binding["args"]) 
        '''
        for binding in self.bindings:
            # if button down and if we find the right 
            if ((state == 1) and (code == binding["code"])):
                #print(binding["name"])
                if binding["action"] == "modifier":
                    self.modifier_flag = True
                else:
                    if not self.modifier_flag:
                        binding["action"](*binding["args"])
                    else:
                        binding["modifier_action"](*binding["modifier_args"])
            elif ((state == 0) and (code == binding["code"])):
                #print(binding["name"])
                if binding["action"] == "modifier":
                    self.modifier_flag = False
                if "action_up" in binding.keys():
                    binding["action_up"](*binding["args_up"])

        print(code, state)

    def dummy(self):
        pass

    def send_click(self, button, method="click"):
        if method == "click":
            os.system("xdotool click "+button)
        elif method == "hold":
            os.system("xdotool mousedown "+button)
        elif method == "release":
            os.system("xdotool mouseup "+button)
        else:
            print("Daemon.send_click(): Incorrect method applied ->", method)

    def send_keys(self, keys, method="once", delay="12"):
        print(keys)
        if method == "once":
            os.system("xdotool key "+keys)
        elif method == "hold":
            os.system("xdotool keydown "+keys)
        elif method == "release":
            os.system("xdotool keyup "+keys)

    def handle_wiimote(self):
        evt = xwiimote.event()
        while True:
            self.poller.poll()
            try:

                self.wiimote.dispatch(evt)
                if evt.type == xwiimote.EVENT_KEY:
                    code, state = evt.get_key()
                    self.handle_key(code, state)
                
                elif evt.type == xwiimote.EVENT_GONE:
                    print("Wiimote is gone! Don't panic!")
                    return
            
                elif evt.type == xwiimote.EVENT_WATCH:
                    print("Watch")
            
            except IOError as e:
                if e.errno != errno.EAGAIN:
                    print("Bad")


    def search_for_wiimote(self):
        # Search for wiimotes, forever if you have to...
        while True:
            found_wiimote = self.monitor_find_wiimote()
            if found_wiimote != None:
                # setup the found wiimote and break, mission accomplished!
                self.wiimote = self.setup_wiimote(found_wiimote)
                break
            else:
                print("Found no wiimotes, retrying in 2 seconds...")
                sleep(2)

    def setup_monitor(self):
        # setup monitor
        try:
            mon = xwiimote.monitor(True, True)
            print("mon fd", mon.get_fd(False))
            return mon

        except SystemError as e:
            print("ooops, cannot create monitor (", e, ")") 

    def monitor_find_wiimote(self):
        # Grab the first
        ent = self.monitor.poll()
        firstwiimote = ent
        while ent is not None:
            print("Found device: " + ent)
            ent = self.monitor.poll()

        # continue only if there is a wiimote
        if firstwiimote is None:
            print("No wiimote to read")
            return None
        else:
            return firstwiimote

    def setup_wiimote(self, wiimote):
        try:
            # create new iface
            dev = xwiimote.iface(wiimote)
            # open device
            sleep(0.1)
            dev.open(dev.available() |  xwiimote.IFACE_WRITABLE)
            print("Opened device")
            # register it with the poller
            self.poller.register(dev.get_fd(), POLLIN)
            return dev

        except IOError as e:
            print("ooops,", e)
            #exit(1)

if __name__ == "__main__":
    dev_mode = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "dev_mode":
            dev_mode = True

    daemon = Daemon(dev_mode)
    exit(0)
