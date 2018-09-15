from entity import Entity
import random
import copy

class PS (Entity):
    def __init__(self, ctx, name="PS", inbuffer_size=0):
        Entity.__init__(self, ctx, name=name, inbuffer_size=inbuffer_size)
        self.received_packets = 0
        self.root = ""
        self.bits_sent = 0
        self.bits_received = {}
        self.bytes_hit = 0
        self.phase = 1
        self.finish_time_assigned = 0

    def lastbitrecv(self, packet):
        Entity.lastbitrecv(self, packet)
        if not packet.MF and self.name in self.ctx.ps_num_items:
            src = packet.src if not self.ctx.in_network_computation else "netagg"
            self.received_packets += max(1, packet.degree)
            if src not in self.bits_received:
                self.bits_received[src] = 0
            #print "name {}, src {}, degree {}, size {}, weight {}".format(packet.name, src, packet.degree, packet.size, self.ctx.edge_weights[packet.name])
            self.bits_received[src] += self.ctx.edge_weights[packet.name]
            # if min([val for key, val in self.bits_received.items()]) > 3000000000 and not self.bytes_hit:
            #     print "3million bytes received at time %0.3f" % (self.ctx.now)
            #     self.bytes_hit = 1
            if self.ctx.multi_step and min([val for key, val in self.bits_received.items()]) > 0 and self.bits_sent == 0 and self.phase == 1:
                self.ctx.start_time = self.ctx.now
            if self.ctx.multi_step and min([val for key, val in self.bits_received.items()]) > 0 and self.bits_sent == 0 and not self.finish_time_assigned:
                self.ctx.finish_time = self.ctx.now
                self.finish_time_assigned = 1
            if self.ctx.multi_step and self.phase < self.ctx.multi_step:
                self.redistribute()
            if self.received_packets == self.ctx.ps_num_items[self.name]:
                if self.ctx.verbosity:
                    print "%s has received all gradient updates at time %0.3f" % (self.name, self.ctx.now)
                    print "{} bits received".format(min([val for key, val in self.bits_received.items()]))
                if self.ctx.multi_step and self.phase < self.ctx.multi_step:
                    #self.distribute()
                    self.phase += 1
                    self.bits_received = {}
                    self.bits_sent = 0
                    self.received_packets = 0
                    self.finish_time_assigned = 0

    def redistribute(self):
        base = 0
        if not self.ctx.in_network_computation and len(self.bits_received) != len(self.ctx.workers):
            return
        bit_recv = min([val for key, val in self.bits_received.items()])
        if self.ctx.use_multicast:
            for arr in self.ctx.sendschedule[self.name]:
                if base + arr[0] > self.bits_sent and \
                        (base + arr[0] < bit_recv or self.received_packets == self.ctx.ps_num_items[self.name]):
                    self.queuesend(self.ctx.make_packet(arr[0], self.name, self.name, name=arr[1]))
                    self.bits_sent += arr[0]
                base += arr[0]
        else:
            #print self.name + ":\t" + str(len(self.ctx.sendschedule[self.name]))
            if self.ctx.striping:
                for arr in self.ctx.sendschedule[self.name]:
                    if base + arr[0] > self.bits_sent and \
                            (base + arr[0] <= bit_recv or self.received_packets == self.ctx.ps_num_items[self.name]):
                        random_wk_list = copy.deepcopy(self.ctx.workers)
                        random.shuffle(random_wk_list)
                        for wk_name in random_wk_list:
                            self.queuesend(self.ctx.make_packet(arr[0], self.name, wk_name, name=arr[1]))
                        self.bits_sent += arr[0]
                        #print "re-sent {} bits at {}".format(self.bits_sent, self.ctx.now)
                    base += arr[0]

    def distribute(self):
        #print '{}:\n\t{}'.format(self.name, self.ctx.sendschedule[self.name])
        if self.ctx.use_multicast:
            for arr in self.ctx.sendschedule[self.name]:
                self.queuesend(self.ctx.make_packet(arr[0], self.name, self.name, name=arr[1]))
        else:
            #print self.name + ":\t" + str(len(self.ctx.sendschedule[self.name]))
            if self.ctx.real_distribution:
                for arr in self.ctx.sendschedule[self.name]:
                    self.queuesend(self.ctx.make_packet(arr[0], self.name, arr[2], name=arr[1]))
            elif self.ctx.striping:
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
