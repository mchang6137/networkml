class Packet (object):
    def __init__(self, size=0, src="", dest="", name = ""):
        self.time_send = -1
        self.time_received = -1
        self.size = size
        self.src = src
        self.dest = dest
        self.path = []
        self.MF = False
        self.part = 0
        self.multicast = False
        self.prevhop = None
        self.nexthop = None
        self.degree = 1
        self.netagg = False
        if name != "":
            self.name = name
        else:
            self.name = src + "->" + dest + "x" + str(size)
    
    def __str__(self):
        #if self.part != 0 or self.MF:
        if self.MF:
            return self.name + "." + str(self.part)
        return self.name

    def copy(self):
        opacket = Packet()
        opacket.time_send = self.time_send
        opacket.time_received = self.time_received
        opacket.size = self.size
        opacket.src = self.src
        opacket.dest = self.dest
        opacket.path = self.path
        opacket.MF = self.MF
        opacket.part = self.part
        opacket.name = self.name
        opacket.multicast = self.multicast
        opacket.prevhop = None
        opacket.nexthop = None
        opacket.degree = self.degree
        opacket.netagg = self.netagg
        return opacket
