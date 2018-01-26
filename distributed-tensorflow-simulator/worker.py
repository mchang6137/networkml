from entity import Entity

class Worker (Entity):
    def __init__(self, ctx, name="Worker", inbuffer_size=0, fwd_pass_time=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.fwd_pass_time = fwd_pass_time

    def lastbitrecv(self, packet):
        Entity.lastbitrecv(self, packet)
        node_name = self.name
        
        if not packet.MF:
            self.received_packets += 1
            if self.ctx.sendschedule[node_name] and self.received_packets == self.ctx.num_from_ps:
                if self.ctx.verbosity:
                    print "%s has received all gradients at time %0.3f" % (self.name, self.ctx.now)
                self.ctx.worker_receive.append(self.ctx.now)
                if self.ctx.now >= self.fwd_pass_time:
                    for arr in self.ctx.sendschedule[node_name]:
                        self.ctx.schedule_send(arr[0], arr[1], self.name, arr[2], name=arr[3])
                else:
                    wait_time = self.fwd_pass_time - self.ctx.now
                    print 'Worker {} still waiting {} sec for forward pass to complete'.format(self.name, wait_time)
                    for arr in self.ctx.sendschedule[node_name]:
                        time_delta = arr[0] + wait_time
                        self.ctx.schedule_send(time_delta, arr[1], self.name, arr[2], name=arr[3])
                    
