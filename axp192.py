from machine import Pin, SoftI2C

class AXP192:
    def __init__(self, i2c):
        self.i2c = i2c
        self.i2c_addr = 0x34
        self.write(0x84,int("0b11110010")) # ADC sampling rate: 200hz
        self.write(0x82,0xff) # All ADCs enabled.

    def read_12bit(self,reg):
        b = self.i2c.readfrom_mem(self.i2c_addr,reg,2)
        return (b[0]<<4 | b[1])

    def write(self,reg,val):
        b = bytearray(1)
        b[0] = val
        self.i2c.writeto_mem(self.i2c_addr,reg,b)

    def get_battery_volts(self):
        volts = self.read_12bit(0x78) * 1.1 / 1000.0
        return volts

if __name__ == "__main__":
    i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
    axp = AXP192(i2c)
    print(axp.get_battery_volts())
