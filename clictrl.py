# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import time

from message import *
from fci import ImageFCI

# This class is used by the FreakWAN class in order to execute
# commands received from the user via Bluetooth. Actually here we
# receive just command strings and reply with the passed send_reply
# method, so this can be used to execute the same commands arriving
# by other means.
class CommandsController:
    # 'command' is the command string to execute, while 'fw' is
    # our FreaWAN application class, used by the CommandsController
    # in order to do anything the application can do.
    #
    # 'send_reply' is the method to call in order to reply to the
    # user command.
    #
    # Commands starting with "!" are special commands to perform
    # special operations or change settings of the device.
    # Otherwise what we get from Bluetooth UART, we just send as
    # a message.
    def exec_user_command(self,fw,cmd,send_reply):
        if len(cmd) == 0:
            return
        print("Command from BLE received: ", cmd)
        if cmd[0] == '!':
            argv = cmd.split()
            argc = len(argv)
            if argv[0] == "!automsg":
                if argc == 2:
                    fw.config['automsg'] = argv[1] == '1' or argv[1] == 'on'
                send_reply("automsg set to "+str(fw.config['automsg']))
            elif argv[0] == "!preset" and argc == 2:
                if argv[1] in LoRaPresets:
                    fw.config.update(LoRaPresets[argv[1]])
                    send_reply("Setting bandwidth:"+str(fw.config['lora_bw'])+
                                " coding rate:"+str(fw.config['lora_cr'])+
                                " spreading:"+str(fw.config['lora_sp']))
                    fw.lora_reset_and_configure()
                else:
                    send_reply("Wrong preset name: "+argv[1]+". Try: "+
                        ", ".join(x for x in LoRaPresets))
            elif argv[0] == "!sp":
                if argc == 2:
                    try:
                        spreading = int(argv[1])
                    except:
                        spreading = 0
                    if spreading < 6 or spreading > 12:
                        send_reply("Invalid spreading. Use 6-12.")
                    else:
                        fw.config['lora_sp'] = spreading
                        fw.lora_reset_and_configure()
                send_reply("spreading set to "+str(fw.config['lora_sp']))
            elif argv[0] == "!cr":
                if argc == 2:
                    try:
                        cr = int(argv[1])
                    except:
                        cr = 0
                    if cr < 5 or cr > 8:
                        send_reply("Invalid coding rate. Use 5-8.")
                    else:
                        fw.config['lora_cr'] = cr 
                        fw.lora_reset_and_configure()
                send_reply("coding rate set to "+str(fw.config['lora_cr']))
            elif argv[0] == "!bw":
                if argc == 2:
                    valid_bw_values = [7800,10400,15600,20800,31250,41700,
                                       62500,125000,250000,500000]
                    try:
                        bw = int(argv[1])
                    except:
                        bw  = 0
                    if not bw in valid_bw_values:
                        send_reply("Invalid bandwidth. Use: "+
                                    ", ".join(str(x) for x in valid_bw_values))
                    else:
                        fw.config['lora_bw'] = bw
                        fw.lora_reset_and_configure()
                send_reply("bandwidth set to "+str(fw.config['lora_bw']))
            elif argv[0] == "!help":
                send_reply("Commands: !automsg !sp !cr !bw !freq !preset !ls !font !last")
            elif argv[0] == "!bat" and argc == 1:
                volts = fw.get_battery_microvolts()/1000000
                perc = fw.get_battery_perc()
                send_reply("battery %d%%, %.2f volts" % (perc,volts))
            elif argv[0] == "!font" and argc == 2:
                if argv[1] not in ["big","small"]:
                    send_reply("Font name can be: big, small")
                else:
                    fw.scroller.select_font(argv[1])
                    fw.refresh_view()
            elif argv[0] == "!ls" and argc == 1:
                list_item = 0
                for node_id in fw.neighbors:
                    m = fw.neighbors[node_id]
                    age = time.ticks_diff(time.ticks_ms(),m.ctime) / 1000
                    list_item += 1
                    send_reply(str(list_item)+". "+
                                m.sender_to_str()+
                                " ("+m.nick+"> "+m.text+") "+
                                ("%.1f" % age) + " sec ago "+
                                (" with RSSI:%d " % (m.rssi))+
                                "It can see "+str(m.seen)+" nodes.")
                if len(fw.neighbors) == 0:
                    send_reply("Nobody around, apparently...")
            elif argv[0] == "!last" and (argc == 1 or argc == 2):
                count = int(argv[1]) if argc == 2 else 10
                if count < 1:
                    send_reply("messages count must be positive")
                else:
                    msglist = fw.history.get_records(count-1,count)
                    for enc in msglist:
                        m = Message.from_encoded(enc)
                        if m.flags & MessageFlagsMedia:
                            send_reply(m.nick+"> [%d bytes of media]"%len(m.media_data))
                        else:
                            send_reply(m.nick+"> "+m.text)
            elif argv[0] == "!image" and argc == 2:
                try:
                    img = ImageFCI(filename=argv[1])
                    if len(img.encoded) > 200:
                        send_reply("Image over 200 bytes. Too large to send before fragmentation gets implemented")
                    else:
                        msg = Message(flags=MessageFlagsMedia,nick=fw.config['nick'],media_type=MessageMediaTypeImageFCI,media_data=img.encoded)
                        fw.send_asynchronously(msg,max_delay=0,num_tx=1,relay=True)
                        fw.scroller.print("you> image:")
                        fw.scroller.print(img)
                        fw.refresh_view()
                except Exception as e:
                    send_reply("Error loading the image: "+str(e))
            else:
                send_reply("Unknown command or num of args: "+argv[0])
        else:
            msg = Message(nick=fw.config['nick'], text=cmd)
            fw.send_asynchronously(msg,max_delay=0,num_tx=3,relay=True)
            fw.scroller.print("you> "+msg.text)
            fw.refresh_view()


