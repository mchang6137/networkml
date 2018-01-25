class Link (object):

    def __init__(self, ctx, left, right, bandwidth=0, latency=1):
        self.left = left
        self.right = right
        self.left.add_link(self, right)
        self.right.add_link(self, left)
        self.bandwidth = bandwidth
        self.latency = latency
    
    def send(self, packet):
        ctx.schedule_task(packet.size / self.bandwidth + self.latency)
