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
        self.parents = []
        self.children = []
        self.ps_branch = {}
        self.semaphore = {}

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
            #print "%s is deliberating on %s" % (self.name, packet.name)
            if self.name == packet.src:
                nexthop = self.parents[0]
                self.sendto(packet, nexthop)
                return
            if packet.src in self.ps_branch:
                if self.parents:
                    if self.ctx.objs[packet.src].root in self.parents:
                        nexthop = self.ctx.objs[packet.src].root
                    else:
                        nexthop = self.parents[0]
                    opacket = packet.copy()
                    self.sendto(opacket, nexthop)
            for dest in self.children:
                if dest in self.ctx.pses:
                    continue
                if dest in self.ctx.workers:
                    #print "removing multicast on %s to %s" % (packet.name, dest)
                    opacket = packet.copy()
                    opacket.dest = dest
                    opacket.multicast = False
                    opacket.path = self.ctx.paths[packet.src + dest]
                    self.queuesend(opacket)
                    continue
                destobj = self.ctx.objs[dest]
                if packet.src not in destobj.ps_branch and packet.src in destobj.in_network:
                    #print "forwarding %s down from %s to %s" % (packet.name, self.name, dest)
                    opacket = packet.copy()
                    self.sendto(opacket, dest)
        elif packet.netagg:
            destobj = self.ctx.objs[packet.dest]
            if self.name in self.ctx.workers:
                nexthop = self.parents[0]
                self.sendto(packet, nexthop)
            elif packet.dest not in self.ps_branch:
                if self.parents:
                    if destobj.root in self.parents:
                        nexthop = destobj.root
                    else:
                        nexthop = self.parents[0]
                    self.sendto(packet, nexthop)
            else:
                path = packet.path
                nexthop = path[path.index(self.name) + 1]
                self.sendto(packet, nexthop)
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
            if self.semaphore[nexthop] > 0:
                self.semaphore[nexthop] -= 1
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
            self.semaphore[nexthop] += 1
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
