from entity import Entity

class Worker (Entity):
    def __init__(self, ctx, name="Worker", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0

    def lastbitrecv(self, packet):
        Entity.lastbitrecv(self, packet)
        node_name = self.name
        
        if not packet.MF:
            self.received_packets += 1
            if self.ctx.sendschedule[node_name] and self.received_packets == len(self.ctx.pses):
                print "%s has received all gradients at time %0.3f" % (self.name, self.ctx.now)
                for arr in self.ctx.sendschedule[node_name]:
                    self.ctx.schedule_send(arr[0], arr[1], self.name, arr[2], name=arr[3]+"."+self.name)
