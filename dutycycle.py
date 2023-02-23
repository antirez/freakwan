# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import time

# This class is used in order to track the duty cycle of the
# LoRa radio. Each time the TX is activated, we need to call
# the start_tx() method. When the TX ends we call end_tx().
# By doing so, we can use get_duty_cycle() to obtain a float
# number from to 0 to 100 expressing the percentage of time
# the TX was active.
#
# The algorithm divides the time in self.slots_num slots each
# of the duration of self.slots_dur seconds. They default to
# 4 slots of 15 minutes. Each slot knows the total tx time
# during that slot, in milliseconds. When we call get_duty_cycle()
# the class will perform the average of the slots.
class DutyCycle:
    def __init__(self,slots_num=4,slots_dur=60*15):
        self.slots_dur = slots_dur
        self.slots_num = slots_num
        # Allocate our slots. The txtime is the number of milliseconds
        # we transmitted during that slot. About 'epoch', see the
        # self.get_epoch() method for more info.
        #
        # We initialize the epochs to -1 to mark the slots
        # as invalid, so that the algorithm will not count them
        # before they are populated with actual data.
        self.slots = [{'txtime':0,'epoch':-1} for i in range(self.slots_num)]
        self.tx_start_time = -1 # time.ticks_ms() of start_tx() call.

    #  Return the current active slot. This is just the UNIX time
    # divided by the slot duration, modulo the number of slots. So
    # every self.slots_dur seconds it will increment, then wrap
    # around (because of the modulo).
    def get_slot_index(self):
        return self.get_epoch() % self.slots_num

    # Get an integer that increments once every self.slots_dur. We
    # know if a given slot was incremented recently, or if at this point
    # it went out of the time window, just by checking the epoch associated
    # with the slot. Each time we increment a slot, we set the epoch,
    # and if the epoch changed, we reset the time counter.
    def get_epoch(self):
        return int(time.time()/self.slots_dur)

    def start_tx(self):
        self.tx_start_time = time.ticks_ms()

    def get_current_tx_time(self):
        if self.tx_start_time == -1: return 0
        return time.ticks_diff(time.ticks_ms(),self.tx_start_time)

    def end_tx(self):
        txtime = self.get_current_tx_time()
        idx = self.get_slot_index()
        epoch = self.get_epoch()
        slot = self.slots[idx]
        if slot['epoch'] != epoch:
            slot['epoch'] = epoch
            slot['txtime'] = 0
        slot['txtime'] += txtime
        self.tx_start_time = -1

    def get_duty_cycle(self):
        txtime = 0
        epoch = self.get_epoch()
        valid_slots = 0
        for slot in self.slots:
            # Add the time of slots yet not out of scope
            if slot['epoch'] > max(epoch-self.slots_num,0):
                txtime += slot['txtime']
                valid_slots += 1
        if valid_slots == 0: return 0
        return (txtime / (self.slots_dur*valid_slots*1000)) * 100

if __name__ == "__main__":
    d = DutyCycle(slots_num=4,slots_dur=10)
    while True:
        d.start_tx()
        time.sleep(0.1)
        d.end_tx()
        time.sleep(.9)
        # Should converge to 10%
        print(d.slots)
        print(d.get_duty_cycle())
