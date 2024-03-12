# Copyright (C) 2023-2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import cryptolib, hashlib, os, urandom
from message import *
from hmac import HMAC_SHA256

# This class implements the packets encryption keychain. It loads and
# saves keys from/to disk, and implements encryption and decryption.
class Keychain:
    def __init__(self,keychain_dir="keys"):
        try: os.mkdir(keychain_dir)
        except: pass
        self.keychain_dir = keychain_dir
        self.load_keys()

    # Load keys in memory.
    def load_keys(self):
        self.keys = {}  # Map "key name" -> SHA256(key)
        for key_name in os.listdir(self.keychain_dir):
            try:
                f = open(self.keychain_dir+"/"+key_name,'rb')
                key = f.read()
                f.close()
                self.keys[key_name] = self.sha16(key)
            except: pass

    # Return all the available key names
    def list_keys(self):
        return os.listdir(self.keychain_dir)

    # Delete the specified key
    def del_key(self,key_name):
        try: os.unlink(self.keychain_dir+"/"+key_name)
        except: pass
        del self.keys[key_name]

    # Add a new key into the keychain, overwriting an old one
    # with the same name if any.
    def add_key(self,key_name,key):
        f = open(self.keychain_dir+"/"+key_name,'wb')
        f.write(key)
        f.close()
        self.load_keys()

    # Return True if the key exists.
    def has_key(self,key_name):
        return self.keys.get(key_name) != None

    # Given a key, derive two keys, one for AES and the other
    # for the HMAC.
    def derive_keys(self,key):
        return HMAC_SHA256(key,"AES14159265358979323846")[:16], \
               HMAC_SHA256(key,"MAC26433832795028841971")

    # Return the SHA256 digest truncated to 16 bytes
    def sha16(self,data):
        return hashlib.sha256(data).digest()[:16]

    # This function expects an already encoded data packet, and
    # return its encrypted version.
    def encrypt(self,packet,key_name):
        key = self.keys.get(key_name)
        if key == None:
            raise Exception("No key with the specified name: "+str(key_name))

        # Derive the encryption and HMAC keys.
        aes_key,hmac_key = self.derive_keys(key)

        # Create an empty bytearray that will contain the encrypted
        # packet. The size is not the same as the original packet:
        # we have the padding needed to encrypt the data section
        # and the 10 bytes HMAC at the end
        data_len = len(packet)-7 # 7 bytes plaintext header.
        padding_len = (16 - data_len % 16) % 16
        encr_len = 4+len(packet)+padding_len+10 # 4 is the 32bit IV field
        encr = bytearray(encr_len)

        # Copy header information.
        encr[0] = packet[0] # Packet type.
        encr[1] = packet[1] & (0xff^MessageFlagsRelayed) # Flags, but Relayed.
        encr[2:6] = packet[2:6] # Sender ID
        encr[6] = 0             # TTL. Set to zero for HMAC.

        # Set the 4 IV bytes.
        for i in range(7,11): encr[i] = urandom.getrandbits(8)

        # Set plaintext data: here we will actually store the ciphertext
        # but we use it as a buffer for zero-padding.
        encr[11:11+data_len] = packet[7:7+data_len]

        # The actual initialization fector includes all the first 11
        # bytes, and is the truncated SHA256.
        iv = self.sha16(encr[:11])

        # Encrypt the payload. The 2 argument below means CBC mode.
        encr_payload = cryptolib.aes(aes_key,2,iv).encrypt(encr[11:-10])
        encr[11:-10] = encr_payload

        # Compute HMAC and store the first 10 bytes at the end
        # of the packet. Last 4 bits are used for padding length.
        hm = HMAC_SHA256(hmac_key,encr[:-10])[:10]
        encr[-10:] = hm
        encr[-1] = (encr[-1] & 0xf0) | padding_len

        # Fix header with right flags & TTL.
        encr[1] = packet[1]
        encr[6] = packet[6]
        return encr

    # Try every possible key, trying to decrypt the packet. Is
    # no match is found, None is returned, otherwise the method returns
    # a two items array: [key_name, decripted_packet].
    def decrypt(self,encr):
        if len(encr) < 11 + 1 + 10:
            return None # Min length is 11 (header) + some data + 10 (HMAC).

        copy = bytearray(encr)
        copy[1] = copy[1] & (0xff^MessageFlagsRelayed) # Clear Relayed.
        copy[6] = 0 # TTL. Set to zero for HMAC.
        padlen = copy[-1] & 0x0f # Padding length.
        copy[-1] = copy[-1] & 0xf0 # Clear padding len field.
        hm = copy[-10:] # The HMAC part: we will check it against our HMAC.

        # Test every key for a matching HMAC.
        for key_name in self.keys:
            key = self.keys[key_name]

            # Derive the encryption and HMAC keys.
            aes_key,hmac_key = self.derive_keys(key)
            my_hm = bytearray(HMAC_SHA256(hmac_key,copy[:-10])[:10])
            my_hm[-1] = my_hm[-1] & 0xf0
            if hm != my_hm: continue # No match.

            # Decrypt the payload
            iv = self.sha16(copy[:11])
            plain = cryptolib.aes(aes_key,2,iv).decrypt(encr[11:-10])

            # Compose the final decrypted packet removing the IV
            # field, the padding and the HMAC.
            orig = bytearray(7 + len(plain) - padlen)
            orig[:7] = encr[:7]
            orig[7:] = plain if padlen == 0 else plain[:-padlen]
            return (key_name,orig)
        return None

if __name__ == "__main__":
    kc = Keychain()
    kc.add_key("freaknet","morte")
    test_packets = [
        b"TF" + "IDID" + "T" + "SENDER" + "foo: bar 0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF",
        b'\x00\x12\xc9~\xdb\x98\x0f\x0c\x8b\x95\xa9\xe70\x06ant433foo'
    ]
    for testnum,test_packet in enumerate(test_packets):
        print("Packet",testnum+1)
        encr = kc.encrypt(test_packet,"freaknet")
        decr = kc.decrypt(encr)
        if test_packet == decr[1]:
            print("OK: Packet encrypted and decrypred with success: got same bytes")
        else:
            print("ERR: decrypted packet is not the same:", test_packet, decr[1])
        # Flipping a bit somewhere should no longer result in a valid packet
        corrupted = encr[:18] + bytes([encr[18]^1]) + encr[19:]
        decr = kc.decrypt(corrupted)
        if decr == None:
            print("OK: Corrupted packet correctly refused")
