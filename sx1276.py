# SX1276 driver for MicroPython
# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

from machine import Pin, SoftSPI
import time, struct, urandom

# SX1276 constants

# Registers IDs
RegFifo = 0x00
RegOpMode = 0x01
RegFrfMsb = 0x06
RegFrfMid = 0x07
RegFrfLsb = 0x08
RegPaConfig = 0x09
RegFifoTxBaseAddr = 0x0e
RegFifoRxBaseAddr = 0x0f
RegFifoAddrPtr = 0x0d
RegFifoRxCurrentAddr = 0x10
RegIrqFlagsMask = 0x11
RegIrqFlags = 0x12
RegRxNbBytes = 0x13
RegModemStat = 0x18
RegPktSnrValue = 0x19
RegPktRssiValue = 0x1a 
RegRssiValue = 0x1b
RegModemConfig1 = 0x1d
RegModemConfig2 = 0x1e
RegPreambleMsb = 0x20
RegPreambleLsb = 0x21
RegPayloadLength = 0x22
RegModemConfig3 = 0x26
RegDioMapping1 = 0x40
RegVersion = 0x42
RegPaDac = 0x4d  

# Working modes
ModeSleep = 0x00
ModeStandby = 0x01
ModeTx = 0x03
ModeContRx = 0x5
ModeSingleRx = 0x6

# Dio0 mapping
Dio0RxDone = 0 << 6
Dio0TxDone = 1 << 6

# Flags for RegIrqFlags register
IRQRxTimeout = 1<<7
IRQRxDone = 1<<6
IRQPayloadCrcError = 1<<5
IRQValidHeader = 1<<4
IRQTxDone = 1<<3
IRQCadDone = 1<<2
IRQFhssChangeChannel = 1<<1
IRQCadDetected = 1<<0

# RegModemStat bits
ModemStatusSignalDetected = 1<<0
ModemStatusSignalSynchronized = 1<<1
ModemStatusRXOngoing = 1<<2
ModemStatusHeaderInfoValid = 1<<3
ModemStatusModemClear = 1<<4

class SX1276:
    def __init__(self, pinset, rx_callback, tx_callback = None):
        self.receiving = False
        self.tx_in_progress = False
        self.msg_sent = 0
        self.received_callback = rx_callback
        self.transmitted_callback = tx_callback
        self.reset_pin = Pin(pinset['reset'],Pin.OUT)
        self.chipselect_pin = Pin(pinset['chipselect'], Pin.OUT)
        self.clock_pin = Pin(pinset['clock'])
        self.mosi_pin = Pin(pinset['mosi'])
        self.miso_pin = Pin(pinset['miso'])
        self.dio0_pin = Pin(pinset['dio0'], Pin.IN)
        self.spi = SoftSPI(baudrate=10000000, polarity=0, phase=0, sck=self.clock_pin, mosi=self.mosi_pin, miso=self.miso_pin)
         
    def reset(self):
        self.reset_pin.off()
        time.sleep_us(500)
        self.reset_pin.on()
        time.sleep_us(500)
        self.receiving = False
        self.tx_in_progress = False

    # Note: the CS pin logic is inverted. It requires to be set to low
    # when the chip is NOT selected for data transfer.
    def deselect_chip(self):
        self.chipselect_pin.on()

    def select_chip(self):
        self.chipselect_pin.off()

    def begin(self):
        self.reset()
        self.deselect_chip()
        self.spi_write(RegOpMode,ModeSleep) # Put in sleep
        self.spi_write(RegOpMode,ModeSleep | 1<<7) # Enable LoRa radio

    # Set the radio parameters. Allowed spreadings are from 6 to 12.
    # Bandwidth and coding rate are listeed below in the dictionaries.
    def configure(self, freq, bandwidth, rate, spreading):
        Bw = {   7800: 0b0000,
                10400: 0b0001,
                15600: 0b0010,
                20800: 0b0011,
                31250: 0b0100,
                41700: 0b0101,
                62500: 0b0110,
               125000: 0b0111,
               250000: 0b1000,
               500000: 0b1001}
        CodingRate = {  5:0b001,
                        6:0b010,
                        7:0b011,
                        8:0b100}

        # Set bandwidth and coding rate. Lower bit is left to 0, so
        # explicit header is selected.
        self.spi_write(RegModemConfig1, Bw[bandwidth] << 4 | CodingRate[rate] << 1)

        RxPayloadCrcOn   = 1
        # Set spreading, CRC ON, TX mode normal
        self.spi_write(RegModemConfig2, spreading << 4 | RxPayloadCrcOn << 2)

        # Enable low data rate optimizer and AGC.
        self.spi_write(RegModemConfig3, 1 << 3 | 1 << 2)  
        
        # Preamble length
        self.spi_write(RegPreambleMsb, 0)  # No need to set a huge preamble.
        self.spi_write(RegPreambleLsb, 12) # LSB set to 12. So preamble len: 12
        
        # Set frequency
        oscfreq = 32000000 # Oscillator frequency for registers calculation

        # The frequency step is: oscillator frequency / 2^19.
        fstep = oscfreq / (2**19)

        # Compute the frequency we want in terms of steps, then
        # set the three registers composing the frequency.
        freq_in_steps = int(freq/fstep)
        self.spi_write(RegFrfMsb,(freq_in_steps >> 16) & 0xff)
        self.spi_write(RegFrfMid,(freq_in_steps >> 8) & 0xff)
        self.spi_write(RegFrfLsb,(freq_in_steps >> 0) & 0xff)
        
        # Set TX power. We want +17db, so we enable PA_BOOST.
        # With boost enabled, output power is due by Pout=17-(15-OutputPower)
        boost = 1<<7
        # Select max power available, but with PA_BOOST enabled should not
        # do anything useful.
        maxpower = 7<<4
        outpower = 15 # Pout = 17-(15-15) = +17db
        self.spi_write(RegPaConfig, boost|maxpower|outpower)
        
        # We either receive or send, so let's use all the 256 bytes
        # of FIFO available by setting both recv and send FIFO address
        # to the base.
        self.spi_write(RegFifoTxBaseAddr, 0)
        self.spi_write(RegFifoRxBaseAddr, 0)
       
        # Setup the IRQ handler to receive the packet tx/rx and
        # other events. Note that the chip will put the packet
        # on the FIFO even on CRC error.
        self.dio0_pin.irq(handler=self.txrxdone, trigger=Pin.IRQ_RISING)
        self.spi_write(RegIrqFlagsMask, 0) # Don't mask any IRQ.

        # Put the chip in standby in order to initialize the config.
        # We will change the mode later, to do rx or tx. The
        # configure() method should be called after the begin() method,
        # so the chip was in sleep during the configuration.
        self.spi_write(RegOpMode, ModeStandby)
    
    def spi_write(self, regid, data): 
        # Writes are performed sending as first byte the register
        # we want to address, with the highest bit set.
        if isinstance(data,int):
            spi_payload = bytes([regid|0x80,data])
        elif isinstance(data,str):
            spi_payload = bytes([regid|0x80]) + bytes(data, 'utf-8')
        elif isinstance(data,bytes):
            spi_payload = bytes([regid|0x80]) + data
        else:
            raise Exception("spi_write can only handle integers and strings")
        self.select_chip()
        self.spi.write(spi_payload)
        self.deselect_chip()

    # SPI read. For simplicity in the API, if the read len is one
    # we return the byte value itself (the first byte is not data).
    # However for bulk reads we return the string (minus the first
    # byte, as said).
    def spi_read(self, regid, l=1):
        # Reads are similar to writes but we don't need to set
        # the highest bit of the byte, so the SPI library will take
        # care of writing the register.
        self.select_chip()
        if l == 1:
            rcv = self.spi.read(l+1,regid)[1]
        else:
            rcv = self.spi.read(l+1,regid)[1:]
        self.deselect_chip()
        return rcv

    # This is our IRQ handler. By default we don't mask any interrupt
    # so the function may be called for more events we actually handle.
    def txrxdone(self, pin): 
        event = self.spi_read(RegIrqFlags)
        self.spi_write(RegIrqFlags, 0xff) # Clear flags
        if (event & IRQRxDone) and not (event & IRQPayloadCrcError):
            # Read data from the FIFO
            addr = self.spi_read(RegFifoRxCurrentAddr)
            self.spi_write(RegFifoAddrPtr, addr) # Read starting from addr
            packet_len = self.spi_read(RegRxNbBytes)
            packet = self.spi_read(RegFifo, packet_len)
            snr = self.spi_read(RegPktSnrValue)
            snr /= 4 # Packet SNR * 0.25, section 3.5.5 of chip spec.
            rssi = self.spi_read(RegPktRssiValue) 

            # Convert RSSI, also taking into account SNR, but only when the
            # message we received has a power under the noise level. Odd
            # but possible with LoRa modulation.
            #
            # We use the formula found in the chip datasheet.
            # Note: this forumla is correct for HF (high frequency) port,
            # but otherwise the constant -157 should be replaced with
            # -164.
            if snr >= 0:
                rssi = round(-157+16/15*rssi,2)
            else:
                rssi = round(-157+rssi+snr,2)

            # Call the callback the user registered, if any.
            if self.received_callback:
                self.received_callback(self, packet, rssi)
        elif event & IRQTxDone:
            self.msg_sent += 1
            # After sending a message, the chip will return in
            # standby mode. However if we were receiving we
            # need to return back to such state.
            if self.transmitted_callback: self.transmitted_callback()
            if self.receiving: self.receive()
            self.tx_in_progress = False
        elif (event & IRQRxDone) and (event & IRQPayloadCrcError):
            print("SX1276: packet with bad CRC received")
        else: 
            print("SX1276: not handled event IRQ flags "+str(event))

    def get_modem_stat(self):
        return self.spi_read(RegModemStat)

    def modem_is_receiving_packet(self):
        return self.get_modem_stat() & ModemStatusSignalDetected

    def receive(self):    
        # Raise IRQ when a packet is received.
        self.spi_write(RegDioMapping1, Dio0RxDone)
        # Go in continuous receiving mode.
        self.spi_write(RegOpMode, ModeContRx)
        self.receiving = True
        
    def send(self, data): 
        self.tx_in_progress = True
        self.spi_write(RegDioMapping1, Dio0TxDone)
        self.spi_write(RegFifoAddrPtr, 0) # Write data starting from FIFO byte 0
        self.spi_write(RegFifo, data)     # Populate FIFO with message
        self.spi_write(RegPayloadLength, len(data))  # Store len of message
        self.spi_write(RegOpMode, ModeTx) # Switch to TX mode

