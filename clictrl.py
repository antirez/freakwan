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
    def __init__(self,fw):
        self.default_key = None
        self.fw = fw # Reference to the FreakWAN app object

    # Split command arguments, trying to consider "strings with quotes
    # and spaces" as a single one. So the user can type: !cmd "argu ment".
    def split_arguments(self,cmd):
        sp = cmd.split()
        argv = []
        in_quotes = False
        for a in sp:
            if in_quotes:
                if len(a) and a[-1] == '"':
                    a = a[:-1]
                    in_quotes = False
                argv[-1] += " "+a
            else:
                if len(a) and a[0] == '"' and a[-1] == '"':
                    a = a[1:-1]
                elif len(a) and a[0] == '"':
                    a = a[1:]
                    in_quotes = True
                argv.append(a)
        return argv

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
    def exec_user_command(self,cmd,send_reply):
        cmd = str(cmd).strip()
        if len(cmd) == 0: return

        print("Command from BLE/IRC received: %s" % cmd)
        if cmd[0] == '!':
            # Command call.
            argv = self.split_arguments(cmd[1:])
            argc = len(argv)
            method_name = 'cmd_'+argv[0]
            if not hasattr(self.__class__,method_name):
                send_reply("Unknown command: "+argv[0])
                return

            # Call the method logically bound to the command name.
            method = getattr(self.__class__, method_name)
            if method(self,argv,argc,send_reply) == False:
                send_reply("Wrong number of arguments for: "+argv[0])
        elif cmd[0] == '#':
            # Encrypted message.
            idx = cmd.find(' ')
            key_name = cmd[1:idx]
            text = cmd[idx+1:]
            if not self.fw.keychain.has_key(key_name):
                send_reply("No key named '"+str(key_name)+"' in keychain.")
            else:
                msg = Message(nick=self.fw.config['nick'], text=text, key_name=key_name)
                self.fw.send_asynchronously(msg,max_delay=0,num_tx=3,relay=True)
                self.fw.scroller.print("#"+key_name+" you> "+msg.text)
                self.fw.refresh_view()
        else:
            # Plain text message.
            key_name = self.default_key
            group = "" if not key_name else "#"+key_name+" "
            msg = Message(nick=self.fw.config['nick'], text=cmd, key_name=key_name)
            self.fw.send_asynchronously(msg,max_delay=0,num_tx=3,relay=True)
            self.fw.scroller.print(group+"you> "+msg.text)
            self.fw.refresh_view()

    def cmd_automsg(self,argv,argc,send_reply):
        if argc > 2: return False
        if argc == 2:
            self.fw.config['automsg'] = argv[1] == '1' or argv[1] == 'on'
        send_reply("automsg set to "+str(self.fw.config['automsg']))
        return True

    def cmd_prom(self,argv,argc,send_reply):
        if argc > 2: return False
        if argc == 2:
            self.fw.promiscuous = argv[1] == '1' or argv[1] == 'on'
        send_reply("promiscuous mode set to "+str(self.fw.promiscuous))
        return True

    def cmd_preset(self,argv,argc,send_reply):
        if argc != 2: return False
        if argv[1] in LoRaPresets:
            self.fw.config.update(LoRaPresets[argv[1]])
            send_reply("Setting bandwidth:"+str(self.fw.config['lora_bw'])+
                        " coding rate:"+str(self.fw.config['lora_cr'])+
                        " spreading:"+str(self.fw.config['lora_sp']))
            self.fw.lora_reset_and_configure()
        else:
            send_reply("Wrong preset name: "+argv[1]+". Try: "+
                ", ".join(x for x in LoRaPresets))
        return True

    def cmd_pw(self,argv,argc,send_reply):
        if argc > 2: return False
        if argc == 2:
            try:
                txpower = int(argv[1])
            except:
                txpower = 0
            if txpower < 2 or txpower > 20:
                send_reply("Invalid tx power (dbm). Use 2-20.")
            else:
                self.fw.config['lora_pw'] = txpower
                self.fw.lora_reset_and_configure()
        send_reply("TX power set to "+str(self.fw.config['lora_pw']))
        return True

    def cmd_sp(self,argv,argc,send_reply):
        if argc > 2: return False
        if argc == 2:
            try:
                spreading = int(argv[1])
            except:
                spreading = 0
            if spreading < 6 or spreading > 12:
                send_reply("Invalid spreading. Use 6-12.")
            else:
                self.fw.config['lora_sp'] = spreading
                self.fw.lora_reset_and_configure()
        send_reply("spreading set to "+str(self.fw.config['lora_sp']))
        return True

    def cmd_cr(self,argv,argc,send_reply):
        if argc > 2: return False
        if argc == 2:
            try:
                cr = int(argv[1])
            except:
                cr = 0
            if cr < 5 or cr > 8:
                send_reply("Invalid coding rate. Use 5-8.")
            else:
                self.fw.config['lora_cr'] = cr 
                self.fw.lora_reset_and_configure()
        send_reply("coding rate set to "+str(self.fw.config['lora_cr']))
        return True

    def cmd_bw(self,argv,argc,send_reply):
        if argc > 2: return False
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
                self.fw.config['lora_bw'] = bw
                self.fw.lora_reset_and_configure()
        send_reply("bandwidth set to "+str(self.fw.config['lora_bw']))
        return True

    def cmd_help(self,argv,argc,send_reply):
        if argc != 1: return False
        helpstr = "Commands: "
        for x in dir(self):
            if x.find("cmd_") != 0: continue
            helpstr += x.replace("cmd_","!")+" "
        send_reply(helpstr)
        return True

    def cmd_config(self,argv,argc,send_reply):
        if argc != 2: return False
        if argv[1] == "save":
            self.fw.save_settings()
            send_reply("Config settings saved")
        elif argv[1] == "reset":
            self.fw.reset_settings()
            send_reply("Config reset done. Restart the device to apply.")
        else:
            send_reply("!config valid subcommands: save, reset")

    def cmd_bat(self,argv,argc,send_reply):
        if argc != 1: return False
        volts = self.fw.get_battery_microvolts()/1000000
        perc = self.fw.get_battery_perc()
        send_reply("battery %d%%, %.2f volts" % (perc,volts))
        return True

    def cmd_font(self,argv,argc,send_reply):
        if argc != 2: return False
        if argv[1] not in ["big","small"]:
            send_reply("Font name can be: big, small.")
        else:
            self.fw.scroller.select_font(argv[1])
            self.fw.refresh_view()
        return True

    def cmd_ls(self,argv,argc,send_reply):
        if argc != 1: return False
        list_item = 0
        for node_id in self.fw.neighbors:
            m = self.fw.neighbors[node_id]
            age = time.ticks_diff(time.ticks_ms(),m.ctime) / 1000
            list_item += 1
            send_reply(str(list_item)+". "+
                        m.sender_to_str()+
                        " ("+m.nick+"> "+m.text+") "+
                        ("%.1f" % age) + " sec ago "+
                        (" with RSSI:%d " % (m.rssi))+
                        "It can see "+str(m.seen)+" nodes.")
        if len(self.fw.neighbors) == 0:
            send_reply("Nobody around, apparently...")
        return True

    def cmd_last(self,argv,argc,send_reply):
        if argc > 2: return False
        count = int(argv[1]) if argc == 2 else 10
        if count < 1:
            send_reply("Messages count must be positive.")
        else:
            msglist = self.fw.history.get_records(count-1,count)
            for enc in msglist:
                m = Message.from_encoded(enc,self.fw.keychain)
                if m.flags & MessageFlagsMedia:
                    send_reply(m.nick+"> [%d bytes of media]"%len(m.media_data))
                else:
                    send_reply(m.nick+"> "+m.text)
        return True

    def cmd_addkey(self,argv,argc,send_reply):
        if argc != 3: return False
        self.fw.keychain.add_key(argv[1],argv[2])
        send_reply("Key added to keychain.")
        return True

    def cmd_delkey(self,argv,argc,send_reply):
        if argc != 2: return False
        if self.fw.keychain.has_key(argv[1]):
            self.fw.keychain.del_key(argv[1])
            send_reply("Key removed from keychain")
        else:
            send_reply("No such key: "+argv[1])
        return True

    def cmd_usekey(self,argv,argc,send_reply):
        if argc != 2: return False
        if self.fw.keychain.has_key(argv[1]):
            self.default_key = argv[1]
            send_reply("Key set.")
        else:
            send_reply("No such key: "+argv[1])
        return True

    def cmd_nokey(self,argv,argc,send_reply):
        if argc != 1: return False
        self.default_key = None
        send_reply("Key unset. New messages will be sent unencrypted.")
        return True

    def cmd_keys(self,argv,argc,send_reply):
        if argc != 1: return False
        send_reply(", ".join(self.fw.keychain.list_keys()))
        return True

    def cmd_wifi(self,argv,argc,send_reply):
        if argc == 1:
            send_reply("Configured wifi networks:")
            for ssid in self.fw.config['wifi']:
                send_reply(ssid)
        elif argc == 4 and argv[1] == 'add':
            self.fw.config['wifi'][argv[2]] = argv[3]
            send_reply("WiFi network added. Use '!config save' to see it after a device restart.")
        elif argc == 3 and (argv[1] == 'del' or argv[1] == 'rm'):
            del(self.fw.config['wifi'][argv[2]])
            send_reply("Wifi network removed. Use '!config save' to permanently remove it.")
        elif argc == 2 and argv[1] == 'start':
            defnet = self.fw.config.get('wifi_default_network')
            defpass = self.fw.config['wifi'].get(defnet)
            if not defnet or not defpass:
                send_reply("No default WiFi network set. Use !wifi start <ssid>.")
            else:
                self.fw.wifi.connect(defnet,defpass)
        elif argc == 3 and argv[1] == 'start':
            netname = argv[2]
            netpass = self.fw.config['wifi'].get(netname)
            if not netpass:
                send_reply("No WiFi network named %s" % netname)
            else:
                self.fw.start_wifi(netname,netpass)
                send_reply("Connecting to %s" % netname)
        elif argc == 2 and argv[1] == 'stop':
            self.fw.stop_wifi()
            send_reply("WiFi turned off")
        else:
            send_reply("Usage: wifi                   -- list wifi networks")
            send_reply("Usage: wifi add <net> <pass>  -- Add wifi network")
            send_reply("Usage: wifi del <net>         -- Remove wifi network")
            send_reply("Usage: wifi start             -- Connect to default network")
            send_reply("Usage: wifi start <net>       -- Connect to specified network")
            send_reply("Usage: wifi stop              -- Disconnect wifi")

    def cmd_image(self,argv,argc,send_reply):
        if argc != 2: return False
        try:
            img = ImageFCI(filename=argv[1])
            if len(img.encoded) > 200:
                send_reply("Image over 200 bytes. Too large to send before fragmentation gets implemented.")
            else:
                msg = Message(flags=MessageFlagsMedia,nick=self.fw.config['nick'],media_type=MessageMediaTypeImageFCI,media_data=img.encoded)
                self.fw.send_asynchronously(msg,max_delay=0,num_tx=1,relay=True)
                self.fw.scroller.print("you> image:")
                self.fw.scroller.print(img)
                self.fw.refresh_view()
        except Exception as e:
            send_reply("Error loading the image: "+str(e))
        return True
