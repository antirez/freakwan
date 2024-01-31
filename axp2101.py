from machine import Pin, SoftI2C

# Setup the AXP2101 to power the device
class AXP2101:
    def __init__(self, sda=10, scl=11):
        self.i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl))
        self.slave_addr = 0x34 # AXP2101 i2c slave address.

        if False:
            # Set above to True if you want to list all the address
            # of reachable devices. In the t-watch S3 they should
            # be 25, 52, 81, 90. Corresponding (in random order) to
            # the haptic motor, RTC clock, accelerometer and the
            # AXP2101.
            print("i2c devices replying to SDA:10 SCL:11",i2c.scan())

    def read(self,reg):
        data = self.i2c.readfrom_mem(self.slave_addr,reg,1)
        return data[0]

    def write(self,reg,val):
        self.i2c.writeto_mem(self.slave_addr,reg,bytearray([val]))

    def setbit(self,reg,bit):
        oldval = self.read(reg)
        oldval |= 1<<bit
        self.write(reg,oldval)

    def clearbit(self,reg,bit):
        oldval = self.read(reg)
        oldval &= 0xff ^ (1<<bit)
        self.write(reg,oldval)

    # Return battery voltage in millivolts.
    def get_battery_voltage(self):
        high_bits = self.read(0x34)
        low_bits = self.read(0x35)
        return (high_bits&0b111111)<<8 | low_bits

    # T-WATCH S3 specific power-on steps.
    def twatch_s3_poweron(self):
        # Read PMU STATUS 1
        pmu_status = self.read(0x00)
        print("[AXP2101] PMU status 1 at startup", bin(pmu_status))

        # Set vbus voltage limit to 4.36v
        # Register 0x15 is Input voltage limit control.
        # A value of 6 means 4.36v as volts = 3.88 + value * 0.08
        # This should be the default.
        self.write(0x15,6)

        # Read it back.
        v = self.read(0x15)
        print("[AXP2101] vbus voltage limit set to", 3.88+v*0.08)

        # Set input current limit to 100ma. The value for 100ma is just 0,
        # and the regsiter 0x16 is "Input current limit control".
        self.write(0x16,0)

        # Set the voltage to sense in order to power-off the device.
        # we set it to 2.6 volts, that is the minimum, corresponding
        # to a value of 0 written in the 0x24 register named
        # "Vsys voltage for PWROFF threshold setting".
        self.write(0x24,0)

        # Now we need to set output voltages of the different output
        # "lines" we have. There are successive registers to set the
        # voltage:
        #
        # 0x92 for ALDO1 (RTC)
        # 0x93 for ALDO2 (TFT backlight)
        # 0x94 for ALDO3 (touchscreen driver)
        # 0x95 for ALDO4 (LoRa chip)
        # 0x96 for BLD01 is not used
        # 0x97 for BLD02 (drv2605, that is the haptic motor)
        #
        # We will set a current of 3.3 volts for all those.
        # The registers to value 'v' so that voltage is
        # 0.5 + (0.1*v), so to get 3.3 we need to set the register
        # to the value of 28.
        for reg in [0x92, 0x93, 0x94, 0x95, 0x97]:
            self.write(reg,28)

        # Note that while we set the voltages, currently the
        # output lines (but DC1, that powers the ESP32 and is already
        # enabled at startup) may be off, so we need to enable them.
        # Let's show the current situation by reading the folliwing
        # registers:
        # 0x90, LDOS ON/OFF control 0
        # 0x91, LDOS ON/OFF control 1
        # 0x80, DCDCS ON/OFF and DVM control
        # that is the one controlling what is ON or OFF:
        for reg in [0x90, 0x91, 0x80]:
            b = self.read(reg)
            print(f"[AXP2101] ON/OFF Control value for {hex(reg)}:", bin(b))

        # Only enable DC1 from register 0x80
        self.write(0x80,1)

        # Enable ADLO1, 2, 3, 4, BLDO2 from register 0x90
        # and disable all the rest.
        self.write(0x90,1+2+4+8+32)
        self.write(0x91,0)

        # Disable TS pin measure channel from the ADC, it
        # causes issues while charging the device.
        # This is performed clearing bit 1 from the
        # 0x30 register: ADC channel enable control.
        self.clearbit(0x30,1)

        self.setbit(0x68,0) # Enable battery detection.
        self.setbit(0x30,0) # Enable battery voltage ADC channel.
        self.setbit(0x30,2) # Enable vbus voltage ADC channel.
        self.setbit(0x30,3) # Enable system voltage ADC channel.

        # We disable all IRQs: we don't use them for now.
        self.write(0x40,0)
        self.write(0x41,0)
        self.write(0x42,0)

        # Also clear IRQ status bits, in case later we enable
        # interrupts.
        self.write(0x48,0)
        self.write(0x49,0)
        self.write(0x4A,0)

        # Disable charging led handling. The device has
        # no charging led.
        self.clearbit(0x69,0)

        # Set precharge current limit to 50ma
        #     constant current charge limit to 100ma
        #     termination of charge limit to 25ma
        self.write(0x61,2) # ma = value * 0.25ma
        self.write(0x62,4) # ma = value * 0.25ma (only up to the value of 8).
        self.write(0x63,1) # ma = value * 0.25ma

        # Charge voltage limit
        self.write(0x64,4) # 4 means limit of 4.35v

        # Charge termination voltage for the button battery (RTC)
        self.write(0x6A,7) # 2.6v + (0.1 * value) = 2.6+0.1*7 = 3.3v

        # Enable button battery charge.
        self.setbit(0x18,2) # Bit 2 is "Button battery charge enabled"

if  __name__ == "__main__":
    twatch_pmu = AXP2101()
    twatch_pmu.twatch_s3_poweron()
    print("[AXP2101] Battery voltage is", twatch_pmu.get_battery_voltage())
