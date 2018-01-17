import context
import Queue

class Entity (object):
    def __init__(self, ctx, name="Entity", inbuffer_size=0):
        self.ctx = ctx
        self.name = name
        self.outbuffer = {}
        self.send_rate = -1
        self.recv_rate = -1
        self.used_outbuffer = {}
        self.rack = 0
        self.used_inbuffer = 0
        self.inbuffer = Queue.Queue(maxsize=inbuffer_size)
        self.inbuffer_size = inbuffer_size

    def __str__(self):
        return self.name

    def queuesend(self, packet):
        while packet.size > self.ctx.MTU:
            opacket = packet.copy()
            opacket.MF = True
            opacket.size = self.ctx.MTU
            self.queuesend(opacket)
            packet.part += 1
            packet.size -= self.ctx.MTU
        if packet.part == 0:
            pass
            #print "packet %s queued to send by %s to %s at time %0.3f" % (packet, self, packet.dest, self.ctx.now)
        if packet.multicast:
            if self.name == packet.src:
                nexthop = "TOR" + str(self.rack)
                self.sendto(packet, nexthop)
            elif self.ctx.objs[packet.src].rack == self.rack:
                for dest in self.ctx.racks[self.rack]:
                    if dest not in self.ctx.workers:
                        continue
                    opacket = packet.copy()
                    opacket.dest = dest
                    opacket.multicast = False
                    opacket.path = self.ctx.paths[packet.src + dest]
                    self.queuesend(opacket)
                nexthop = "GSwitch0"
                self.sendto(packet, nexthop)
            elif self.rack == -1:
                for count in range(len(self.ctx.racks)):
                    if count != self.ctx.objs[packet.src].rack:
                        opacket = packet.copy()
			self.sendto(opacket, "TOR" + str(count))
            else:
                for dest in self.ctx.racks[self.rack]:
                    if dest not in self.ctx.workers:
                        continue
                    opacket = packet.copy()
                    opacket.dest = dest
                    opacket.multicast = False
                    opacket.path = self.ctx.paths[packet.src + dest]
                    self.queuesend(opacket)
        else:
            path = packet.path
            nexthop = path[path.index(self.name) + 1]
            self.sendto(packet, nexthop)

    def sendto(self, packet, nexthop):
        packet.prevhop = self.name
        packet.nexthop = nexthop
        nextobj = self.ctx.objs[nexthop]
        if self.send_rate == -1 and nextobj.recv_rate == -1:
            self.send(packet)
        else:
            if nexthop not in self.outbuffer:
                self.outbuffer[nexthop] = Queue.Queue()
            if nexthop not in self.used_outbuffer:
                self.used_outbuffer[nexthop] = 0
            self.used_outbuffer[nexthop] += packet.size
            if self.used_outbuffer[nexthop] == packet.size:
                self.send(packet)
            else:
                self.outbuffer[nexthop].put(packet)

    def send(self, packet):
        nexthop = packet.nexthop
        nextobj = self.ctx.objs[nexthop]
        if packet.part == 0:
            pass
            #print "packet %s sent by %s to %s at time %0.3f" % (packet, self, str(nexthop), self.ctx.now)
        ping = self.ctx.latency
        self.ctx.schedule_task(ping, lambda: nextobj.recv(packet))
        rate = min(self.send_rate, nextobj.recv_rate)
        if rate == -1:
            rate = max(self.send_rate, nextobj.recv_rate)
        delta = packet.size / rate
        if rate == -1:
            delta = 0
        self.ctx.schedule_task(delta, lambda: self.finishsend(packet))

    def finishsend(self, packet):
        nexthop = packet.nexthop
        nextobj = self.ctx.objs[nexthop]
        if not packet.MF:
            pass
            #print "packet %s finished sending from %s to %s at time %0.3f" % (packet, self, str(nexthop), self.ctx.now)
        rate = min(self.send_rate, nextobj.recv_rate)
        if rate == -1:
            rate = max(self.send_rate, nextobj.recv_rate)
        if rate != -1:
            self.used_outbuffer[nexthop] -= packet.size
        if not self.outbuffer[nexthop].empty():
            nextpacket = self.outbuffer[nexthop].get()
            self.send(nextpacket)

    def recv(self, packet):
        lasthop = packet.prevhop
        lastobj = self.ctx.objs[lasthop]
        if self.inbuffer_size == -1 or self.used_inbuffer < self.inbuffer_size:
            rate = min(self.recv_rate, lastobj.send_rate)
            if rate == -1:
                rate = max(self.recv_rate, lastobj.send_rate)
            if packet.part == 0:
                pass
                #print "packet %s started to be received by %s at time %0.3f" % (packet, self, self.ctx.now)
            delta = packet.size / rate
            if rate == -1:
                delta = 0
            self.ctx.schedule_task(delta, lambda: self.lastbitrecv(packet))
        else:
            resend_time = max(packet.time_send + self.ctx.timeout, self.ctx.now)
            self.ctx.schedule_task_at(resend_time, lambda: self.ctx.objs[packet.src].queuesend(packet))
            print "packet %s dropped by %s at time %0.3f" % (packet, self, self.ctx.now)

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
            self.queuesend(packet)
