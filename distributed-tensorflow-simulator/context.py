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
        self.in_network_computation = False
        self.edge_weights = {}
        self.worker_receive = []
        self.ps_num_items = {}
        self.num_from_ps = 0
        self.sendschedule = {}
        self.verbosity = 1
        self.use_optimal_param = 0
        self.horovod = 0
        self.butterfly = 0
        self.scattercast = 0
        self.multi_step = 1
        self.forward_pass_as_bytes = 0
        self.forward_pass_size = 0
        self.max_param_size = -1.0
        self.start_time = 0
        self.finish_time = 0

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
        if self.multi_step == 1:
            self.final_time = self.current_time
            if self.use_multicast and self.in_network_computation:
                self.final_time = self.finish_time
        else:
            self.final_time = self.finish_time - self.start_time
        if self.verbosity:
            for worker in self.workers:
                print '{}:\tReceived {}/{}'.format(worker, self.objs[worker].received_packets, self.num_from_ps)
                print '{}:\tSent {}'.format(worker, self.objs[worker].packets_sent)
            for ps in self.pses:
                print '{}:\tReceived {}/{}'.format(ps, self.objs[ps].received_packets, self.ps_num_items[ps])
            #print self.edge_weights
            for worker in self.workers:
                print self.sendschedule[worker][-1]
        #print "{}, {}, {}".format(self.final_time, self.start_time, self.finish_time)

    def make_packet(self, size, src, dest, name):
        mpacket = Packet(size, src=src, dest=dest, name=name)
        mpacket.time_send = self.current_time
        if src + dest in self.paths:
            mpacket.path = self.paths[src + dest]
        else:
            mpacket.path = [src, dest]
        if src == dest and self.use_multicast:
            mpacket.multicast = True
        if src in self.workers and self.in_network_computation:
            mpacket.netagg = True
        return mpacket

    def schedule_send(self, delta, size, src, dest, name=""):
        if src == dest and not self.use_multicast:
            for dest in self.workers:
                self.schedule_send_internal(delta, size, src, dest, name=name)
        else:
            self.schedule_send_internal(delta, size, src, dest, name=name)

    def schedule_send_internal(self, delta, size, src, dest, name=""):
        mpacket = self.make_packet(size, src, dest, name)
        mpacket.time_send = self.current_time + delta
        self.schedule_task(delta, lambda: self.objs[src].queuesend(mpacket))

    def schedule_recv(self, delta, packet):
        self.schedule_task(delta, lambda: self.objs[packet.dest].recv(packet))
