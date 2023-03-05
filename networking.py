# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import usocket, network, time, uasyncio as asyncio, urandom, re

# Minimal IRC protocol chat example:
#
# Registration is like that:
#   USER lora1234 8 * :FreakWAN Device
#   NICK lora1234
#
# You have to reply to pings with pongs, to avoid timing out:
#   PING :\gsYQfum`R
#   PONG :\gsYQfum`R
#
# Joining channels and sending messages to channels (or users):
#   JOIN #test1234
#   PRIVMSG #test1234 :hey
#
# Joining is confirmed:
#   :antirez83728!~antirez83@freenode-bj0.sp3.osjlkk.IP JOIN :#test1234
#
# This is how messages are received:
#   :antirez83728!~antirez83@freenode-bj0.sp3.osjlkk.IP PRIVMSG #test1234 :Hello

class IRC:
    def __init__(self,nick,callback,host="irc.libera.chat",port=6667):
        self.host=host
        self.port=port
        self.nick = nick
        self.channel="##Freakwan-"+nick
        self.connected = False
        self.active = False
        self.callback = callback # Called when receiving messages

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
        try:
            self.connected = False
            self.rbuf = b''
            self.wbuf = b''
            # Leave close() as last call so that the previous calls will
            # always get executed.
            self.socket.close()
        except:
            pass

    # Register to the server.
    def register(self):
        self.socket.write(b"USER %s 8 * :FreakWAN Device\r\n" % self.nick)
        # Use a random nickname, to avoid collisions after disconnections.
        nick="%s%d" % (self.nick,urandom.getrandbits(32))
        self.socket.write(b"NICK %s\r\n" % nick)
        self.socket.write(b"JOIN %s\r\n" % self.channel)

    # Write to the IRC server. Here we just do buffering. Actual writing
    # is performing to flush_write_buffer().
    def write(self,data):
        if not self.connected: return
        # If for some reason we can't flush the buffer to the socket, we
        # are forced to discard it. Better to accumulate the last part
        # of the buffer than the first one, so that it will contain more
        # recent messages.
        if len(self.wbuf) > 1024: self.wbuf = b''
        self.wbuf += data

    # Try to write our pending write buffer, if any. And leave
    # the part we were not able to transfer to the socket still in the
    # buffer for the next time.
    def flush_write_buffer(self):
        while True:
            if len(self.wbuf) == 0: return
            try:
                written = self.socket.write(self.wbuf)
                if written == 0: return
                self.wbuf = self.wbuf[written:]
            except:
                # Handle socket errors in the read path.
                return

    # Write a message into the bot channel
    def reply(self,reply):
        if not self.connected: return
        self.write(b"PRIVMSG %s :%s\r\n" %(self.channel,reply))

    # Receive every line from the IRC server, and does the
    # right thing according to the protocol.
    def process_line(self,line):
        # Reply to server PINGs, to avoid timing out.
        if line[:4] == b'PING':
            self.write(b'PONG'+line[4:]+b'\r\n')
            return

        # Reply to user messages
        match = b"PRIVMSG %s :" % self.channel
        idx = line.find(match)
        self.lastline = line
        if idx != -1:
            try:
                idx += len(match)
                user_msg = line[idx:].decode('utf-8')
            except Exception as e:
                print("[IRC] error processing command: "+str(e))
                pass    # Ignore wrong UTF-8 strings.
            self.callback(user_msg)
            return

        # Handle JOIN message. We don't do much with it right now,
        # just print in the logs that we (or somebody else) joined.
        v = line.split(b' ')
        if len(v) == 3 and v[1] == b'JOIN':
            v2 = v[0].split(b'!')
            if len(v2) == 2:
                nick = v2[0][1:].decode('utf-8')
                channel = v[2][1:].decode('utf-8')
                print("[IRC] %s joined %s" % (nick,channel))

    # Called to disable the IRC subsystem and abort the asynchronous
    # main loop.
    def stop(self):
        if self.active:
            # Setting active to False will also cause it to
            # disconnect, after exiting the loop.
            self.active = False
        else:
            self.disconnect()

    # Main loop: wait for server data, react to it.
    async def run(self):
        self.active = True
        while self.active:
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
                l = self.socket.read(64) # Why 64? To avoid out of memory.
            except Exception as e:
                print("[IRC] Disconnected: "+str(e))
                self.disconnect()
                continue
            
            # We need to accumulate data till we find "\r\n", and
            # accumulate the last unfinished line.
            if l:
                self.rbuf += l
                while True:
                    idx = self.rbuf.find(b'\r\n')
                    if idx == -1: break
                    line = self.rbuf[:idx]
                    self.process_line(line)
                    self.rbuf = self.rbuf[idx+2:]

            # Send data to the server
            self.flush_write_buffer()

            # If no data is available, the best we can do is sleeping,
            # as uasyncio does not support awaiting sockets. Anyway this
            # code path is not very delay sensitive, and replying to the
            # user 200 milliseconds later is not going to ruin the experience.
            if not l: await asyncio.sleep(.2)

        print("[IRC] subsystem disabeld. Exiting")
        self.disconnect()

# This class just implements what is needed in order to setup the
# wifi, check if it is currently connected, wait for the connection
# to happen and so forth.
class WiFiConnection:
    def __init__(self):
        self.interface = network.WLAN(network.STA_IF)

    def connect(self,ssid,password):
        self.interface.active(True)
        try:
            self.interface.disconnect()
        except:
            pass
        self.interface.connect(ssid,password)

    def stop(self):
        try:
            self.interface.active(False)
        except:
            pass

    def is_connected(self):
        return self.interface.isconnected()

    async def wait_for_connection(self):
        print("[WiFi] Waiting for connection...")
        while not self.interface.isconnected():
            await asyncio.sleep(1)
        print("[WiFi] Connected.")

if __name__ == "__main__":
    SSID='TestSSDI'
    password='SomePassword'
    wifi = WiFiConnection()
    wifi.connect(SSID,password)
    while not wifi.is_connected():
        print("Waiting for WiFi")
        time.sleep(1)

    irc = IRC("test1234")
    asyncio.run(irc.run())
