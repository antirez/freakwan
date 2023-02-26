# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import usocket, network, time, uasyncio

# Minimal IRC protocol chat example:
#
# USER lora1234 8 * :FreakWAN Device
# NICK lora1234
#
# PING :\gsYQfum`R
# PONG :\gsYQfum`R
#
# JOIN #test1234
# PRIVMSG #test1234 hey
# :antirez83728!~antirez83@freenode-bj0.sp3.osjlkk.IP JOIN :#test1234
# :antirez83728!~antirez83@freenode-bj0.sp3.osjlkk.IP PRIVMSG #test1234 :Hello

class IRC:
    def __init__(self,nick,host="irc.libera.chat",port=6667):
        self.host=host
        self.port=port
        self.nick=nick
        self.connected = False

    # Connect to the IRC server.
    def connect(self):
        ai = usocket.getaddrinfo(self.host, self.port, 0, usocket.SOCK_STREAM)
        ai = ai[0]
        self.socket = usocket.socket(ai[0], usocket.SOCK_STREAM, ai[2])
        
        # Setting timeout may fail. Not implemented in all the platforms.
        try:
            self.socket.settimeout(1000)
        except:
            pass
        self.socket.connect(ai[-1])
        self.rbuf = b'' # Read buffer
        self.wbuf = b'' # Write buffer

    def disconnect(self):
        self.socket.close()
        self.connected = False
        self.rbuf = b''
        self.wbuf = b''

    # Register to the server.
    def register(self):
        self.socket.write(b"USER %s 8 * :FreakWAN Device\r\n" % self.nick)
        self.socket.write(b"NICK %s\r\n" % self.nick)
        self.socket.write(b"JOIN #%s-%s\r\n" % ("FreakWAN-",self.nick))

    # Write to the IRC server. Here we just do buffering. Actual writing
    # is performing to flush_write_buffer().
    def write(self,data):
        if not self.connected: return
        self.wbuf += data

    # Try to write our pending write buffer, if any. And leave
    # the part we were not able to transfer to the socket still in the
    # buffer for the next time.
    def flush_write_buffer(self):
        if len(self.wbuf) == 0: return
        try:
            written = self.socket.write(self.wbuf)
            self.wbuf = self.wbuf[written:]
        except:
            # Detect socket errors in the read path.
            pass

    # Main loop: wait for server data, react to it.
    async def run(self):
        while True:
            # Reconnect if needed
            if not self.connected:
                print("[IRC] Connecting to server...")
                try:
                    self.connect()
                    self.register()
                    self.socket.setblocking(False)
                    self.connected = True
                except Exception as e:
                    print("[IRC] Error connecting: "+str(e))
                    await asyncio.sleep(5)
                    continue

            # Read data from server
            try:
                l = self.socket.read()
            except Exception as e:
                printf("[IRC] Disconnected: "+str(e))
                self.disconnect()
                continue
            
            # If no data is available, the best we can do is sleeping,
            # as uasyncio does not support awaiting sockets. Anyway this
            # code path is not very delay sensitive, and replying to the
            # user 200 milliseconds later is not going to ruin the experience.
            if not l:
                await asyncio.sleep(.2)
                continue

            # We need to accumulate data till we find "\r\n", and
            # accumulate the last unfinished line.
            self.rbuf += l
            while True:
                idx = self.rbuf.find(b'\r\n')
                if idx == -1: break
                line = self.rbuf[:idx]
                print(line)
                self.rbuf = self.rbuf[idx+2:]

            # Send data to the server.
            self.flush_write_buffer()

if __name__ == "__main__":
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        sta_if.active(True)
        sta_if.connect('Suite 2', '23041972')
        while not sta_if.isconnected():
            print("Waiting for wifi connection...")
            time.sleep(1)

    irc = IRC("test1234")
    asyncio.run(irc.run())
