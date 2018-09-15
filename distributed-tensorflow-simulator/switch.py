from entity import Entity

class Switch (Entity):
    def __init__(self, ctx, name="switch", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.in_network = {}
        self.received_packets = {}

    def lastbitrecv(self, packet):
        if str(self) == packet.dest:
            if not packet.MF:
                pass
                #print "packet %s fully received by destination %s at time %0.3f" % (packet, self, self.ctx.now)
            packet.time_received = self.ctx.now
        else:
            if not packet.MF:
                pass
                #print "packet %s fully received by %s at time %0.3f" % (packet, self, self.ctx.now)
            if packet.dest not in self.ctx.pses or not packet.netagg:
                self.queuesend(packet)
            elif not packet.MF:
                if packet.name not in self.received_packets:
                    self.received_packets[packet.name] = 0
                self.received_packets[packet.name] += packet.degree
                if self.received_packets[packet.name] == self.in_network[packet.name]:
                    packet.size = self.ctx.edge_weights[packet.name]
                    packet.degree = self.in_network[packet.name]
                    self.queuesend(packet)
                    if self.ctx.multi_step:
                        self.received_packets[packet.name] = 0