# SX1276 driver for MicroPython
# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import machine, ssd1306, sx1276, time, urandom, struct, gc
from machine import Pin, SoftI2C, ADC
import uasyncio as asyncio
from wan_config import *
import bluetooth
from bt import BLEUART

MessageTypeData = 0
MessageTypeAck = 1
MessageTypeHello = 2
MessageTypeBulkStart = 3
MessageTypeBulkData = 4
MessageTypeBulkEND = 5
MessageTypeBulkReply = 6

MessageFlagsRelayed = 1<<0
MessageFlagsPleaseRelay = 1<<1

LoRaPresets = {
    'superfast': {
        'lora_sp': 7,
        'lora_cr': 5,
        'lora_bw': 500000
    },
    'veryfast': {
        'lora_sp': 8,
        'lora_cr': 6,
        'lora_bw': 250000
    },
    'fast': {
        'lora_sp': 9,
        'lora_cr': 8,
        'lora_bw': 250000
    },
    'mid': {
        'lora_sp': 10,
        'lora_cr': 8,
        'lora_bw': 250000
    },
    'far': {
        'lora_sp': 11,
        'lora_cr': 8,
        'lora_bw': 125000
    },
    'veryfar': {
        'lora_sp': 12,
        'lora_cr': 8,
        'lora_bw': 125000
    },
    'superfar': {
        'lora_sp': 12,
        'lora_cr': 8,
        'lora_bw': 62500
    }
}

# This class implements an IRC-alike view for the ssd1306 display.
# it is possible to push new lines of text, and only the latest N will
# be shown, handling also text wrapping if a line is longer than
# the screen width.
class Scroller:
    def __init__(self, display):
        self.display = display # ssd1306 actual driver
        self.lines = []
        self.xres = 128
        self.yres = 64
        # The framebuffer of MicroPython only supports 8x8 fonts so far, so:
        self.cols = int(self.xres/8)
        self.rows = int(self.yres/8)

    # Return the number of rows needed to display the current self.lines
    # This number may be > self.rows.
    def rows_needed(self):
        needed = 0
        for l in self.lines:
            needed += int((len(l)+(self.cols-1))/self.cols)
        return needed

    # Update the screen content.
    def refresh(self):
        self.display.fill(0)
        # We need to draw the lines backward starting from the last
        # row and going backward. This makes handling line wraps simpler,
        # as we consume from the end of the last line and so forth.
        y = (min(self.rows,self.rows_needed())-1) * 8
        lines = self.lines[:]
        while y >= 0:
            if len(lines[-1]) == 0:
                lines.pop(-1)
                if len(lines) == 0: return # Should not happen
            to_consume = len(lines[-1]) % self.cols
            if to_consume == 0: to_consume = self.cols
            rowchars = lines[-1][-to_consume:] # Part to display from the end
            lines[-1]=lines[-1][:-to_consume]  # Remaining part.
            self.display.text(rowchars, 0, y, 1)
            y -= 8
        self.display.show()

    # Add a new line, without refreshing the display.
    def print(self,msg):
        self.lines.append(msg)
        self.lines = self.lines[-self.rows:]

# The message object represents a FreakWAN message, and is also responsible
# of the decoding and encoding of the messages to be sent to the "wire".
class Message:
    def __init__(self, nick="", text="", uid=False, ttl=15, mtype=MessageTypeData, sender=False, flags=0, rssi=0, ack_type=0, seen=0):
        self.ctime = time.ticks_ms() # To evict old messages

        # send_time is only useful for sending, to introduce a random delay.
        self.send_time = self.ctime

        # Number of times to transmit this message. Each time the message
        # is transmitted, this value is reduced by one. When it reaches
        # zero, the message is removed from the send queue.
        self.num_tx = 1
        self.acks = 0       # Number of received ACKs for this message
        self.type = mtype
        self.flags = flags
        self.nick = nick
        self.text = text
        self.uid = uid if uid != False else self.gen_uid()
        self.sender = sender if sender != False else self.get_this_sender()
        self.ttl = ttl              # Only DATA
        self.ack_type = ack_type    # Only ACK
        self.seen = seen            # Only HELLO
        self.rssi = rssi

    # Generate a 32 bit unique message ID.
    def gen_uid(self):
        return urandom.getrandbits(32)

    # Get the sender address for this device. We just take 6 bytes
    # of the device unique ID.
    def get_this_sender(self):
        return machine.unique_id()[-6:]

    # Return the sender as a printable hex string.
    def sender_to_str(self):
        if self.sender:
            s = self.sender
            return "%02x%02x%02x%02x%02x%02x" % (s[0],s[1],s[2],s[3],s[4],s[5])
        else:
            return "ffffffffffff"

    # Turn the message into its binary representation.
    def encode(self):
        if self.type == MessageTypeData:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ttl)+self.sender+self.nick+":"+self.text
        elif self.type == MessageTypeAck:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ack_type)+self.sender
        elif self.type == MessageTypeHello:
            return struct.pack("<BB6sB",self.type,self.flags,self.sender,self.seen)+self.nick+":"+self.text

    # Fill the message with the data found in the binary representation
    # provided in 'msg'.
    def decode(self,msg):
        try:
            mtype = struct.unpack("<B",msg)[0]
            if mtype == MessageTypeData:
                self.type,self.flags,self.uid,self.ttl,self.sender = struct.unpack("<BBLB6s",msg)
                self.nick,self.text = msg[13:].decode("utf-8").split(":")
                return True
            elif mtype == MessageTypeAck:
                self.type,self.flags,self.uid,self.ack_type,self.sender = struct.unpack("<BBLB6s",msg)
                return True
            elif mtype == MessageTypeHello:
                self.type,self.flags,self.sender,self.seen = struct.unpack("<BB6sB",msg)
                self.nick,self.text = msg[9:].decode("utf-8").split(":")
                return True
            else:
                return False
        except Exception as e:
            print("msg decode error "+str(e))
            return False

    # Create a message object from the binary representation of a message.
    def from_encoded(encoded):
        m = Message()
        if m.decode(encoded):
            return m
        else:
            return False

# This class is used by the FreakWAN class in order to execute
# commands received from the user via Bluetooth. Actually here we
# receive just command strings and reply with the passed send_reply
# method, so this can be used to execute the same commands arriving
# by other means.
class BTCommandsController:
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
                                       62500,62500,125000,250000,500000]
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
                send_reply("Commands: !automsg !sp !cr !bw !freq !preset !ls")
            elif argv[0] == "!bat" and argc == 1:
                volts = fw.get_battery_microvolts()/1000000
                send_reply("battery volts: "+str(volts))
            elif argv[0] == "!ls" and argc == 1:
                list_item = 0
                for node_id in fw.neighbors:
                    m = fw.neighbors[node_id]
                    age = time.ticks_diff(time.ticks_ms(),m.ctime) / 1000
                    list_item += 1
                    send_reply(str(list_item)+". "+
                                m.sender_to_str()+
                                " ("+m.nick+") "+
                                ("%.1f" % age) + " sec ago. "+
                                "Can see "+str(m.seen)+" nodes.")
                if len(fw.neighbors) == 0:
                    send_reply("Nobody around, apparently...")
            else:
                send_reply("Unknown command or num of args: "+argv[0])
        else:
            msg = Message(nick=fw.config['nick'], text=cmd)
            fw.send_asynchronously(msg,max_delay=0,num_tx=3,relay=True)
            fw.scroller.print("you> "+msg.text)
            fw.scroller.refresh()

# The application itself, including all the WAN routing logic.
class FreakWAN:
    def __init__(self):

        # Initialize data structures...
        self.config = {
            'nick': self.device_hw_nick(),
            'automsg': True,
            'relay_num_tx': 3,
            'relay_max_delay': 10000,
            'relay_rssi_limit': -60,
            'status': "Hi there!",
        }
        self.config.update(UserConfig.config)

        LYLIGO_216_pinconfig = {
            'miso': 19,
            'mosi': 27,
            'clock': 5,
            'chipselect': 18,
            'reset': 23,
            'dio0': 26
        }

        # Init display
        i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
        self.display = ssd1306.SSD1306_I2C(128, 64, i2c)
        self.display.poweron()
        self.display.text('Starting...', 0, 0, 1)
        self.display.show()
        self.scroller = Scroller(self.display)

        # Init LoRa chip
        self.lora = sx1276.SX1276(LYLIGO_216_pinconfig,self.process_message)
        self.lora_reset_and_configure()

        # Init BLE chip
        ble = bluetooth.BLE()
        self.uart = BLEUART(ble, name="FreakWAN_%s" % self.config['nick'])
        self.cmdctrl = BTCommandsController()

        # Init battery voltage pin
        self.battery_adc = ADC(Pin(35))
        # Voltage is divided by 2 befor reaching PID 32. Since normally
        # a 3.7V battery is used, to sample it we need the full 3.3
        # volts range.
        self.battery_adc.atten(ADC.ATTN_11DB)

        # Queue of messages we should send ASAP. We append stuff here, so they
        # should be sent in reverse order, from index 0.
        self.send_queue = []
        self.send_queue_max = 100 # Don't accumulate too many messages

        # The 'processed' dictionary contains messages IDs of messages already
        # received/processed. We save the ID and the associated message
        # in case we are the originators (in order to collect acks). The
        # message has also a timestamp, this way we can evict old messages
        # from this list, to avoid a memory usage explosion.
        #
        # Note that we have two processed dict: a and b. Together, they
        # hold all the recently processed messages, however we need two
        # since we slowly analyze all the elements of dict a and put them
        # into dict b only if it is not expired (otherwise we would retain
        # all the messages seen, for a long time, running out of memory).
        #
        # Follow these rules:
        # 1. To see if a message was processed, check both dicts.
        # 2. When adding new messages, always add in 'a'.
        self.processed_a = {}
        self.processed_b = {}

        # The 'neighbors' dictionary contains the IDs of devices we seen
        # (only updated when receiving Hello messages), and the corresponding
        # unix time of the last time we received a Hello message from
        # them.
        self.neighbors = {}

        # Start receiving. This will just install the IRQ
        # handler, without blocking the program.
        self.lora.receive()

    # Reset the chip and configure with the required paramenters.
    # Used during initialization and also in the TX watchdog if
    # the radio is stuck transmitting the current frame for some
    # reason.
    def lora_reset_and_configure(self):
        was_receiving = self.lora.receiving
        self.lora.begin()
        self.lora.configure(self.config['lora_fr'],self.config['lora_bw'],self.config['lora_cr'],self.config['lora_sp'])
        if was_receiving: self.lora.receive()

    # Return the battery voltage. The battery voltage is divided
    # by two and fed into the ADC at pin 35.
    def get_battery_microvolts(self):
        return self.battery_adc.read_uv() * 2

    # Return a human readable nickname for the device, composed
    # using the device unique ID.
    def device_hw_nick(self):
        uid = list(machine.unique_id())
        nick = ""
        consonants = "kvprmnzflst"
        vowels = "aeiou"
        for x,y in zip(uid[0::2],uid[1::2]):
            nick += consonants[x%len(consonants)]
            nick += vowels [y%len(vowels)]
        return nick

    # Put a packet in the send queue. Will be delivered ASAP.
    # The delay is in milliseconds, and is selected randomly
    # between 0 and the specified amount.
    def send_asynchronously(self,m,max_delay=2000,num_tx=1,relay=False):
        if len(self.send_queue) >= self.send_queue_max: return False
        m.send_time = time.ticks_add(time.ticks_ms(),urandom.randint(0,max_delay))
        m.num_tx = num_tx
        if relay: m.flags |= MessageFlagsPleaseRelay
        self.send_queue.append(m)

        # Since we generated this message, if applicable by type we
        # add it to the list of messages we know about. This way we will
        # be able to resolve ACKs received, avoiding sending relays for
        # messages we originated and so forth.
        self.mark_as_processed(m)
        return True

    # Send packets waiting in the send queue. This function, right now,
    # will just send every packet in the queue. But later it should
    # implement percentage of channel usage to be able to send only
    # a given percentage of the time.
    def send_messages_in_queue(self):
        send_later = [] # List of messages we can't send, yet.
        while len(self.send_queue):
            m = self.send_queue.pop(0)
            if (time.ticks_diff(time.ticks_ms(),m.send_time) > 0):

                # If the radio is busy sending. We wait here.
                # However it was sperimentally observed that sometimes
                # it can get stuck (maybe because of some race condition
                # in this code?). So if a given amount of time has elapsed
                # without progresses, we reset the radio and return.
                wait_ms_counter = 0
                wait_ms_counter_max = 5000 # 5 seconds
                while(self.lora.tx_in_progress):
                    wait_ms_counter += 1
                    if wait_ms_counter == 5000:
                        print("WARNING: TX watchdog radio reset")
                        self.lora_reset_and_configure()
                        self.lora.receive()
                        return
                    time.sleep_ms(1)
                self.lora.send(m.encode())
                time.sleep_ms(1)

                # This message may be scheduled for multiple
                # retransmissions. In this case decrement the count
                # of transmissions and queue it back again.
                if m.num_tx > 1:
                    m.num_tx -= 1
                    next_tx_min_delay = 3000
                    next_tx_max_delay = 8000
                    m.send_time = time.ticks_add(time.ticks_ms(),urandom.randint(next_tx_min_delay,next_tx_max_delay))
                    send_later.append(m)
            else:
                send_later.append(m)
        self.send_queue = send_later

    # Called upon reception of some message. It triggers sending an ACK
    # if certain conditions are met. This method does not check the
    # message type: it is assumed that the method is called only for
    # message type where this makes sense.
    def send_ack_if_needed(self,m):
        if m.type != MessageTypeData: return     # Acknowledge only data.
        if m.flags & MessageFlagsRelayed: return # Don't acknowledge relayed.
        ack = Message(mtype=MessageTypeAck,uid=m.uid,ack_type=m.type)
        self.send_asynchronously(ack)
        print("[>> net] Sending ACK about "+("%08x"%m.uid))

    # Called for data messages we see for the first time. If the
    # originator asked for relay, we schedule a retransmission of
    # this packet, so that other peers can receive it.
    def relay_if_needed(self,m):
        if m.type != MessageTypeData: return     # Relay only data messages.
        if not m.flags & MessageFlagsPleaseRelay: return # No relay needed.
        # We also avoid relaying messages that are too strong: if the
        # originator of this message (or some other device that relayed it
        # already) is too near to us, it is unlikely that we will help
        # by transmitting it again. Actually we could just waste channel time.
        if m.rssi > self.config['relay_rssi_limit']: return
        if m.ttl <= 1: return # Packet reached relay limit.

        # Ok, we can relay it. Let's update the message.
        m.ttl -= 1
        m.flags |= MessageFlagsRelayed  # This is a relay. No ACKs, please.
        self.send_asynchronously(m,num_tx=self.config['relay_num_tx'],max_delay=self.config['relay_max_delay'])
        print("[>> net] Relaying "+("%08x"%m.uid)+" from "+m.nick)

    # Return the message if it was already marked as processed, otherwise
    # None is returned.
    def get_processed_message(self,uid):
        m = self.processed_a.get(uid)
        if m: return m
        m = self.processed_b.get(uid)
        if m: return m
        return None

    # Mark a message received as processed. Not useful for all the kind
    # of messages. Only the ones that may be resent by the network
    # relays or retransmission mechanism, and we want to handle only
    # once. If the message was already processed, and thus is not added
    # again to the list of messages, True is returned, and the caller knows
    # it can discard the message. Otherwise we return False and add it
    # if needed.
    def mark_as_processed(self,m):
        if m.type == MessageTypeData:
            if self.get_processed_message(m.uid):
                return True
            else:
                self.processed_a[m.uid] = m
                return False
        else:
            return False

    # Remove old items from the processed cache
    def evict_processed_cache(self):
        count = 10 # Items to scan
        maxage = 60000 # Max cached message age in milliseconds
        while count and len(self.processed_a):
            count -= 1
            uid,m = self.processed_a.popitem()
            # Yet not expired? Move in the other dictionary, so we
            # know that the dictionary 'a' only has the items yet to
            # check for eviction.
            age = time.ticks_diff(time.ticks_ms(),m.ctime)
            if age <= maxage:
                self.processed_b[uid] = m
            else:
                print("[cache] Evicted: "+"%08x"%uid)

        # If we processed all the items of the 'a' dictionary, start again.
        if len(self.processed_a) == 0 and len(self.processed_b) != 0:
            self.processed_a = self.processed_b
            self.processed_b = {}

    # Called by the LoRa radio IRQ upon new packet reception.
    def process_message(self,lora_instance,packet,rssi):
        m = Message.from_encoded(packet)
        if m:
            m.rssi = rssi
            if m.type == MessageTypeData:
                # Already processed? Return ASAP.
                if self.mark_as_processed(m):
                    print("[<< net] Ignore duplicated message "+("%08x"%m.uid)+" <"+m.nick+"> "+m.text)
                    return

                # Report messsage to the user.
                user_msg = m.nick+"> "+m.text
                msg_info = "(rssi: "+str(m.rssi)+")"
                self.scroller.print(user_msg)
                self.uart.print(user_msg+" "+msg_info)
                print("*** "+user_msg+" "+msg_info)
                self.scroller.refresh()

                # Reply with ACK if needed.
                self.send_ack_if_needed(m)

                # Relay if needed.
                self.relay_if_needed(m)
            elif m.type == MessageTypeAck:
                about = self.get_processed_message(m.uid)
                if about != None:
                    about.acks += 1
                    print("[<< net] Got ACK about "+("%08x"%m.uid)+" by "+m.sender_to_str())
            elif m.type == MessageTypeHello:
                # Limit the number of neighbors to protect against OOM
                # due to bugs or too many nodes near us.
                max_neighbors = 32
                if not m.sender in self.neighbors:
                    msg = "[net] New node sensed: "+m.sender_to_str()
                    print(msg)
                    self.uart.print(msg)
                self.neighbors[m.sender] = m
                if len(self.neighbors) > max_neighbors:
                    self.neighbors.popitem()
            else:
                print("Unknown message type received: "+str(m.type))

    # Send HELLO messages from time to time. Evict nodes not refreshed
    # for some time from the neighbors list.
    async def send_hello_message(self):
        hello_msg_period_min = 60000        # 1 minute
        hello_msg_period_max = 120000       # 2 minutes
        hello_msg_max_age = 300000          # 5 minutes
        while True:
            # Evict not refreshed nodes from neighbors.
            new = {}
            while len(self.neighbors):
                sender,m = self.neighbors.popitem()
                age = time.ticks_diff(time.ticks_ms(),m.ctime)
                if age <= hello_msg_max_age:
                    new[sender] = m
                else:
                    print("[net] Flushing timedout neighbor: "+
                        m.sender_to_str()+" ("+m.nick+")")
            self.neighbors = new

            # Send HELLO.
            msg = Message(mtype=MessageTypeHello,
                        nick=self.config['nick'],
                        text=self.config['status'],
                        seen=len(self.neighbors))
            self.send_asynchronously(msg,max_delay=0)
            await asyncio.sleep(
                urandom.randint(hello_msg_period_min,hello_msg_period_max)
                /1000)

    # This function is used in order to send automatic messages.
    # For now, automatic messages are turned on by default, but they will
    # later be disabled and remain just a testing feature that is possible
    # to turn on when needed. Very useful for range testing.
    async def send_periodic_message(self):
        counter = 0
        while True:
            if self.config['automsg']:
                msg = Message(nick=self.config['nick'],
                            text="Hi "+str(counter))
                self.send_asynchronously(msg,max_delay=0,num_tx=3)
                self.scroller.print("you> "+msg.text)
                self.scroller.refresh()
                counter += 1
            await asyncio.sleep(urandom.randint(15000,20000)/1000) 

    # This shows some information about the process in the debug console.
    def show_status_log(self):
        sent = self.lora.msg_sent
        cached_total = len(self.processed_a)+len(self.processed_b)
        msg = "~"
        msg += " Sent:"+str(sent)
        msg += " SendQueue:"+str(len(self.send_queue))
        msg += " CacheLen:"+str(cached_total)
        msg += " FreeMem:"+str(gc.mem_free())
        print(msg)
    
    # This is the default callback that handle a message received from BLE.
    # It will:
    # 1. get the text from BLE message;
    # 2. create a our Message with the received text;
    # 3. send asynchronously the message and display it.
    def ble_receive_callback(self):
        cmd = self.uart.read().decode().strip()
        self.cmdctrl.exec_user_command(self,cmd,fw.uart.print)

    # This is the event loop of the application where we handle messages
    # received from BLE using the specified callback.
    # If the callback is not defined we use the class provided one:
    # self.ble_receive_callback.
    async def receive_from_ble(self):
        self.uart.set_callback(self.ble_receive_callback)
        # Our callback will be called by the IRQ only when
        # some BT event happens. We could return, without
        # staying here in this co-routine, but we'll likely soon
        # have certain periodic things to do related to the
        # BT connection. For now, just wait in a loop.
        while True: await asyncio.sleep(1)

    # This is the main event loop of the application, where we perform
    # periodic tasks, like sending messages in the queue. Other tasks
    # are handled by sub-tasks.
    async def run(self):
        asyncio.create_task(self.send_hello_message())
        asyncio.create_task(self.send_periodic_message())
        asyncio.create_task(self.receive_from_ble())
        tick = 0
        while True:
            if tick % 10 == 0: gc.collect()
            if tick % 50 == 0: self.show_status_log()
            self.send_messages_in_queue()
            self.evict_processed_cache()
            await asyncio.sleep(0.1)
            tick += 1

if __name__ == "__main__":
    fw = FreakWAN()
    asyncio.run(fw.run())
