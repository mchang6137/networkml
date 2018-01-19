from entity import Entity
import Queue

class PS (Entity):
    def __init__(self, ctx, name="PS", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.root = ""

    def lastbitrecv(self, packet):
        Entity.lastbitrecv(self, packet)
        if not packet.MF and self.name in self.ctx.ps_num_items:
            self.received_packets += packet.degree
            if self.received_packets == self.ctx.ps_num_items[self.name]:
                self.received_packets = 0
                print "%s has received all gradient updates at time %0.3f" % (self.name, self.ctx.now)

"""    
    deprecated
    def proc(self, packet):
        packet.time_processed = self.ctx.now
        self.used_inbuffer -= packet.size
        if self.recv_rate != -1:
            print "packet %s processed by %s at time %0.3f" % (packet, self, self.ctx.now)
        if self.used_inbuffer != 0:
            packet = self.inbuffer.get()
            delta = packet.size / self.recv_rate if self.recv_rate != -1 else 0
            self.ctx.schedule_task(delta, lambda: self.proc(packet))
"""