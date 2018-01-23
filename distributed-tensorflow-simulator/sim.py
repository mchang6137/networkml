import sys
import random
import json
import os
from packet import Packet
from context import Context
from worker import Worker
from ps import PS
from tor import TOR
from gswitch import GSwitch
from switch import Switch

class Simulation (object):
    def __init__ (self):
        self.ctx = None

    def Setup (self, args):
        tracename_base_dir = args.trace_base_dir
        jsonname = args.json
        self.ctx = Context()
        self.ctx.objs = {}
        self.ctx.internal_latency = args.latency
        self.ctx.latency_distribution = args.latency_distribution
        self.ctx.latency_std = args.latency_std
        self.ctx.timeout = args.timeout
        self.ctx.MTU = args.MTU
        self.ctx.use_multicast = args.use_multicast
        self.ctx.in_network_computation = args.in_network_computation
        self.ctx.verbosity = args.verbosity
        gigabit = 10**9
        if args.topology == '':
            # Store Workers and PS all on same rack
            if args.on_same_rack == 1:
                tor_name = "TOR0"
                self.ctx.objs[tor_name] = TOR(self.ctx, name=tor_name, inbuffer_size=args.tor_inbuffer_size)
                torobj = self.ctx.objs[tor_name]
                torobj.send_rate = args.tor_send_rate * gigabit
                torobj.recv_rate = args.tor_recv_rate * gigabit
                torobj.rack = 0
                self.ctx.tors.append(tor_name)

                # Place all workers and parameter servers on same rack
                for wk_num in range(args.num_workers):
                    worker_name = 'worker{}'.format(wk_num)
                    self.ctx.objs[worker_name] = Worker(self.ctx,
                                                        name=worker_name,
                                                        inbuffer_size=args.worker_inbuffer_size,
                                                        fwd_pass_time=args.fwd_pass_time
                    )
                    wkobj = self.ctx.objs[worker_name]
                    wkobj.send_rate = args.worker_send_rate * gigabit
                    wkobj.recv_rate = args.worker_recv_rate * gigabit
                    self.ctx.workers.append(worker_name)
                    wkobj.rack = 0
                    wkobj.parents.append(tor_name)
                    torobj.children.append(worker_name)

                for ps_num in range(args.num_ps):
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_num)
                    self.ctx.objs[ps_name] = PS(self.ctx, name=ps_name, inbuffer_size=args.ps_inbuffer_size)
                    ps_obj = self.ctx.objs[ps_name]
                    ps_obj.send_rate = args.ps_send_rate * gigabit
                    ps_obj.recv_rate = args.ps_recv_rate * gigabit
                    self.ctx.pses.append(ps_name)
                    ps_obj.rack = 0
                    ps_obj.parents.append(tor_name)
                    torobj.children.append(ps_name)

            # Store all the workers and PS, each on their own rack.
            elif args.on_same_rack == 0:
                rack_counter = 0
                for wk_num in range(args.num_workers):
                    tor_name = "TOR{}".format(rack_counter)
                    self.ctx.objs[tor_name] = TOR(self.ctx, name=tor_name, inbuffer_size=args.tor_inbuffer_size)
                    torobj = self.ctx.objs[tor_name]
                    torobj.send_rate = args.tor_send_rate * gigabit
                    torobj.recv_rate = args.tor_recv_rate * gigabit
                    torobj.rack = rack_counter
                    self.ctx.tors.append(tor_name)
                    
                    worker_name = 'worker{}'.format(wk_num)
                    self.ctx.objs[worker_name] = Worker(self.ctx,
                                                        name=worker_name,
                                                        inbuffer_size=args.worker_inbuffer_size,
                                                        fwd_pass_time=args.fwd_pass_time
                    )
                    wkobj = self.ctx.objs[worker_name]
                    wkobj.send_rate = args.worker_send_rate * gigabit
                    wkobj.recv_rate = args.worker_recv_rate * gigabit
                    self.ctx.workers.append(worker_name)
                    wkobj.rack = rack_counter
                    wkobj.parents.append(tor_name)
                    torobj.children.append(worker_name)
                    rack_counter += 1

                for ps_num in range(args.num_ps):
                    tor_name = "TOR{}".format(rack_counter)
                    self.ctx.objs[tor_name] = TOR(self.ctx, name=tor_name, inbuffer_size=args.tor_inbuffer_size)
                    torobj = self.ctx.objs[tor_name]
                    torobj.send_rate = args.tor_send_rate * gigabit
                    torobj.recv_rate = args.tor_recv_rate * gigabit
                    torobj.rack = rack_counter
                    self.ctx.tors.append(tor_name)
                    
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_num)
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_num)
                    self.ctx.objs[ps_name] = PS(self.ctx, name=ps_name, inbuffer_size=args.ps_inbuffer_size)
                    ps_obj = self.ctx.objs[ps_name]
                    ps_obj.send_rate = args.ps_send_rate * gigabit
                    ps_obj.recv_rate = args.ps_recv_rate * gigabit
                    self.ctx.pses.append(ps_name)
                    ps_obj.rack = rack_counter
                    ps_obj.parents.append(tor_name)
                    torobj.children.append(ps_name)
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
                        self.ctx.objs[name] = Worker(self.ctx,
                                                     name=name,
                                                     inbuffer_size=args.worker_inbuffer_size,
                                                     fwd_pass_time=args.fwd_pass_time
                        )
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
        if args.fat_tree and len(self.ctx.tors) > 1:
            layers = 0
            while True:
                if 2 ** layers >= len(self.ctx.tors):
                    break
                layers += 1
            #print "%d %d" % (layers, len(self.ctx.tors))
            random.shuffle(self.ctx.tors)
            prev_layer = []
            cur_layer = []
            for layer_num in range(layers):
                cur_layer = []
                for switch_num in range(2 ** layer_num):
                    name = "Switch%d.%d" % (layer_num, switch_num)
                    self.ctx.objs[name] = GSwitch(self.ctx, name=name, inbuffer_size=args.gswitch_inbuffer_size)
                    switch_obj = self.ctx.objs[name]
                    switch_obj.send_rate = args.gswitch_send_rate * gigabit * (layers - layer_num)
                    switch_obj.recv_rate = args.gswitch_recv_rate * gigabit * (layers - layer_num)
                    switch_obj.rack = -1
                    self.ctx.gswitches.append(name)
                    cur_layer.append(name)
                for parent_name in prev_layer:
                    parent_obj = self.ctx.objs[parent_name]
                    parent_obj.children.append(cur_layer.pop(0))
                    parent_obj.children.append(cur_layer.pop(0))
                    for child_name in parent_obj.children:
                        self.ctx.objs[child_name].parents.append(parent_name)
                        cur_layer.append(child_name)
                prev_layer = cur_layer
            for tor_name in self.ctx.tors:
                tor_obj = self.ctx.objs[tor_name]
                cur_switch_name = cur_layer.pop(0)
                cur_switch_obj = self.ctx.objs[cur_switch_name]
                cur_switch_obj.children.append(tor_name)
                tor_obj.parents.append(cur_switch_name)
                if len(cur_switch_obj.children) < 2:
                    cur_layer.insert(0, cur_switch_name)
            path_to_ps = {}
            for ps_name in self.ctx.pses:
                path_to_ps[ps_name] = [ps_name]
                cur_obj = self.ctx.objs[ps_name]
                cur_obj.ps_branch[ps_name] = True
                while True:
                    if not cur_obj.parents:
                        break
                    parent_name = cur_obj.parents[0]
                    path_to_ps[ps_name].insert(0, parent_name)
                    cur_obj = self.ctx.objs[parent_name]
                    cur_obj.ps_branch[ps_name] = True
                    #print "%s branches to %s" % (str(cur_obj), ps_name)
                ps_obj = self.ctx.objs[ps_name]
                ps_obj.root = str(cur_obj)
                #print "ps %s root set to %s" % (ps_name, ps_obj.root)
            path_from_worker = {}
            for wk_name in self.ctx.workers:
                path_from_worker[wk_name] = [wk_name]
                cur_obj = self.ctx.objs[wk_name]
                while True:
                    if not cur_obj.parents:
                        break
                    parent_name = cur_obj.parents[0]
                    path_from_worker[wk_name].append(parent_name)
                    cur_obj = self.ctx.objs[parent_name]
                cur_path_from_worker = path_from_worker[wk_name]
                for ps_name in self.ctx.pses:
                    cur_path_to_ps = path_to_ps[ps_name]
                    pname = str(wk_name) + str(ps_name)
                    path = []
                    for step in cur_path_from_worker:
                        if step in cur_path_to_ps:
                            path = cur_path_from_worker[:cur_path_from_worker.index(step)]
                            path.extend(cur_path_to_ps[cur_path_to_ps.index(step):])
                            break
                    self.ctx.paths[pname] = path
                    #print "%s: %s" % (pname, str(path))
                    for step in path:
                        step_obj = self.ctx.objs[step]
                        if not isinstance(step_obj, Switch):
                            continue
                        if ps_name not in step_obj.in_network:
                            step_obj.in_network[ps_name] = 0
                        step_obj.in_network[ps_name] += 1
                    path = path[::-1]
                    pname = str(ps_name) + str(wk_name)
                    self.ctx.paths[pname] = path
                    #print "%s: %s" % (pname, str(path))
            for gswitch in self.ctx.gswitches:
                gs_obj = self.ctx.objs[gswitch]
                #print str(gs_obj)
                #print "\tparents: " + str(gs_obj.parents)
                #print "\tchildren: " + str(gs_obj.children)
                #print "\tnetwork: " + str(gs_obj.in_network)
                #print "\tps branch: " + str(gs_obj.ps_branch)
        else:
            for i in range(args.num_gswitches):
                name = "GSwitch" + str(i)
                self.ctx.objs[name] = GSwitch(self.ctx, name=name, inbuffer_size=args.gswitch_inbuffer_size)
                self.ctx.objs[name].send_rate = args.gswitch_send_rate * gigabit
                self.ctx.objs[name].recv_rate = args.gswitch_recv_rate * gigabit
                self.ctx.objs[name].rack = -1
                self.ctx.gswitches.append(name)
                self.ctx.objs[name].children.extend(self.ctx.tors)

            for tor in self.ctx.tors:
                self.ctx.objs[tor].parents.extend(self.ctx.gswitches)

            for ps in self.ctx.pses:
                ps_obj = self.ctx.objs[ps]
                ps_obj.root = random.choice(self.ctx.gswitches)
                tor_obj = self.ctx.objs[ps_obj.parents[0]]
                tor_obj.ps_branch[ps] = True
                root_obj = self.ctx.objs[ps_obj.root]
                root_obj.ps_branch[ps] = True

            for src in self.ctx.workers:
                srcobj = self.ctx.objs[src]
                for dest in self.ctx.pses:
                    destobj = self.ctx.objs[dest]
                    pname = str(src) + str(dest)
                    if srcobj.parents[0] == destobj.parents[0]:
                        path = [src, srcobj.parents[0], dest]
                    else:
                        path = [src, srcobj.parents[0], destobj.root, destobj.parents[0], dest]
                    self.ctx.paths[pname] = path
                    for step in path:
                        step_obj = self.ctx.objs[step]
                        if not isinstance(step_obj, Switch):
                            continue
                        if dest not in step_obj.in_network:
                            step_obj.in_network[dest] = 0
                        step_obj.in_network[dest] += 1
                    pname = str(dest) + str(src)
                    path = path[::-1]
                    self.ctx.paths[pname] = path
        self.load_parameter_mapping(jsonname, args)
        self.load_relative_send_schedule(tracename_base_dir, args)

        

    def load_relative_send_schedule(self, tracename_basedir, args):
        all_worker_names = self.ctx.workers
        step_num = args.step_num
        num_workers = args.num_workers
        num_ps = args.num_ps
        use_optimal_ps = args.optimal_param_distribution
        
        # Open up individual trace file per worker

        tracename_basedir = tracename_basedir + '{}/'.format(num_workers)
        if os.path.exists(tracename_basedir) is False:
            print 'The provided basename directory does not exist'
            exit()

        self.ctx.sendschedule = {}
        for worker_id in range(num_workers):
            worker_name = 'worker{}'.format(worker_id)
            assert worker_name in all_worker_names
            wk_path = tracename_basedir + 'wk{}_{}.csv'.format(worker_id, step_num)

            if os.path.exists(wk_path) is False:
                print 'There is no trace data for {} cluster, wkid {}, step_num {}'.format(num_workers, worker_id, step_num)
                exit()
        
            trace = open(wk_path).readlines()

            self.ctx.sendschedule[worker_name] = []
            for ev in trace:
                if ev.startswith("//") or ev.startswith('"'):
                    continue
                parts = ev.strip().split(',')
                time = float(parts[0])
                size = float(parts[1])
                if args.inputs_as_bytes:
                    size *= 8
                edgename = str(parts[2])
                if use_optimal_ps == 0:
                    if edgename in self.ctx.pmappings:
                        self.ctx.sendschedule[worker_name].append((time / 1000, size, self.ctx.pmappings[edgename], edgename))
                        self.ctx.ps_num_items[self.ctx.pmappings[edgename]] += len(self.ctx.workers)
                elif use_optimal_ps == 1:
                    # Split the parameter evenly between all the parameter servers
                    revised_size  = size / float(num_ps)
                    for ps_index in range(num_ps):
                        new_edgename = edgename + '_ps{}'.format(ps_index)
                        if new_edgename in self.ctx.pmappings:
                            self.ctx.sendschedule[worker_name].append((time / 1000, revised_size, self.ctx.pmappings[new_edgename], new_edgename))
                            self.ctx.ps_num_items[self.ctx.pmappings[new_edgename]] += len(self.ctx.workers)
                else:
                    print 'Use Optimal PS is invalid. Exiting...'
                    exit()

    def load_parameter_mapping(self, jsonname, args):
        use_optimal_ps = args.optimal_param_distribution
        num_ps = args.num_ps
        
        f = open(jsonname, 'r')
        datastore = json.load(f)
        if use_optimal_ps == 0:
            datastore = datastore[str(len(self.ctx.pses))]
        elif use_optimal_ps == 1:
            datastore = datastore['1']
        self.ctx.ps_num_items = {}
        self.ctx.pmappings = {}
        self.ctx.edge_weights = {}

        if use_optimal_ps == 0:
            for ps, arr in datastore.iteritems():
                self.ctx.ps_num_items[ps] = 0
                for item in arr:
                    self.ctx.pmappings[item[5]] = ps
                    self.ctx.edge_weights[item[5]] = item[1] * 8
            	    self.ctx.schedule_send(0, item[1] * 8, ps, ps, name=str(ps)+"."+item[5])
        elif use_optimal_ps == 1:
            # Should only be the results from the irst parameter server
            for ps, arr in datastore.iteritems():
                for ps_index in range(num_ps):
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_index)
                    self.ctx.ps_num_items[ps_name] = 0
                    for item in arr:
                        event_name = item[5] + '_ps{}'.format(ps_index)
                        param_size = item[1] / float(num_ps)
                        self.ctx.edge_weights[event_name] = param_size * 8
                        self.ctx.pmappings[event_name] = ps_name
                        self.ctx.schedule_send(0, param_size* 8.0, ps_name, ps_name, name=str(ps_name)+"."+event_name)
                    
    def Run (self):
        if self.ctx.verbosity:
            print "Starting replay"        
        self.ctx.run()
        if self.ctx.verbosity:
            print "Done replay at %0.3f, left %d items"%(self.ctx.final_time, self.ctx.queue.qsize()) 
        return self.ctx.final_time
