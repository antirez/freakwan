# Copyright (C) 2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

# This file contains other minor views used by FreakWAN to show
# information on the display. The main terminal-alike view, that is
# the "Scroller", is in scroller.py, while the splash screen view
# used at startup is in splash.py.

class NodesListView:
    def __init__(self,fw,display):
        self.fw = fw # Reference to the application object.
        self.display = display

    def refresh(self):
        if not self.display: return
        self.display.fill(0)
        self.display.text("Nodes seen",0,0,1)
        self.display.line(0,10,self.display.width-1,10,1)
        y = 12 
        for node_id, m in self.fw.neighbors.items():
            self.display.text(m.nick,0,y,1)
            y += 8
            if y >= self.display.height: break
        self.display.contrast(255)
        self.display.show()

    def min_refresh_time(self):
        return 5
