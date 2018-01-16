import sys
import random
import json
from packet import Packet
from context import Context
from worker import Worker
from ps import PS
from tor import TOR
from gswitch import GSwitch
class Simulation (object):
    def __init__ (self):
        self.ctx = None

    def Setup (self, args):
        tracename = args.trace
        jsonname = args.json
        self.ctx = Context()
        self.ctx.objs = {}
        self.ctx.internal_latency = args.latency
        self.ctx.latency_distribution = args.latency_distribution
        self.ctx.latency_std = args.latency_std
        self.ctx.timeout = args.timeout
        self.ctx.MTU = args.MTU
        self.ctx.use_multicast = args.use_multicast
        gigabit = 10**9
        if args.topology == '':
            # Store Workers and PS all on same rack
            if args.on_same_rack == 1:
                self.ctx.racks[0] = []
                name = "TOR0"
                self.ctx.objs[name] = TOR(self.ctx, name=name, inbuffer_size=args.tor_inbuffer_size)
                self.ctx.objs[name].send_rate = args.tor_send_rate * gigabit
                self.ctx.objs[name].recv_rate = args.tor_recv_rate * gigabit
                self.ctx.objs[name].rack = 0
                self.ctx.racks[0].append(name)
                self.ctx.tors.append(name)

                # Place all workers and parameter servers on same rack
                for wk_num in range(args.num_workers):
                    worker_name = 'worker{}'.format(wk_num)
                    self.ctx.objs[worker_name] = Worker(self.ctx,
                                                        name=worker_name,
                                                        inbuffer_size=args.worker_inbuffer_size)
                    self.ctx.objs[worker_name].send_rate = args.worker_send_rate * gigabit
                    self.ctx.objs[worker_name].recv_rate = args.worker_recv_rate * gigabit
                    self.ctx.workers.append(worker_name)
                    self.ctx.objs[worker_name].rack = 0
                    self.ctx.racks[0].append(worker_name)

                for ps_num in range(args.num_ps):
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_num)
                    self.ctx.objs[ps_name] = PS(self.ctx, name=ps_name, inbuffer_size=args.ps_inbuffer_size)
                    self.ctx.objs[ps_name].send_rate = args.ps_send_rate * gigabit
                    self.ctx.objs[ps_name].recv_rate = args.ps_recv_rate * gigabit
                    self.ctx.pses.append(ps_name)
                    self.ctx.objs[ps_name].rack = 0
                    self.ctx.racks[0].append(ps_name)

            # Store all the workers and PS, each on their own rack.
            elif args.on_same_rack == 0:
                rack_counter = 0
                for wk_num in range(args.num_workers):
                    self.ctx.racks[rack_counter] = []
                    name = "TOR{}".format(rack_counter)
                    self.ctx.objs[name] = TOR(self.ctx, name=name, inbuffer_size=args.tor_inbuffer_size)
                    self.ctx.objs[name].send_rate = args.tor_send_rate * gigabit
                    self.ctx.objs[name].recv_rate = args.tor_recv_rate * gigabit
                    self.ctx.objs[name].rack = rack_counter
                    self.ctx.racks[rack_counter].append(name)
                    self.ctx.tors.append(name)
                    
                    worker_name = 'worker{}'.format(wk_num)
                    self.ctx.objs[worker_name] = Worker(self.ctx,
                                                        name=worker_name,
                                                        inbuffer_size=args.worker_inbuffer_size)
                    self.ctx.objs[worker_name].send_rate = args.worker_send_rate * gigabit
                    self.ctx.objs[worker_name].recv_rate = args.worker_recv_rate * gigabit
                    self.ctx.workers.append(worker_name)
                    self.ctx.objs[worker_name].rack = rack_counter
                    self.ctx.racks[rack_counter].append(worker_name)
                    rack_counter += 1

		for ps_num in range(args.num_ps):
                    self.ctx.racks[rack_counter] = []
                    name = "TOR{}".format(rack_counter)
                    self.ctx.objs[name] = TOR(self.ctx, name=name, inbuffer_size=args.tor_inbuffer_size)
                    self.ctx.objs[name].send_rate = args.tor_send_rate * gigabit
                    self.ctx.objs[name].recv_rate = args.tor_recv_rate * gigabit
                    self.ctx.objs[name].rack = rack_counter
                    self.ctx.racks[rack_counter].append(name)
                    self.ctx.tors.append(name)
                    
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_num)
                    self.ctx.objs[ps_name] = PS(self.ctx,
                                                name=ps_name,
                                                inbuffer_size=args.ps_inbuffer_size)
                    self.ctx.objs[ps_name].send_rate = args.ps_send_rate * gigabit
                    self.ctx.objs[ps_name].recv_rate = args.ps_recv_rate * gigabit
                    self.ctx.pses.append(ps_name)
                    self.ctx.objs[ps_name].rack = rack_counter
                    self.ctx.racks[rack_counter].append(ps_name)
                    rack_counter += 1
        # Leaving this here: declaring manual topologies
        elif args.topology:
            topology = args.topology
            topology = topology.strip("[]")
            topology = topology.replace('],',';')
            topology = topology.replace('[','')
            topology = topology.replace(' ','')
            racks = topology.split(';')
            rack_number = 0
            for rack in racks:
                self.ctx.racks[rack_number] = []
                name = "TOR" + str(rack_number)
                self.ctx.objs[name] = TOR(self.ctx, name=name, inbuffer_size=args.tor_inbuffer_size)
                self.ctx.objs[name].send_rate = args.tor_send_rate * gigabit
                self.ctx.objs[name].recv_rate = args.tor_recv_rate * gigabit
                self.ctx.objs[name].rack = rack_number
                self.ctx.racks[rack_number].append(name)
                self.ctx.tors.append(name)
                for name in rack.split(','):
                    if 'ps' in name:
                        self.ctx.objs[name] = PS(self.ctx, name=name, inbuffer_size=args.ps_inbuffer_size)
                        self.ctx.objs[name].send_rate = args.ps_send_rate * gigabit
                        self.ctx.objs[name].recv_rate = args.ps_recv_rate * gigabit
                        self.ctx.pses.append(name)
                    elif 'worker' in name:
                        self.ctx.objs[name] = Worker(self.ctx, name=name, inbuffer_size=args.worker_inbuffer_size)
                        self.ctx.objs[name].send_rate = args.worker_send_rate * gigabit
                        self.ctx.objs[name].recv_rate = args.worker_recv_rate * gigabit
                        self.ctx.workers.append(name)
                    else:
                        print 'Could not determine the type of ' + name
                        exit()
                    self.ctx.objs[name].rack = rack_number
                    self.ctx.racks[rack_number].append(name)
                rack_number += 1
            for key, value in self.ctx.objs.iteritems():
                pass
        for i in range(args.num_gswitches):
            name = "GSwitch" + str(i)
            self.ctx.objs[name] = GSwitch(self.ctx, name=name, inbuffer_size=args.ps_inbuffer_size)
            self.ctx.objs[name].send_rate = args.gswitch_send_rate * gigabit
            self.ctx.objs[name].recv_rate = args.gswitch_recv_rate * gigabit
            self.ctx.objs[name].rack = -1
            self.ctx.gswitches.append(name)

        for src in self.ctx.objs:
            srcobj = self.ctx.objs[src]
            if src not in self.ctx.workers and src not in self.ctx.pses:
                continue
            for dest in self.ctx.objs:
                destobj = self.ctx.objs[dest]
                if dest not in self.ctx.workers and dest not in self.ctx.pses:
                    continue
                pname = str(src) + str(dest)
                if pname not in self.ctx.paths:
                    if srcobj.rack == destobj.rack:
                        path = [src, "TOR%d"%(srcobj.rack), dest]
                    else:
                        path = [src, "TOR%d"%(srcobj.rack), "GSwitch%d"%(random.randint(0, args.num_gswitches - 1)), "TOR%d"%(destobj.rack), dest]
                    self.ctx.paths[pname] = path

        self.load_parameter_mapping(jsonname, args)
        self.load_relative_send_schedule(tracename, args)

    def load_raw_trace(self, tracename, args):
        trace = open(tracename).readlines()
        num_packets = 0
        for ev in trace:
            if ev.startswith("//") or ev.startswith('"'):
                continue
            parts = ev.strip().split(',')
            time = float(parts[0])
            size = float(parts[1])
            if args.inputs_as_bytes:
                size *= 8
            src = str(parts[2])
            dest = str(parts[3])
            if src not in self.ctx.objs:
                if 'ps' in src:
                    self.ctx.objs[src] = PS(self.ctx, name=src)
                    self.ctx.objs[src].send_rate = args.ps_send_rate
                    self.ctx.objs[src].recv_rate = args.ps_recv_rate
                    self.ctx.objs[src].inbuffer_size = args.ps_inbuffer_size
                elif 'worker' in src:
                    self.ctx.objs[src] = Worker(self.ctx, name=src)
                else:
                    print 'Could not determine the type of ' + src
                self.ctx.objs[src].rack = 0
            if dest not in self.ctx.objs:
                if 'ps' in dest:
                    self.ctx.objs[dest] = PS(self.ctx, name=dest)
                    self.ctx.objs[dest].send_rate = args.ps_send_rate
                    self.ctx.objs[dest].recv_rate = args.ps_recv_rate
                    self.ctx.objs[dest].inbuffer_size = args.ps_inbuffer_size
                elif 'worker' in dest:
                    self.ctx.objs[dest] = Worker(self.ctx, name=dest)
                    self.ctx.objs[dest].send_rate = args.worker_send_rate
                    self.ctx.objs[dest].recv_rate = args.worker_recv_rate
                    self.ctx.objs[dest].inbuffer_size = args.worker_inbuffer_size
                else:
                    print 'Could not determine the type of ' + dest
                self.ctx.objs[dest].rack = 0
            if src in self.ctx.pses:
                if not self.ctx.use_multicast:
                    for dest in self.ctx.workers:
                        self.ctx.schedule_send(time, size, src, dest, name=str(num_packets))
                else:
                    self.ctx.schedule_send(time, size, src, src, name=str(num_packets))
            else:
                self.ctx.schedule_send(time, size, src, dest, name=str(num_packets))
            num_packets += 1
    
    def load_send_from_json(self, jsonname, args):
        f = open(jsonname, 'r')
        datastore = json.load(f)
        self.ctx.sendschedule = []
        self.ctx.ps_num_items = {}
        gradient_size = 0
        for ps, arr in datastore.iteritems():
            self.ctx.ps_num_items[ps] = len(arr) * len(self.ctx.workers)
            for item in arr:
                self.ctx.sendschedule.append(item)
                gradient_size += item[1]
        if args.gradient_size:
            gradient_size = args.gradient_size
        if args.inputs_as_bytes:
            gradient_size *= 8
        for ps in self.ctx.pses:
            self.ctx.schedule_send(0, gradient_size, ps, ps, name=str(ps)+"gradients")

    def load_relative_send_schedule(self, tracename, args):
        trace = open(tracename).readlines()
        self.ctx.sendschedule = []
        for ev in trace:
            if ev.startswith("//") or ev.startswith('"'):
                continue
            parts = ev.strip().split(',')
            time = float(parts[0])
            size = float(parts[1])
            if args.inputs_as_bytes:
                size *= 8
            edgename = str(parts[2])
            self.ctx.sendschedule.append((time / 1000, size, self.ctx.pmappings[edgename], edgename))
            self.ctx.ps_num_items[self.ctx.pmappings[edgename]] += len(self.ctx.workers)

    def load_parameter_mapping(self, jsonname, args):
        f = open(jsonname, 'r')
        datastore = json.load(f)
        datastore = datastore[str(len(self.ctx.pses))]
        self.ctx.ps_num_items = {}
        self.ctx.pmappings = {}
        cumgrad = 0
        for ps, arr in datastore.iteritems():
            gradient_size = 0
            self.ctx.ps_num_items[ps] = 0
            for item in arr:
                self.ctx.pmappings[item[5]] = ps
                gradient_size += item[1]       
            if args.gradient_size:
                gradient_size = args.gradient_size
            if True or args.inputs_as_bytes:
                gradient_size *= 8
            cumgrad += gradient_size
            #print "%s: %f" % (str(ps), gradient_size)
            self.ctx.schedule_send(0, gradient_size, ps, ps, name=str(ps)+".gradients")
        #print "%f" % (cumgrad)

    def Run (self):
        print "Starting replay"        
        self.ctx.run()
        print "Done replay at %0.3f, left %d items"%(self.ctx.final_time, self.ctx.queue.qsize()) 
