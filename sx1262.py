# SX1262 driver for MicroPython
# Copyright (C) 2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

# TODO:
# - Improve modem_is_receiving_packet() if possible at all with the SX1262.

from machine import Pin, SoftSPI
from micropython import const
import time, struct, urandom

# SX1262 constants

# Registers IDs and notable values
RegRxGain = const(0x8ac)
RegRxGain_PowerSaving = const(0x94) # Value for RegRxGain
RegRxGain_Boosted = const(0x96)     # Value for RegRxGain
RegLoRaSyncWordMSB = const(0x0740)
RegLoRaSyncWordLSB = const(0x0741)
RegTxClampConfig = const(0x08d8)

# Dio0 mapping
IRQSourceNone = const(0)
IRQSourceTxDone = const(1 << 0)
IRQSourceRxDone = const(1 << 1)
IRQSourcePreambleDetected = const(1 << 2)
IRQSourceSyncWordValid = const(1 << 3)
IRQSourceHeaderValid = const(1 << 4)
IRQSourceHeaderErr = const(1 << 5)
IRQSourceCrcErr = const(1 << 6)
IRQSourceCadDone = const(1 << 7)
IRQSourceCadDetected = const(1 << 8)
IRQSourceTimeout = const(1 << 9)

# Commands opcodes
ClearIrqStatusCmd = const(0x02)
SetDioIrqParamsCmd = const(0x08)
WriteRegisterCmd = const(0x0d)
WriteBufferCmd = const(0x0e)
GetIrqStatusCmd = const(0x12)
GetRxBufferStatusCmd = const(0x13)
GetPacketStatusCmd = const(0x14)
ReadRegisterCmd = const(0x1d)
ReadBufferCmd = const(0x1e)
SetStandByCmd = const(0x80)
SetRxCmd = const(0x82)
SetTxCmd = const(0x83)
SleepCmd = const(0x84)
SetRfFrequencyCmd = const(0x86)
SetPacketTypeCmd = const(0x8a)
SetModulationParamsCmd = const(0x8b)
SetPacketParamsCmd = const(0x8c)
SetTxParamsCmd = const(0x8e)
SetBufferBaseAddressCmd = const(0x8f)
SetPaConfigCmd = const(0x95)
SetDIO3AsTCXOCtrlCmd = const(0x97)
CalibrateImageCmd = const(0x98)
SetDIO2AsRfSwitchCtrlCmd = const(0x9d)

# Constants for SetPacketParam() arguments
PacketHeaderTypeExplicit = const(0)
PacketHeaderTypeImplicit = const(1)
PacketCRCOff = const(1)
PacketCRCOn = const(1)
PacketStandardIQ = const(0)
PacketInvertedIQ = const(1)

# Constants used for listen-before-talk method
# modem_is_receiving_packet()
POAPreamble = const(0)
POAHeader = const(1)

class SX1262:
    def __init__(self, pinset, rx_callback, tx_callback = None):
        self.receiving = False # True if we are in receive mode.
        self.tx_in_progress = False
        self.packet_on_air = False # see modem_is_receiving_packet().
        self.msg_sent = 0
        self.received_callback = rx_callback
        self.transmitted_callback = tx_callback
        self.busy_pin = Pin(pinset['busy'],Pin.IN)
        self.reset_pin = Pin(pinset['reset'],Pin.OUT)
        self.chipselect_pin = Pin(pinset['chipselect'], Pin.OUT)
        self.clock_pin = Pin(pinset['clock'])
        self.mosi_pin = Pin(pinset['mosi'])
        self.miso_pin = Pin(pinset['miso'])
        self.dio_pin = Pin(pinset['dio'], Pin.IN)
        self.spi = SoftSPI(baudrate=10000000, polarity=0, phase=0, sck=self.clock_pin, mosi=self.mosi_pin, miso=self.miso_pin)
        self.bw = 0 # Currently set bandwidth. Saved to compute freq error.
         
    def reset(self):
        self.reset_pin.off()
        time.sleep_us(500)
        self.reset_pin.on()
        time.sleep_us(500)
        self.receiving = False
        self.tx_in_progress = False

    def standby(self):
        self.command(SetStandByCmd,0) # argument 0 menas STDBY_RC mode.

    # Note: the CS pin logic is inverted. It requires to be set to low
    # when the chip is NOT selected for data transfer.
    def deselect_chip(self):
        self.chipselect_pin.on()

    def select_chip(self):
        self.chipselect_pin.off()

    # Send a read or write command, and return the reply we
    # got back. 'data' can be both an array of a single integer.
    def command(self, opcode, data=None): 
        if data != None:
            if isinstance(data,int): data = [data]
            payload = bytearray(1+len(data)) # opcode + payload
            payload[0] = opcode
            payload[1:] = bytes(data)
        else:
            payload = bytearray([opcode])
        reply = bytearray(len(payload))

        # Wait for the chip to return available.
        while self.busy_pin.value():
            time.sleep_us(1)

        self.select_chip()
        self.spi.write_readinto(payload,reply)
        self.deselect_chip()

        # Enable this for debugging.
        if False: print(f"Reply for {hex(opcode)} is {repr(reply)}")

        return reply

    def readreg(self, addr, readlen=1):
        payload = bytearray(2+1+readlen) # address + nop + nop*bytes_to_read
        payload[0] = (addr&0xff00)>>8
        payload[1] = addr&0xff
        reply = self.command(ReadRegisterCmd,payload)
        return reply[4:]

    def writereg(self, addr, data):
        if isinstance(data,int): data = bytes([data])
        payload = bytearray(2+len(data)) # address + bytes_to_write
        payload[0] = (addr&0xff00)>>8
        payload[1] = addr&0xff
        payload[2:] = data
        self.command(WriteRegisterCmd,payload)

    def readbuf(self, off, numbytes):
        payload = bytearray(2+numbytes)
        payload[0] = off
        data = self.command(ReadBufferCmd,payload)
        return data[3:]

    def writebuf(self, off, data):
        payload = bytearray(1+len(data))
        payload[0] = off
        payload[1:] = data
        self.command(WriteBufferCmd,payload)

    def set_frequency(self, mhz):
        # The final frequency is (rf_freq * xtal freq) / 2^25.
        oscfreq = 32000000 # Oscillator frequency for registers calculation
        rf_freq = int(mhz * (2**25) / oscfreq)
        arg = [(rf_freq & 0xff000000) >> 24,
               (rf_freq & 0xff0000) >> 16,
               (rf_freq & 0xff00) >> 8,
               (rf_freq & 0xff)]
        self.command(SetRfFrequencyCmd, arg)

    def set_packet_params(self, preamble_len = 12, header_type = PacketHeaderTypeExplicit, payload_len = 255, crc = PacketCRCOn, iq_setup = PacketStandardIQ):
        pp = bytearray(6)
        pp[0] = preamble_len >> 8
        pp[1] = preamble_len & 0xff
        pp[2] = header_type
        pp[3] = payload_len
        pp[4] = crc
        pp[5] = iq_setup
        self.command(SetPacketParamsCmd,pp)

    def begin(self):
        self.reset()
        self.deselect_chip()
        self.standby()              # SX126x gets configured in standby.
        self.command(SetPacketTypeCmd,0x01) # Put the chip in LoRa mode.

        # Apply fix for PA clamping as specified in datasheet.
        curval = self.readreg(RegTxClampConfig)[0]
        curval |= 0x1E
        self.writereg(RegTxClampConfig,curval)

    # Set the radio parameters. Allowed spreadings are from 6 to 12.
    # Bandwidth and coding rate are listeed below in the dictionaries.
    # TX power is from -9 to +22 dbm.
    def configure(self, freq, bandwidth, rate, spreading, txpower):
        Bw = {   7800: 0,
                10400: 0x8,
                15600: 0x1,
                20800: 0x9,
                31250: 0x2,
                41700: 0xa,
                62500: 0x3,
               125000: 0x4,
               250000: 0x5,
               500000: 0x6}
        CodingRate = {  5:1,
                        6:2,
                        7:3,
                        8:4}

        # Make sure the chip is in standby mode
        # during configuration.
        self.standby()

        # Set LoRa parameters.
        lp = bytearray(4)
        lp[0] = spreading
        lp[1] = Bw[bandwidth]
        lp[2] = CodingRate[rate]
        lp[3] = 1 # Enable low data rate optimization
        self.command(SetModulationParamsCmd,lp)

        # Set packet params.
        self.set_packet_params()

        # Set RF frequency.
        self.set_frequency(freq)

        # Use maximum sensibility
        self.writereg(RegRxGain,0x96)

        # Set TCXO voltage to 1.7 with 5000us delay.
        tcxo_delay = int(5000.0 / 15.625)
        tcxo_config = bytearray(4)
        tcxo_config[0] = 1 # 1.7v
        tcxo_config[1] = (tcxo_delay >> 16) & 0xff
        tcxo_config[2] = (tcxo_delay >> 8) & 0xff
        tcxo_config[3] = (tcxo_delay >> 0) & 0xff
        self.command(SetDIO3AsTCXOCtrlCmd,tcxo_config)

        # Set DIO2 as RF switch like in Semtech examples.
        self.command(SetDIO2AsRfSwitchCtrlCmd,1)

        # Set the power amplifier configuration.
        paconfig = bytearray(4)
        paconfig[0] = 4 # Duty Cycle of 4
        paconfig[1] = 7 # Max output +22 dBm
        paconfig[2] = 0 # Select PA for SX1262 (1 would be SX1261)
        paconfig[3] = 1 # Always set to 1 as for datasheet
        self.command(SetPaConfigCmd,paconfig)

        # Set TX power and ramping. We always use high power mode.
        txpower = min(max(-9,txpower),22)
        txparams = bytearray(2)
        txparams[0] = (0xF7 + (txpower+9)) % 256
        txparams[1] = 4 # 200us ramping time
        self.command(SetTxParamsCmd,txparams)

        # We either receive or send, so let's use all the 256 bytes
        # of FIFO available by setting both recv and send FIFO address
        # to the base.
        self.command(SetBufferBaseAddressCmd,[0,0])
       
        # Setup the IRQ handler to receive the packet tx/rx and
        # other events. Note that the chip will put the packet
        # on the FIFO even on CRC error.
        # We will enable all DIOs for all the interrputs. In
        # practice most of the times only one chip DIO is connected
        # to the MCU.
        self.dio_pin.irq(handler=self.txrxdone, trigger=Pin.IRQ_RISING)
        self.command(SetDioIrqParamsCmd,[0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff])
        self.clear_irq()

        # Set sync word to 0x12 (private network).
        # Note that "12" is in the most significant hex digits of
        # the two registers: [1]4 and [2]4.
        self.writereg(RegLoRaSyncWordMSB,0x14)
        self.writereg(RegLoRaSyncWordLSB,0x24)

        # Calibrate for the specific selected frequency
        if 430 <= freq <= 440: f1,f2 = 0x6b,0x6f
        elif 470 <= freq <= 510: f1,f2 = 0x75,0x81
        elif 779 <= freq <= 787: f1,f2 = 0xc1,0xc5
        elif 863 <= freq <= 870: f1,f2 = 0xd7,0xdb
        elif 902 <= freq <= 928: f1,f2 = 0xe1,0xe9
        else: f1,f2 = None,None

        if f1 and f2:
            self.command(CalibrateImageCmd,[f1,f2])

    # This is just for debugging. We can understand if a given command
    # caused a failure while debugging the driver since the command status
    # will be set to '5'. We can also observe if the chip is in the
    # right mode (tx, rx, standby...).
    def show_status(self):
        status = self.command(0xc0,0)[1]
        print("Chip mode  = ", (status >> 4) & 7)
        print("Cmd status = ", (status >> 1) & 7)

    # Put the chip in continuous receive mode.
    # Note that the SX1262 is bugged and if there is a strong
    # nearby signal sometimes it "crashes" and no longer
    # receives anything, so it may be a better approach to
    # set a timeout and re-enter receive from time to time?
    def receive(self):
        self.command(SetRxCmd,[0xff,0xff,0xff])
        self.receiving = True
    
    def get_irq(self):
        reply = self.command(GetIrqStatusCmd,[0,0,0])
        return (reply[2]<<8) | reply[3]

    def clear_irq(self):
        reply = self.command(ClearIrqStatusCmd,[0xff,0xff])

    # This is our IRQ handler. By default we don't mask any interrupt
    # so the function may be called for more events we actually handle.
    def txrxdone(self, pin):
        event = self.get_irq()
        self.clear_irq()

        if event & (IRQSourceRxDone|IRQSourceCrcErr):
            # Packet received. The channel is no longer busy.
            self.packet_on_air = False

            # Obtain packet information.
            bs = self.command(GetRxBufferStatusCmd,[0]*3)
            ps = self.command(GetPacketStatusCmd,[0]*4)

            # Extract packet information.
            packet_len = bs[2]
            packet_start = bs[3]
            rssi = -ps[2]/2 # Average RSSI in dB.
            snr = ps[3]-256 if ps[3] > 128 else ps[3] # Convert to unsigned
            snr /= 4 # The reported value is upscaled 4 times.

            packet = self.readbuf(packet_start,packet_len)
            bad_crc = (event & IRQSourceCrcErr) != 0

            if bad_crc:
                print("SX1262: packet with bad CRC received")

            # Call the callback the user registered, if any.
            if self.received_callback:
                self.received_callback(self, packet, rssi, bad_crc)
        elif event & IRQSourceTxDone:
            self.msg_sent += 1
            # After sending a message, the chip will return in
            # standby mode. However if we were receiving we
            # need to return back to such state.
            if self.transmitted_callback: self.transmitted_callback()
            if self.receiving: self.receive()
            self.tx_in_progress = False
        elif event & IRQSourcePreambleDetected :
            # Packet detected, we will return true for some
            # time when user calls modem_is_receiving_packet().
            self.packet_on_air = time.ticks_ms()
            self.packet_on_air_type = POAPreamble
        elif event & IRQSourceHeaderValid:
            # The same as above, but if we also detected a header
            # we will take this condition for a bit longer.
            self.packet_on_air = time.ticks_ms()
            self.packet_on_air_type = POAHeader
        else: 
            print("SX1262: not handled event IRQ flags "+bin(event))

    def get_instantaneous_rss(self):
        data = self.command(0x15,[0,0])
        return -data[2]/2

    # This modem is used for listen-before-talk and returns true if
    # even if the interrupt of packet reception completed was not yet
    # called, we believe there is a current packet-on-air that we are
    # possibly receiving. This way we can avoid to transmit while there
    # is already a packet being transmitted, avoiding collisions.
    #
    # While the RX1276 has a register that tells us if a reception is
    # in progress, the RX1262 lacks it, so we try to do our best using
    # other systems...
    def modem_is_receiving_packet(self):
        if self.packet_on_air != False:
            # We are willing to wait more or less before cleaning
            # the channel busy flag, depending on the fact we
            # were able to detect just a preamble or also a valid
            # header.
            timeout = 2000 if self.packet_on_air_type == POAPreamble else 5000
            age = time.ticks_diff(time.ticks_ms(),self.packet_on_air)
            if age > timeout: self.packet_on_air = False
        return self.packet_on_air != False

    # Send the specified packet immediately. Will raise the interrupt
    # when finished.
    def send(self, data): 
        self.tx_in_progress = True
        self.set_packet_params(payload_len = len(data))
        self.writebuf(0x00,data)
        self.command(SetTxCmd,[0,0,0]) # Enter TX mode without timeout.

# Example usage.
if  __name__ == "__main__":
    pinset = {
        'busy': 7,
        'reset': 8,
        'chipselect': 5,
        'clock': 3,
        'mosi': 1,
        'miso': 4,
        'dio': 9
    }

    # The callback will be called every time a packet was
    # received.
    def onrx(lora_instance,packet,rssi,bad_crc):
        print(f"Received packet {packet} RSSI:{rssi} bad_crc:{bad_crc}")

    lora = SX1262(pinset=pinset,rx_callback=onrx)
    lora.begin() # Initialize the chip.
    lora.configure(869500000, 250000, 8, 12, 22) # Set our configuration.
    lora.receive() # Enter RX mode.
    lora.show_status() # Show the current device mode.

    # Send packets from time to time, while receiving if there
    # is something in the air.
    while True:
        if True:
            time.sleep(10)
            # Example packet in FreakWAN format.
            # Note that after we send a packet, if we were in
            # receive mode, we will return back in receive mode.
            lora.send(bytearray(b'\x00\x024j\x92\x11\x0f\x0c\x8b\x95\xa1\xe70\x07anti433Hi 626'))
