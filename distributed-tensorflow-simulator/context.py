import Queue
import random
from packet import Packet
from entity import Entity
from ps import PS

class Context (object):
    def __init__(self):
        self.queue = Queue.PriorityQueue()
        self.current_time = 0
        self.final_time = -1
        self.objs = {}
        self.internal_latency = 0
        self.latency_distribution = "none"
        self.latency_std = 0
        self.num_racks = 0
        self.paths = {}
        self.racks = {}
        self.workers = []
        self.pses = []
        self.tors = []
        self.gswitches = []
        self.use_multicast = False

    def schedule_task(self, delta, task):
        self.queue.put_nowait((self.current_time + delta, task))

    def schedule_task_at(self, time, task):
        self.queue.put_nowait((time, task))

    @property
    def now(self):
        return self.current_time

    @property
    def latency(self):
        if self.latency_distribution == "uniform":
            mlatency = self.internal_latency + random.uniform(-self.latency_std,self.latency_std)
        elif self.latency_distribution == "standard":
            mlatency =  random.normalvariate(self.internal_latency, self.latency_std)
        else:
            mlatency = self.internal_latency
        if mlatency < 0:
            print "Latency cannot result in a negative value, but was {}".format(mlatency)
            exit(1)
            mlatency = 0
        return mlatency

    def run(self):
        while not self.queue.empty() and (self.final_time == -1 or self.current_time < self.final_time):
            (time, task) = self.queue.get_nowait()
            self.current_time = time
            task()
        self.final_time = self.current_time

    def schedule_send(self, delta, size, src, dest, name=""):
        if src == dest and not self.use_multicast:
            for dest in self.workers:
                self.schedule_send_internal(delta, size, src, dest, name=name)
        else:
            self.schedule_send_internal(delta, size, src, dest, name=name)

    def schedule_send_internal(self, delta, size, src, dest, name=""):
        mpacket = Packet(size, src=src, dest=dest, name=name)
        mpacket.time_send = delta
        mpacket.path = self.paths[src + dest]
        if src == dest:
            mpacket.multicast = True
        self.schedule_task(delta, lambda: self.objs[src].queuesend(mpacket))

    def schedule_recv(self, delta, packet):
        self.schedule_task(delta, lambda: self.objs[packet.dest].recv(packet))