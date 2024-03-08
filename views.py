# Copyright (C) 2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

# This file contains other minor views used by FreakWAN to show
# information on the display. The main terminal-alike view, that is
# the "Scroller", is in scroller.py, while the splash screen view
# used at startup is in splash.py.

import time

class NodesListView:
    def __init__(self,fw,display):
        self.fw = fw # Reference to the application object.
        self.display = display
        self.page = 0 # At each refresh, a different page is shown.
        self.page_change_time = None # Set at first refresh & page change.
        self.items_per_page = None # Will be set after the first refresh.

    def refresh(self):
        if not self.display: return
        if self.page_change_time == None:
            self.page_change_time = time.ticks_ms()

        self.display.fill(0)
        self.display.text("Nodes seen",0,0,1)
        self.display.line(0,10,self.display.width-1,10,1)
        neigh = self.fw.neighbors

        # Select next page at each refresh. Wrap around when
        # we already displayed them all.
        if self.items_per_page != None and \
           time.ticks_diff(time.ticks_ms(),self.page_change_time) > 8000:
            self.page += 1
            if self.page * self.items_per_page >= len(neigh):
                self.page = 0
            self.page_change_time = time.ticks_ms()
        print("page",self.page)

        # Render the list of nodes for this page.
        y = 12
        item_id = 0
        for node_id, m in neigh.items():
            # Only show items belonging to this page.
            if self.items_per_page == None or \
               item_id >= self.page*self.items_per_page:
                self.display.text(f"{item_id+1} {m.nick}({m.seen})",0,y,1)
                y += 8
                if y+7 >= self.display.height: break
            item_id += 1
        self.display.contrast(255)
        self.display.show()

        # Set the items_per_page if this is the first refresh.
        if self.items_per_page == None:
            while y+7 < self.display.height: # Virtually reach end of screen.
                y += 8
                item_id += 1
            self.items_per_page = item_id + 1

    def min_refresh_time(self):
        return 5
