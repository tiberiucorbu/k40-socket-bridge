#!/usr/bin/env python
'''
This script comunicated with the K40 Laser Cutter.

Copyright (C) 2017-2019 Scorch www.scorchworks.com

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
import logging
import os

import k40usb
from time import time

from egv import egv
from windowsinhibitor import WindowsInhibitor


##############################################################################

class K40_CLASS:
    def __init__(self):
        self.connection = k40usb.connection.K40UsbConnectionManager()
        self.n_timeouts = 10
        self.read_addr = 0x82  # Read address
        self.read_length = 168

        #### RESPONSE CODES ####
        self.OK = 206
        self.BUFFER_FULL = 238
        self.CRC_ERROR = 207
        self.TASK_COMPLETE = 236
        self.UNKNOWN_2 = 239  # after failed initialization followed by succesful initialization
        #######################
        self.hello = [160]
        self.unlock = [166, 0, 73, 83, 50, 80, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70,
                       70, 70, 70, 70, 70, 70, 70, 70, 166, 15]
        self.home = [166, 0, 73, 80, 80, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70,
                     70, 70, 70, 70, 70, 70, 70, 166, 228]
        self.estop = [166, 0, 73, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70,
                      70, 70, 70, 70, 70, 70, 70, 70, 166, 130]

    def say_hello(self):
        cnt = 0
        status_timeouts = self.n_timeouts
        while cnt < status_timeouts:
            cnt = cnt + 1
            try:
                self.send_packet(self.hello)
                break
            except:
                pass
        if cnt >= status_timeouts:
            return None

        response = None
        read_cnt = 0
        while response == None and read_cnt < status_timeouts:
            try:
                response = self.connection.read()
            except:
                response = None
                read_cnt = read_cnt + 1

        DEBUG = False
        if response != None:
            if DEBUG:
                if int(response[0]) != 255:
                    print("0: ", response[0])
                elif int(response[1]) != 206:
                    print("1: ", response[1])
                elif int(response[2]) != 111:
                    print("2: ", response[2])
                elif int(response[3]) != 8:
                    print("3: ", response[3])
                elif int(response[4]) != 19:  # Get a 3 if you try to initialize when already initialized
                    print("4: ", response[4])
                elif int(response[5]) != 0:
                    print("5: ", response[5])
                else:
                    print(".", )
            logging.info('got response, %s', response)
            if response[1] == self.OK or \
                    response[1] == self.BUFFER_FULL or \
                    response[1] == self.CRC_ERROR or \
                    response[1] == self.TASK_COMPLETE or \
                    response[1] == self.UNKNOWN_2:
                return response[1]
            else:
                return 9999
        else:
            return None

    def unlock_rail(self):
        self.send_packet(self.unlock)

    def e_stop(self):
        self.send_packet(self.estop)

    def home_position(self):
        self.send_packet(self.home)

    def reset_usb(self):
        self.connection.reset()

    def release_usb(self):
        self.connection.release_usb()

    #######################################################################
    #  The one wire CRC algorithm is derived from the OneWire.cpp Library
    #  The latest version of this library may be found at:
    #  http://www.pjrc.com/teensy/td_libs_OneWire.html
    #######################################################################
    def OneWireCRC(self, line):
        crc = 0
        for i in range(len(line)):
            inbyte = line[i]
            for j in range(8):
                mix = (crc ^ inbyte) & 0x01
                crc >>= 1
                if (mix):
                    crc ^= 0x8C
                inbyte >>= 1
        return crc

    #######################################################################
    def none_function(self, dummy=None, bgcolor=None):
        # Don't delete this function (used in send_data)
        return False

    def send_data(self, data, update_gui=None, stop_calc=None, passes=1, preprocess_crc=True, wait_for_laser=False):
        if stop_calc == None:
            stop_calc = []
            stop_calc.append(0)
        if update_gui == None:
            update_gui = self.none_function

        NoSleep = WindowsInhibitor()
        NoSleep.inhibit()

        blank = [166, 0, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70,
                 70, 70, 70, 70, 70, 70, 166, 0]
        packets = []
        packet = blank[:]
        cnt = 2
        len_data = len(data)
        for j in range(passes):
            if j == 0:
                istart = 0
            else:
                istart = 1
                data[-4]
            if passes > 1:
                if j == passes - 1:
                    data[-4] = ord("F")
                else:
                    data[-4] = ord("@")
            timestamp = 0
            for i in range(istart, len_data):
                if cnt > 31:
                    packet[-1] = self.OneWireCRC(packet[1:len(packet) - 2])
                    stamp = int(3 * time())  # update every 1/3 of a second
                    if not preprocess_crc:
                        self.send_packet_w_error_checking(packet, update_gui, stop_calc)
                        if (stamp != timestamp):
                            timestamp = stamp  # interlock
                            update_gui("Sending Data to Laser = %.1f%%" % (100.0 * float(i) / float(len_data)))
                    else:
                        packets.append(packet)
                        if (stamp != timestamp):
                            timestamp = stamp  # interlock
                            update_gui("Calculating CRC data and Generate Packets: %.1f%%" % (
                                    100.0 * float(i) / float(len_data)))
                    packet = blank[:]
                    cnt = 2

                    if stop_calc[0] == True:
                        NoSleep.uninhibit()
                        raise Exception("Action Stopped by User.")
                packet[cnt] = data[i]
                cnt = cnt + 1
        packet[-1] = self.OneWireCRC(packet[1:len(packet) - 2])
        if not preprocess_crc:
            self.send_packet_w_error_checking(packet, update_gui, stop_calc)
        else:
            packets.append(packet)
        packet_cnt = 0

        for line in packets:
            update_gui()
            self.send_packet_w_error_checking(line, update_gui, stop_calc)
            packet_cnt = packet_cnt + 1.0
            update_gui("Sending Data to Laser = %.1f%%" % (100.0 * packet_cnt / len(packets)))
        ##############################################################
        if wait_for_laser:
            self.wait_for_laser_to_finish(update_gui, stop_calc)
        NoSleep.uninhibit()

    def send_packet_w_error_checking(self, line, update_gui=None, stop_calc=None):
        timeout_cnt = 1
        crc_cnt = 1
        while True:
            if stop_calc[0]:
                msg = "Action Stopped by User."
                update_gui(msg, bgcolor='red')
                raise Exception(msg)
            try:
                self.send_packet(line)
            except:
                timeout_cnt = timeout_cnt + 1
                if timeout_cnt < self.n_timeouts:
                    msg = "USB Timeout #%d" % (timeout_cnt)
                    update_gui(msg, bgcolor='yellow')
                else:
                    msg = "The laser cutter is not responding (%d attempts). Press stop to stop trying!" % (timeout_cnt)
                    gui_active = update_gui(msg, bgcolor='red')
                    if not gui_active:
                        msg = "The laser cutter is not responding after %d attempts." % (timeout_cnt)
                        raise Exception(msg)
                continue
            ######################################
            response = self.say_hello()

            if response == self.BUFFER_FULL:
                while response == self.BUFFER_FULL:
                    response = self.say_hello()
                break  # break and move on to next packet

            elif response == self.CRC_ERROR:
                crc_cnt = crc_cnt + 1
                if crc_cnt < self.n_timeouts:
                    msg = "Data transmission (CRC) error #%d" % (crc_cnt)
                    update_gui(msg, bgcolor='yellow')
                else:
                    msg = "There are many data transmission errors (%d). Press stop to stop trying!" % (crc_cnt)
                    gui_active = update_gui(msg, bgcolor='red')
                    if not gui_active:
                        msg = "There are many data transmission errors (%d)." % (crc_cnt)
                        raise Exception(msg)
                continue
            elif response == None:
                # The controller board is not reporting status. but we will
                # assume things are going OK. until we cannot transmit to the controller.
                break  # break to move on to next packet

            else:  # assume: response == self.OK:
                break  # break to move on to next packet

    def wait_for_laser_to_finish(self, update_gui=None, stop_calc=None):
        FINISHED = False
        while not FINISHED:
            response = self.say_hello()
            if response == self.TASK_COMPLETE:
                FINISHED = True
                break
            elif response == None:
                msg = "The laser cutter stopped responding after sending data was complete."
                raise Exception(msg)
            else:  # assume: response == self.OK:
                msg = "Waiting for the laser to finish."
                update_gui(msg)
            if stop_calc[0]:
                msg = "Action Stopped by User."
                update_gui(msg, bgcolor='red')
                raise Exception(msg)

    def send_packet(self, line):
        self.connection.ensure_connection()
        self.connection.write(line[0], line[1:])

    def rapid_move(self, dxmils, dymils):
        if (dxmils != 0 or dymils != 0):
            data = []
            egv_inst = egv(target=lambda s: data.append(s))
            egv_inst.make_move_data(dxmils, dymils)
            self.send_data(data, wait_for_laser=False)

    def initialize_device(self):
        self.connection.connect()

    def hex2dec(self, hex_in):
        # format of "hex_in" is ["40","e7"]
        dec_out = []
        for a in hex_in:
            dec_out.append(int(a, 16))
        return dec_out


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    k40 = K40_CLASS()
    run_laser = False

    try:
        k40.initialize_device(verbose=True)
    # the following does not work for python 2.5
    except RuntimeError as e:  # (RuntimeError, TypeError, NameError, StandardError):
        print(e)
        print("Exiting...")
        os._exit(0)

        # k40.initialize_device()
    print(k40.say_hello())
    # print k40.reset_position()
    # print k40.unlock_rail()
    print("DONE")
