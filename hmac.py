# Copyright (C) 2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import hashlib

# RFC 2104 HMAC-SHA256.
def HMAC_SHA256(key,msg):
    ipad = bytearray(64)
    opad = bytearray(64)
    if isinstance(key,str): key = key.encode()
    keylen = len(key)
    if keylen > 64: raise ValueError("Key is too big.")
    for i in range(64):
        if i < keylen:
            ipad[i] = key[i] ^ 0x36
            opad[i] = key[i] ^ 0x5c
        else:
            ipad[i],opad[i] = 0x36, 0x5c
    # The following is equivalent to:
    # hashlib.sha256(opad+hashlib.sha256(ipad+msg.encode()).digest())
    # But will perform less allocation.
    h = hashlib.sha256(opad)
    h2 = hashlib.sha256(ipad)
    h2.update(msg)
    h.update(h2.digest())
    return h.digest()

if __name__ == "__main__":
    # RFC 4231 test vectors.
    testvectors = [
    {'key': "\x0b"*20,
     'txt': "Hi There",
     'mac': "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"},
    {'key': "Jefe",
     'txt': "what do ya want for nothing?",
     'mac': "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"},
    ]

    for tv in testvectors:
        h = HMAC_SHA256(tv['key'],tv['txt'])
        print(tv['mac'])
        print(h.hex())
