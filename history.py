# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import os, struct

# This class implements an append only history file. In order to
# avoid any seek, and in general to demand too much to the very
# rudimental filesystem of the ESP32, we use two files, and always
# append to one of them, up 'histlen+1' entries are reached.
#
# Files are created inside the specified folder, and are called
# hist1 and hist2. We append to only one of the two. Our records
# are fixed length, so just from the file length we can know how
# many items each file contains, and we can seek at fixed offsets
# in order to read specific items.
#
# This is how the append algorithm works:
#
# To select where to append among hist1 and hist2:
# * If no file exists, we append to hist1.
# * If only a single file exists, we use it if it has less than histlen+1
#   entries.
# * If only a single file exists, but it reached histlen+1 len (or more), we
#   append to the other file (creating it).
# * If two files exist, we pick the shortest one, that is the only one
#   that didn't yet reach histlen+1 entries. In case of corruptions or
#   bugs, and we found both files having the same length, we use the
#   first file. In case the histlen changed and now even the shortest file is
#   larger than histlen+1, we still select the shortest file among the two,
#   and append there.
#
# To append to the selected file:
# * When we append a new entry to the selected file, if appending to it
#   will make it reach histlen+1 or more (can happen if histlen changed)
#   entires, we delete the other file, then append.
#
# To read entries from the history files:
# * If there is only one file, it contains the latest N entries.
# * If there are two files, the longer contains the oldest N
#   messages and the shortest contains additional M newest messages. So
#   the algorithm knows to have a total history of M+N and will seek
#   in one or the other file according to the requested index. Entries
#   indexes, to retrieve the history, are specified as indexes from the
#   newest to the oldest entry. So an index of 0 means the newest entry
#   stored, 1 is the previous one, and so forth.
#
# This way we are sure that at least 'histlen' entries are always stored
# on disk, just using two operations: append only writes and file deletion.
class History:
    def __init__(self, folder, histlen=100, recordsize=256):
        try:
            os.mkdir(folder)
        except:
            pass
        self.files = [folder+"/hist1",folder+"/hist2"]
        self.histlen = histlen
        self.recordsize = recordsize

    # Return number of records len of first and second file.
    # Non existing files are reported as 0 len.
    def get_file_size(self,file_id):
        try:
            flen = int(os.stat(self.files[file_id])[6] / (self.recordsize+4))
        except:
            flen = 0
        return flen

    # Return the ID (0 or 1) of the file we should append new entries to.
    # See algorithm in the top comment of this class.
    def select_file(self):
        len0 = self.get_file_size(0)
        len1 = self.get_file_size(1)

        # Files are the same length. Happens when no file exists (both zero)
        # or in case of corrutpions / bugs if they are non zero. Use the
        # first file.
        if len0 == len1:
            try:
                os.unlink(self.files[1])
            except:
                pass
            return 0

        # Only a single file exists. We use it if it is still within size
        # limits.
        if len0 == 0 or len1 == 0:
            file = 0 if len0 else 1
            file_len = max(len0,len1)

            if file_len <= self.histlen:
                return file
            else:
                # if we reached histlen+1, switch file.
                return (file+1)%2

        # Both files exist, select the smaller one.
        return 0 if len0 < len1 else 1

    def append(self, data):
        if (len(data) > self.recordsize):
            print("[history] Data to append is larger than record size");
            return False

        file_id = self.select_file()
        file_name = self.files[file_id]

        # Delete the other file if we are appending the last
        # entry in the current file.
        if self.get_file_size(file_id) >= self.histlen:
            try:
                os.unlink(self.files[(file_id+1)%2])
            except:
                pass

        # The only record header we have is 4 bytes of length
        # information. Our records are fixed size, so the remaning
        # space is just padding.
        padding = b'\x00' * (self.recordsize - len(data))
        record = struct.pack("<L",len(data)) + data + padding;
        f = open(file_name,'ab')
        f.write(record)
        f.close()
        return True

    # Total number of records in our history
    def get_num_records(self):
        return self.get_file_size(0)+self.get_file_size(1)

    # Return stored entries, starting at 'index' and for 'count' total
    # items (or less, if there are less entries stored than the ones
    # requested). An index of 0 means the last entry stored (so the newest)
    # 1 is the penultimate record stored and so forth. The method returns
    # an array of items.
    def get_records(self, index, count=1):
        max_records = self.get_num_records()
        if max_records == 0: return []

        # Normalize index according to actual history len
        if index >= max_records: index = max_records-1

        # Turn the index under an offset in the whole history len,
        # so that 0 would be the oldest entry stored, and so forth:
        # it makes more sense to work with offsets here, but for the API
        # it makes more sense to reason in terms of "last N items".
        index = max_records - index - 1

        # Order files according to length. We need to read from the
        # bigger file and proceed to the smaller file (if there is one)
        # and if the records count requires so.
        lens = self.get_file_size(0), self.get_file_size(1)
        if lens[0] > lens[1]:
            files = [0,1]
        else:
            files = [1,0]
            lens = lens[1],lens[0]

        # Compute how many records we take from the first
        # and second file, and at which offset.
        seek = [index,max(index-lens[0],0)]
        subcount = [max(min(lens[0]-index,count),0),0]
        subcount[1] = count - subcount[0]

        # Load results from one or both files.
        result = []
        for i in range(2):
            # print("From file %d: count:%d seek:%d" % (files[i],subcount[i],seek[i]))
            if subcount[i] == 0: continue
            f = open(self.files[files[i]],'rb')
            f.seek(seek[i]*(4+self.recordsize))
            for c in range(subcount[i]):
                rlen = struct.unpack("<L",f.read(4))[0]
                data = f.read(self.recordsize)[0:rlen]
                result.append(data)
            f.close()
        return result

    # Remove all the history
    def reset(self):
        try:
            os.unlink(self.files[0])
            os.unlink(self.files[1])
        except:
            pass

# Only useful in order to test the history API
if __name__ == "__main__":
    h = History("test_history",histlen=5,recordsize=20)
    h.reset()
    h.append(b'123')
    h.append(b'456')
    h.append(b'foo1')
    h.append(b'foo2')
    h.append(b'foo3')
    h.append(b'foo4')
    h.append(b'foo5')
    h.append(b'foo6')
    print("Current records: %d" % h.get_num_records())
    records = h.get_records(4,4) # Cross file fetch
    print(records)
    records = h.get_records(1,2)
    print(records)

    print("Adding 100 entries...")
    for i in range(100):
        h.append(bytes("entry %d" % i,'utf-8'))
    print("Current records: %d" % h.get_num_records())
    records = h.get_records(1,2)
    print(records)
