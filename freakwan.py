import machine
import ssd1306, sx1276, time, urandom, struct
from machine import Pin, SoftI2C

class Message:
    def __init__(self, sender, text, uid=False, ttl=3):
        self.sender = sender
        self.text = text
        self.uid = uid if uid != False else self.gen_uid()
        self.ttl = ttl

    def gen_uid(self):
        return urandom.getrandbits(32)

    def encode(self):
        return struct.pack("LB",self.uid,self.ttl)+self.sender+":"+self.text

    def decode(self,msg):
        try:
            self.uid,self.ttl = stuct.unpack("LB",msg)
            self.sender,self.text = str(msg[5:]).split(":")
            return True
        except Exception as e:
            return False

class FreakWAN:
    def __init__(self):
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

        # Init LoRa chip
        self.lora = sx1276.SX1276(LYLIGO_216_pinconfig,self.receive_callback)
        self.lora.begin()
        self.lora.configure(869500000,500000,8,12)

        # Start receiving. This will just install the IRQ
        # handler, without blocking the program.
        self.lora.receive()

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

    def receive_callback(self,lora_instance,packet,RSSI):
        self.display.fill(0)
        self.display.text(packet, 0, 0, 1)
        self.display.text(str(RSSI), 0, 15, 1)
        self.display.show()

    def run(self):
        counter = 0
        while True:
            msg = Message(sender=self.device_hw_nick(),
                         text="Hi "+str(counter))
            self.lora.send(msg.encode())
            time.sleep(5) 
            counter += 1

fw = FreakWAN()
fw.run()
