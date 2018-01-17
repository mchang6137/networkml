from entity import Entity

class TOR (Entity):
    def __init__(self, ctx, name="TOR", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.fromworkers = {}

    def lastbitrecv(self, packet):
        if packet.src not in self.ctx.workers or not self.ctx.in_network_computation:
            Entity.lastbitrecv(self, packet)
        else:
            if not packet.MF:
                self.fromworkers[packet.name]
