from entity import Entity
import random
import copy

class PS (Entity):
    def __init__(self, ctx, name="PS", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.root = ""

    def lastbitrecv(self, packet):
        Entity.lastbitrecv(self, packet)
        if not packet.MF and self.name in self.ctx.ps_num_items:
            self.received_packets += max(1, packet.degree)
            if self.received_packets == self.ctx.ps_num_items[self.name]:
                print "%s has received all gradient updates at time %0.3f" % (self.name, self.ctx.now)

    def distribute(self):
        #print '{}:\n\t{}'.format(self.name, self.ctx.sendschedule[self.name])
        if self.ctx.use_multicast:
            for arr in self.ctx.sendschedule[self.name]:
                self.queuesend(self.ctx.make_packet(arr[0], self.name, self.name, name=arr[1]))
        else:
            #print self.name + ":\t" + str(len(self.ctx.sendschedule[self.name]))
            if self.ctx.striping:
                for arr in self.ctx.sendschedule[self.name]:
                    random_wk_list = copy.deepcopy(self.ctx.workers)
                    random.shuffle(random_wk_list)
                    for wk_name in random_wk_list:
                        self.queuesend(self.ctx.make_packet(arr[0], self.name, wk_name, name=arr[1]))
            else:
                random_wk_list = copy.deepcopy(self.ctx.workers)
                random.shuffle(random_wk_list)
                for wk_name in random_wk_list:
                    for arr in self.ctx.sendschedule[self.name]:
                        self.queuesend(self.ctx.make_packet(arr[0], self.name, wk_name, name=arr[1]))

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
