# Copyright (C) 2023-2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

Version="0.41"

SEND_MAX_DELAY = const(2000) # Random delay in milliseconds of asynchronous
                             # packet transmission. From 0 to the specified
                             # value. Choosen randomly.

# When a message will be transmitted multiple times (num_tx > 1), there
# following values, in milliseconds, will configure the minimum and maximum
# random delay between retransmissions. The max is not guaranteed: we could
# have many packets on the send queue, or the channel may be busy.
TX_AGAIN_MIN_DELAY = const(3000)
TX_AGAIN_MAX_DELAY = const(8000)

import machine, time, urandom, gc, sys, io
import select
from machine import Pin, SoftI2C, ADC, SPI
import uasyncio as asyncio
from wan_config import *
from device_config import *
from scroller import Scroller
from icons import StatusIcons
from splash import SplashScreen
from history import History
from message import *
from clictrl import CommandsController
from dutycycle import DutyCycle
from fci import ImageFCI
from keychain import Keychain
from views import *
from sensor import Sensor

### Bluetooth and networking may not be available.
try:
    import bluetooth
    from bt import BLEUART
except:
    pass

try:
    from networking import IRC, WiFiConnection
    from telegram import TelegramBot
except:
    pass

# The application itself, including all the WAN routing logic.
class FreakWAN:
    def __init__(self):

        # Initialize data structures...
        self.config = {
            'nick': self.device_hw_nick(),
            'automsg': True,
            'tx_led': False,
            'relay_num_tx': 3,
            'relay_max_delay': 10000,
            'relay_rssi_limit': -60,
            'status': "Hi there!",
            'sleep_battery_perc': 20,
            'wifi': {},
            'wifi_default_network': False,
            # When promiscuous mode is enabled, we can debug all the messages we
            # receive, as the message cache, to avoid re-processing messages,
            # is disabled.
            'prom': False,
            # When quiet mode is on, we avoid sending any non-data packet and
            # to relay other packets, in order to lower our channel usage.
            # So no ACKs, relayed packets, HELLO messages, no repeated messages.
            'quiet': False,
            'check_crc': True, # Discard packets with wrong CRC if False.
            'irc': {'enabled':False},
            'telegram': {'enabled':False, 'token':None, 'chat_id':0},
        }
        self.config.update(UserConfig.config)
        self.config.update(DeviceConfig.config)

        #################################################################
        # The first thing we need to initialize is the different devices
        # ways to obtain battery information and the TX led.
        #
        # This way we can re-enter deep sleep ASAP if we are just returning
        # from low battery deep sleep. We will just flash the led to
        # report we are actaully sleeping for low battery.
        #################################################################
        DeviceConfig.power_up(self)

        # Init TX led
        if self.config['tx_led']:
            self.tx_led = Pin(self.config['tx_led']['pin'],Pin.OUT)
        else:
            self.tx_led = None

        # We can be resumed from deep sleep for two reasons:
        # 1. We went in deep sleep for low battery.
        # 2. We are in "sensor mode" and went in deep sleep after
        #    transmitting the last sensor sample.
        if (hasattr(machine, 'DEEPSLEEP_RESET') and \
            machine.reset_cause() == machine.DEEPSLEEP_RESET) or \
            (hasattr(machine, 'WDT_RESET') and \
            machine.reset_cause() == machine.WDT_RESET):
            # Check if we are in low battery mode, and if the battery
            # is still too low to restart, before powering up anything
            # else.
            if self.low_battery(try_awake = True):
                for i in range(3):
                    self.set_tx_led(True)
                    time.sleep_ms(50)
                    self.set_tx_led(True)
                    time.sleep_ms(50)
                machine.deepsleep(5000) # Will restart again after few sec.

        ################### NORMAL STARTUP FOLLOWS ##################

        # Load certain configuration settings the user changed
        # using bang-commands.
        self.load_settings()

        # Init display
        self.display = None

        if 'ssd1306' in self.config:
            import ssd1306
            self.xres = self.config['ssd1306']['xres']
            self.yres = self.config['ssd1306']['yres']

            i2c = SoftI2C(sda=Pin(self.config['ssd1306']['sda']),
                          scl=Pin(self.config['ssd1306']['scl']))
            self.display = ssd1306.SSD1306_I2C(self.xres, self.yres, i2c)
            self.display.poweron()
            self.display.show()
        elif 'st7789' in self.config:
            import st7789
            self.xres = self.config['st7789']['xres']
            self.yres = self.config['st7789']['yres']

            cfg = self.config['st7789']
            spi = SPI(cfg['spi_channel'], baudrate=40000000, polarity=cfg['polarity'], phase=cfg['phase'], sck=Pin(cfg['sck']), mosi=Pin(cfg['mosi']), miso=Pin(cfg['miso']))
            self.display = st7789.ST7789_base (
                spi, cfg['xres'], cfg['yres'],
                reset = Pin(cfg['reset'], Pin.OUT) if isinstance(cfg['reset'],int) else None,
                dc = Pin(cfg['dc'], Pin.OUT),
                cs = Pin(cfg['cs'], Pin.OUT) if isinstance(cfg['cs'],int) else None
            )
            self.display.init(xstart=cfg['xstart'],ystart=cfg['ystart'],landscape=cfg['landscape'],mirror_y=cfg['mirror_y'],mirror_x=cfg['mirror_x'],inversion=cfg['inversion'])
            self.display.enable_framebuffer(mono=True)
            self.display.line = self.display.fb.line
            self.display.pixel = self.display.fb.pixel
            self.display.text = self.display.fb.text
            self.display.fill_rect = self.display.fb.fill_rect
            self.display.fill = self.display.fb.fill
            self.display.contrast = lambda x: x
        else:
            print("Headless mode (no display) selected")
            # Set dummy values for display because they cold be
            # still referenced to create objects.
            self.xres = 64
            self.yres = 64
            self.display = None

        # Views
        icons = StatusIcons(self.display,get_batt_perc=self.get_battery_perc)
        self.scroller = Scroller(self.display,icons=icons,xres=self.xres,yres=self.yres)
        if self.yres <= 64: self.scroller.select_font("small")
        self.splashscreen = SplashScreen(self.display,self.xres,self.yres)
        self.nodeslist_view = NodesListView(self,self.display)

        # Order in which the views will be selected when the
        # view switch button is pressed.
        self.views_order = [self.scroller, self.nodeslist_view]

        # View IDs
        if 'sensor' in self.config:
            self.switch_view(self.scroller)
        else:
            self.switch_view(self.splashscreen)

        # Init LoRa chip
        if 'sx1276' in self.config:
            import sx1276
            self.lora = sx1276.SX1276(self.config['sx1276'],self.receive_lora_packet,self.lora_tx_done)
        elif 'sx1262' in self.config:
            import sx1262
            self.lora = sx1262.SX1262(self.config['sx1262'],self.receive_lora_packet,self.lora_tx_done)
        self.lora_reset_and_configure()
        
        # Init BLE chip
        self.bleuart = None
        try:
            ble = bluetooth.BLE()
            if self.config['ble_enabled']:
                self.bleuart = BLEUART(ble, name="FW_%s" % self.config['nick'])
        except:
            pass

        # Create our CLI commands controller.
        self.cmdctrl = CommandsController(self)

        # Queue of messages we should send ASAP. We append stuff here, so they
        # should be sent in reverse order, from index 0.
        self.send_queue = []
        self.send_queue_max = 100 # Don't accumulate too many messages

        # We log received messages on persistent memory
        self.history = History("msg.db",histlen=100,recordsize=256)

        # Our keychain is responsible of handling keys and
        # encrypting / decrypting packets.
        self.keychain = Keychain()

        # Configure the duty cycle tracker, use a period of 25 minutes
        # with five 5min slots. We could extend it up to an hour, according
        # to regulations.
        self.duty_cycle = DutyCycle(slots_num=5,slots_dur=60*5)

        # Networking stuff. They are allocated only on demand in order
        # to save memory. Many users may not need such features.
        self.irc = None
        self.irc_task = None
        self.wifi = None
        self.telegram = None
        self.telegram_task = None

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

        # Create the sensor instance if FreakWAN is configured to run
        # in sensor mode.
        if 'sensor' in self.config:
            self.sensor = Sensor(self,self.config['sensor'])
        else:
            self.sensor = None

        # This is the buffer used in order to accumulate the
        # command the user is typing directly in the MicroPython
        # REPL via UBS serial.
        self.serial_buf = ""

        # If false, disable logging of debug info to serial.
        self.serial_log_enabled = True

    # Restart
    def reset(self):
        machine.reset()

    # Load settings.txt, with certain changes overriding our
    # self.config values.
    def load_settings(self):
        try:
            f = open("settings.txt","rb")
        except:
            return # ENOENT, likely
        try:
            content = f.read()
            f.close()
            exec(content,{},{'self':self})
        except Exception as e:
            self.serial_log("Loading settings: "+self.get_stack_trace(e))
            pass

    # Save certain settings the user is able to modify using
    # band commands. We just save things that we want likely to be
    # reloaded on startup.
    def save_settings(self):
        settings = ['nick', 'lora_sp','lora_bw','lora_cr','lora_pw','automsg','irc','telegram','wifi','wifi_default_network','quiet','check_crc']
        try:
            f = open("settings.txt","wb")
            code = ""
            for s in settings:
                if s in self.config:
                    code += "self.config['%s'] = %s\n" % (s,repr(self.config[s]))
            f.write(code)
            f.close()
        except Exception as e:
            self.serial_log("Saving settings: "+self.get_stack_trace(e))
            pass

    # Remove the setting file. After a restar the device will just use
    # wan_config.py settings.
    def reset_settings(self):
        try:
            os.unlink("settings.txt")
        except:
            pass

    # Call the current view refresh method, in order to draw the
    # representation of the view in the framebuffer.
    def refresh_view(self):
        self.current_view.refresh()

    # Switch to the specified view
    def switch_view(self,view):
        self.current_view = view
        self.refresh_view()

    # Reset the chip and configure with the required paramenters.
    # Used during initialization and also in the TX watchdog if
    # the radio is stuck transmitting the current frame for some
    # reason.
    def lora_reset_and_configure(self):
        was_receiving = self.lora.receiving
        self.lora.begin()
        self.lora.configure(self.config['lora_fr'],self.config['lora_bw'],self.config['lora_cr'],self.config['lora_sp'],self.config['lora_pw'])
        if was_receiving: self.lora.receive()

    # This is just a proxy for DeviceConfig hardware-specific method.
    def get_battery_microvolts(self):
        return DeviceConfig.get_battery_microvolts()

    # Return the battery percentage using the equation of the
    # discharge curve of a typical lipo 3.7v battery.
    def get_battery_perc(self):
        volts = DeviceConfig.get_battery_microvolts()/1000000
        if volts == 0: return 100
        perc = 123-(123/((1+((volts/3.7)**80))**0.165))
        return max(min(100,int(perc)),0)

    # Turn led on if state is True, off if it is False
    def set_tx_led(self,new_state):
        if not self.tx_led: return     # No led in this device
        if self.config['tx_led']['inverted']:
            new_state = not new_state
        if new_state:
            self.tx_led.on()
        else:
            self.tx_led.off()

    # Return a human readable nickname for the device, composed
    # using the device unique ID.
    def device_hw_nick(self):
        uid = list(machine.unique_id())
        nick = ""
        consonants = "kvprmnzflst"
        vowels = "aeiou"
        val = 0
        for x in range(len(uid)): val += uid[x] << (x*8)
        while val > 0 and len(nick) < 10:
            if len(nick) % 2:
                nick += consonants[val%len(consonants)]
                val = int(val/len(consonants))
            else:
                nick += vowels [val%len(vowels)]
                val = int(val/len(vowels))
        return nick

    # Put a packet in the send queue. Will be delivered ASAP.
    # The delay is in milliseconds, and is selected randomly
    # between 0 and the specified amount.
    #
    # Check the send_messages_in_queue() method for the function
    # that actually transfers the messages to the LoRa radio.
    def send_asynchronously(self,m,max_delay=SEND_MAX_DELAY,num_tx=1,relay=False):
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

    # Called when the packet was transmitted. Only useful to turn
    # the TX led off.
    def lora_tx_done(self):
        self.duty_cycle.end_tx()
        self.set_tx_led(False)

    # Send packets waiting in the send queue. This function, right now,
    # will just send every packet in the queue. But later it should
    # implement percentage of channel usage to be able to send only
    # a given percentage of the time.
    def send_messages_in_queue(self):
        if self.lora.modem_is_receiving_packet(): return
        send_later = [] # List of messages we can't send, yet.
        while len(self.send_queue):
            m = self.send_queue.pop(0)
            if (time.ticks_diff(time.ticks_ms(),m.send_time) > 0):
                # If the radio is busy sending, waiting here is of
                # little help: it may take a while for the packet to
                # be transmitted. Try again in the next cycle. However
                # check if the radio looks stuck sending for
                # a very long time, and if so, reset the LoRa radio.
                if self.lora.tx_in_progress:
                    if self.duty_cycle.get_current_tx_time() > 60000:
                        self.serial_log("WARNING: TX watchdog radio reset")
                        self.lora_reset_and_configure()
                        self.lora.receive()
                    # Put back the message, in the same order as
                    # it was, before exiting the loop.
                    self.send_queue = [m] + self.send_queue
                    break

                # Send the message and turn the green led on. This will
                # be turned off later when the IRQ reports success.
                if m.send_canceled == False:
                    encoded = m.encode(keychain=self.keychain)
                    if encoded != None:
                        self.set_tx_led(True)
                        self.duty_cycle.start_tx()
                        self.lora.send(encoded)
                        time.sleep_ms(1)
                    else:
                        m.send_canceled = True

                # This message may be scheduled for multiple
                # retransmissions. In this case decrement the count
                # of transmissions and queue it back again.
                if m.num_tx > 1 and m.send_canceled == False and not self.config['quiet']:
                    m.num_tx -= 1
                    m.send_time = time.ticks_add(time.ticks_ms(),urandom.randint(TX_AGAIN_MIN_DELAY,TX_AGAIN_MAX_DELAY))
                    send_later.append(m)
            else:
                # Time to send this message yet not reached, send later.
                send_later.append(m)

        # In case of early break of the while loop, we have still
        # messages in the original send queue, so the new queue is
        # the sum of the ones to process again, plus the ones not
        # yet processed.
        self.send_queue = self.send_queue + send_later

    # Called upon reception of some message. It triggers sending an ACK
    # if certain conditions are met. This method does not check the
    # message type: it is assumed that the method is called only for
    # message type where this makes sense.
    def send_ack_if_needed(self,m):
        if self.config['quiet']: return          # No ACKs in quiet mode.
        if m.type != MessageTypeData: return     # Acknowledge only data.
        if m.flags & MessageFlagsMedia: return   # Don't acknowledge media.
        if m.flags & MessageFlagsRelayed: return # Don't acknowledge relayed.
        ack = Message(mtype=MessageTypeAck,uid=m.uid,ack_type=m.type)
        self.send_asynchronously(ack,max_delay=0)
        self.serial_log("[>> net] Sending ACK about "+("%08x"%m.uid))

    # Called for data messages we see for the first time. If the
    # originator asked for relay, we schedule a retransmission of
    # this packet, so that other peers can receive it.
    def relay_if_needed(self,m):
        if self.config['quiet']: return          # No relays in quiet mode.
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
        self.scroller.icons.set_relay_visibility(True)
        self.serial_log("[>> net] Relaying "+("%08x"%m.uid)+" from "+m.nick)

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
                if self.config['prom']: return False
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
                self.serial_log("[cache] Evicted: "+"%08x"%uid)

        # If we processed all the items of the 'a' dictionary, start again.
        if len(self.processed_a) == 0 and len(self.processed_b) != 0:
            self.processed_a = self.processed_b
            self.processed_b = {}

    # Called by the LoRa radio IRQ upon new packet reception.
    def receive_lora_packet(self,lora_instance,packet,rssi,bad_crc):
        if self.config['check_crc'] and bad_crc: return
        m = Message.from_encoded(packet,self.keychain)
        if m:
            m.rssi = rssi
            if bad_crc: m.flags |= MessageFlagsBadCRC
            if m.no_key == True:
                # This message is encrypted and we don't have the
                # right key. Let's relay it, to help the network anyway.
                if self.mark_as_processed(m): return
                self.relay_if_needed(m)
            elif m.type == MessageTypeData:
                # Already processed? Return ASAP.
                if self.mark_as_processed(m):
                    self.serial_log("[<< net] Ignore duplicated message "+("%08x"%m.uid)+" <"+m.nick+"> "+m.text)
                    return

                # If this message is not relayed by some other node, then
                # it is a proof of recent node activity. We can update the
                # last seen time from the HELLO message we have in memory
                # for this node (if any).
                if not m.flags & MessageFlagsRelayed:
                    if m.sender in self.neighbors:
                        self.neighbors[m.sender].ctime = time.ticks_ms()

                # Report message to the user.
                msg_info = \
                    "(rssi:%d, ttl:%d, flags:%s)" % \
                    (m.rssi,m.ttl,"{0:b}".format(m.flags))
                channel_name = "" if not m.key_name else "#"+str(m.key_name)+" "

                if m.flags & MessageFlagsMedia:
                    if m.media_type == MessageMediaTypeImageFCI:
                        img = ImageFCI(data=m.media_data)
                        self.scroller.print(channel_name+m.nick+"> image:")
                        self.scroller.print(img)
                        user_msg = channel_name+m.nick+"> image"
                    elif m.media_type == MessageMediaTypeSensorData:
                        sensor_data = m.sensor_data_to_str()
                        self.serial_log("[SENSOR-DATA] channel:%s sensor_id:%s %s" % (channel_name.strip(),m.nick,sensor_data))
                        user_msg = channel_name+m.nick+"> "+sensor_data
                        self.scroller.print(user_msg)
                    else:
                        self.serial_log("[<<< net] Unknown media type %d" % m.media_type)
                        user_msg = channel_name+m.nick+"> unknown media"
                else:
                    user_msg = channel_name+m.nick+"> "+m.text
                    if m.flags & MessageFlagsRelayed: user_msg += " [R]"
                    if m.flags & MessageFlagsBadCRC: user_msg += " [BADCRC]"
                    self.scroller.print(user_msg)
                    if self.bleuart: self.bleuart.print(user_msg+" "+msg_info)
                    if self.irc: self.irc.reply(user_msg+" "+msg_info)
                    if self.telegram: self.telegram_send(user_msg+" "+msg_info)

                self.serial_log("\033[32m"+channel_name+user_msg+" "+msg_info+"\033[0m", force=True)
                self.refresh_view()

                # Reply with ACK if needed.
                self.send_ack_if_needed(m)

                # Save message on history DB
                encoded = m.encode(keychain=self.keychain)
                if encoded != None: self.history.append(encoded)

                # Relay if needed.
                self.relay_if_needed(m)
            elif m.type == MessageTypeAck:
                about = self.get_processed_message(m.uid)
                if about != None:
                    self.scroller.icons.set_ack_visibility(True)
                    self.serial_log("[<< net] Got ACK about "+("%08x"%m.uid)+" by "+m.sender_to_str())
                    about.acks[m.sender] = True
                    # If we received ACKs from all the nodes we know about,
                    # stop retransmitting this message.
                    if len(self.neighbors) and len(about.acks) == len(self.neighbors):
                        about.send_canceled = True
                        self.serial_log("[<< net] ACKs received from all the %d known nodes. Suppress resending." % (len(self.neighbors)))
            elif m.type == MessageTypeHello:
                # Limit the number of neighbors to protect against OOM
                # due to bugs or too many nodes near us.
                max_neighbors = 32
                if not m.sender in self.neighbors:
                    msg = "[net] New node sensed: "+m.sender_to_str()
                    self.serial_log(msg)
                    if self.bleuart: self.bleuart.print(msg)
                self.neighbors[m.sender] = m
                if len(self.neighbors) > max_neighbors:
                    self.neighbors.popitem()
            else:
                self.serial_log("receive_lora_packet(): message type not implemented: %d" % m.type)
        else:
            self.serial_log("!!! Can't decoded packet: "+repr(packet))
            if self.config['prom']:
                self.scroller.print("Unrecognized LoRa packet: "+repr(packet))

    # Send HELLO messages from time to time. Evict nodes not refreshed
    # for some time from the neighbors list.
    async def send_hello_message(self):
        hello_msg_period_min = 60000        # 1 minute
        hello_msg_period_max = 120000       # 2 minutes
        hello_msg_max_age = 600000          # 10 minutes
        while True:
            # Evict not refreshed nodes from neighbors.
            new = {}
            while len(self.neighbors):
                sender,m = self.neighbors.popitem()
                age = time.ticks_diff(time.ticks_ms(),m.ctime)
                if age <= hello_msg_max_age:
                    new[sender] = m
                else:
                    self.serial_log("[net] Flushing timedout neighbor: "+
                        m.sender_to_str()+" ("+m.nick+")")
            self.neighbors = new

            # Send HELLO, if not in quiet mode.
            if not self.config['quiet']:
                self.serial_log("[net] Sending HELLO message")
                msg = Message(mtype=MessageTypeHello,
                            nick=self.config['nick'],
                            text=self.config['status'],
                            seen=len(self.neighbors))
                self.send_asynchronously(msg,max_delay=0)

            # Wait until we need to send the next HELLO.
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
                self.send_asynchronously(msg,max_delay=0,num_tx=3,relay=True)
                self.scroller.print("you> "+msg.text)
                self.refresh_view()
                counter += 1
            await asyncio.sleep(urandom.randint(15000,20000)/1000) 

    # This shows some information about the process in the debug console.
    def show_status_log(self):
        sent = self.lora.msg_sent
        cached_total = len(self.processed_a)+len(self.processed_b)
        msg = "~"+self.config['nick']
        msg += " Sent:"+str(sent)
        msg += " SendQueue:"+str(len(self.send_queue))
        msg += " CacheLen:"+str(cached_total)
        msg += " FreeMem:"+str(gc.mem_free())
        msg += " DutyCycle: %.2f%%" % self.duty_cycle.get_duty_cycle()
        self.serial_log(msg)
    
    # This is the default callback that handle a message received from BLE.
    # It will:
    # 1. Get the text from BLE message;
    # 2. Create a our Message with the received text;
    # 3. Send asynchronously the message and display it.
    def ble_receive_callback(self):
        cmd = self.bleuart.read().decode()
        self.cmdctrl.exec_user_command(cmd,self.bleuart.print)

    # Process commands from IRC.
    def irc_receive_callback(self,cmd):
        self.cmdctrl.exec_user_command(cmd,self.irc.reply)

    # Process commands from Telegram:
    def telegram_receive_callback(self,bot,msg_type,chat_name,sender_name,chat_id,text,entry):
        self.config['telegram']['chat_id'] = chat_id
        self.cmdctrl.exec_user_command(text,self.telegram_send)

    # Reply to Telegram.
    def telegram_send(self,msg):
        if self.telegram and self.config['telegram']['chat_id'] != 0:
            self.telegram.send(self.config['telegram']['chat_id'],msg,True)

    # Return if the battery is under the low battery threshould.
    # If 'try_awake' is true, it means we are asking from the point
    # of view of awaking back the device after we did an emergency
    # shut down, and in that case, we want the battery to be a few
    # points more than the threshold.
    def low_battery(self,try_awake=False):
        min_level = self.config['sleep_battery_perc']
        if try_awake: min_level += 3
        return self.get_battery_perc() < min_level

    def power_off(self,offtime):
        self.lora.reset()
        if self.display and hasattr(self.display,'poweroff'):
            self.display.poweroff()
        machine.deepsleep(offtime)

    # We want to reply to CLI inputs even if written directly in the
    # UART via USB, so that a user with the REPL open with the device
    # will be able to send commands directly.
    async def receive_from_serial(self):
        while True:
            await asyncio.sleep(0.1)
            while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                try:
                    ch = sys.stdin.read(1)
                except:
                    continue
                if ch == '\n':
                    sys.stdout.write("\n")
                    cmd = self.serial_buf.strip()
                    self.serial_buf = ""
                    self.cmdctrl.exec_user_command(cmd,self.reply_to_serial)
                elif ord(ch) == 127:
                    # Backslash key.
                    self.serial_buf = self.serial_buf[:-1]
                    sys.stdout.write("\033[D \033[D") # Cursor back 1 position.
                else:
                    self.serial_buf += ch
                    sys.stdout.write(ch) # Echo

    # This method logs to the serial, but it is aware that we also let the
    # user write commands to the serial (see receive_from_serial() method).
    # So when we write to the serial, we hide the user input for a moment,
    # write the log, then restore the user input. Like an async readline
    # library would do.
    def serial_log(self,msg,force=False):
        if not self.serial_log_enabled and not force: return
        if len(self.serial_buf):
            sys.stdout.write("\033[2K\033[G") # Clean line, cursor on the left.
        sys.stdout.write(msg+"\r\n")
        if len(self.serial_buf):
            sys.stdout.write(self.serial_buf)

    # Callback to reply to CLI commands when they are received from
    # the USB serial.
    def reply_to_serial(self,msg):
        self.serial_log(msg,force=True)

    # Start the WiFi subsystem, using an already configured network
    # (if password is None) or a new network.
    def start_wifi(self,network,password=None):
        if password == None:
            password = self.config['wifi'].get(network)
            if not password: return False
        if not self.wifi: self.wifi = WiFiConnection()
        self.serial_log("[WiFi] Connecting to %s" % network)
        self.wifi.connect(network,password)
        self.config['wifi_default_network'] = network
        return True

    # Disconenct WiFi network
    def stop_wifi(self):
        # WiFi may be enabled even if we didn't start it in the lifespan
        # of the application: after a soft reset, the ESP32 will keep
        # the state of the WiFi network.
        if not self.wifi: self.wifi = WiFiConnection()
        self.serial_log("[WiFi] Stopping Wifi (if active)")
        self.wifi.stop()
        self.config['wifi_default_network'] = False

    # Start the IRC subsystem.
    def start_irc(self):
        if not self.irc:
            self.irc = IRC(self.config['nick'],self.irc_receive_callback)
        if not self.irc.active:
            self.irc_task = asyncio.create_task(self.irc.run())
        self.config['irc']['enabled'] = True
        return self.irc_task

    # Stop the IRC subsystem
    def stop_irc(self):
        if not self.irc: return
        self.irc.reply("IRC subsystem is shutting down")
        self.irc.stop()
        self.irc_task = None
        self.irc = None
        self.config['irc']['enabled'] = False

    # Start the Telegram bot.
    def start_telegram(self):
        if not self.telegram:
            self.telegram = TelegramBot(self.config['telegram']['token'], self.telegram_receive_callback)
        if not self.telegram_task:
            self.telegram_task = asyncio.create_task(self.telegram.run())
            self.config['telegram']['enabled'] = True

    # Stop the Telegram bot handling.
    def stop_telegram(self):
        self.telegram_send("Telegram subsystem is shutting down")
        self.telegram.stop()
        self.telegram_task = None
        self.telegram = None
        self.config['telegram']['enabled'] = False

    # This callback can be configured during the device init
    # in device_config.py. When pressed, button 0 switches to
    # the next view on the device screen.
    def button_0_pressed(self,pin):
        if self.current_view not in self.views_order:
            idx = 0
        else:
            # Switch to next view or wrap around.
            idx = self.views_order.index(self.current_view)
            if idx == len(self.views_order)-1:
                idx = 0
            else:
                idx += 1
        self.switch_view(self.views_order[idx])

    # This is the main control loop of the application, where we perform
    # periodic tasks, like sending messages in the queue. Other tasks
    # are handled by different tasks created at startup, at the end
    # of this file.
    async def cron(self):
        tick = 0
        animation_ticks = 10
        sensor_state = "start"

        while True:
            # Splash screen handling.
            if tick <= animation_ticks:
                if tick == animation_ticks or self.low_battery() or self.sensor:
                    self.switch_view(self.scroller)
                    self.scroller.print("FreakWAN v"+Version)
                    tick = animation_ticks+1

                self.splashscreen.next_frame()
                self.refresh_view()
                tick += 1
                continue

            ### SENSOR MODE HANDLING ###
            if self.sensor:
                self.sensor.exec_state_machine(tick)
            ############################

            # Normal loop, entered after the splah screen.
            if tick % 10 == 0: gc.collect()
            if tick % 50 == 0: self.show_status_log()

            # From time to time, refresh the current view so that
            # we can update the battery icon, turn off the ACK
            # and relay icon, and so forth.
            if hasattr(self.current_view,'min_refresh_time'):
                rt = int(self.current_view.min_refresh_time() * 10)
                if tick % rt == 0: self.refresh_view()

            # Periodically check the battery level, and if too low, protect
            # it shutting the device down.
            if tick % 100 == 0:
                if self.low_battery():
                    self.scroller.print("")
                    self.scroller.print("*******************")
                    self.scroller.print("***             ***")
                    self.scroller.print("*** LOW BATTERY ***")
                    self.scroller.print("***             ***")
                    self.scroller.print("*******************")
                    self.scroller.print("")
                    self.scroller.print("Device frozen. Switching off in 15 seconds.")
                    self.refresh_view()
                    time.sleep_ms(15000)
                    self.power_off(5000)

            self.send_messages_in_queue()
            self.evict_processed_cache()

            # The tick time is randomized between 80 and 120
            # milliseconds instead of being exactly 100. This is
            # useful to always take the different nodes in desync:
            # a simple but effective way to avoid an all-together start
            # after listen-before-talk and other events.
            sleeptime = urandom.randint(800,1200)/10000
            await asyncio.sleep(sleeptime)
            tick += 1

    # Turn the exception into a proper stack trace.
    # Much better than str(exception).
    def get_stack_trace(self,exception):
        buf = io.StringIO()
        sys.print_exception(exception, buf)
        return buf.getvalue()

    def crash_handler(self,loop,context):
        # Try freeing some memory in order to avoid OOM during
        # the crash logging itself.
        self.send_queue = []
        self.processed_a = {}
        self.processed_b = {}
        gc.collect()

        # Capture the error as a string. It isn't of much use to have
        # it just in the serial, if nobody is connected via USB.
        stacktrace = self.get_stack_trace(context['exception'])
        print(stacktrace)

        # Print errors on the OLED, too. We want to immediately
        # recognized a crashed device.
        for stline in stacktrace.split("\n"):
            self.scroller.print(stline)
        self.scroller.refresh()

        # Let's log the stack trace on the filesystem, too.
        f = open('crash.txt','w')
        f.write(stacktrace)
        f.close()
