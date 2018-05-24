import sys
import random
import json
import os
import glob

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
        distribution_trace_base_dir = args.distribution_trace_base_dir
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
        self.ctx.striping = args.striping
        self.ctx.real_distribution = args.real_distribution
        self.ctx.verbosity = args.verbosity
        self.ctx.use_optimal_param = args.optimal_param_distribution

        fw_pass_time_dict = {'inception-v3': 0.176,
                    'resnet-200': 0.357,
                    'vgg16': 0.169,
                    'resnet-101': 0.176}

        args.fwd_pass_time = fw_pass_time_dict[args.model_name]
        gigabit = 10**9
        if args.horovod:
            args.on_same_rack = 1
            args.num_ps = 0
            args.in_network_computation = 0
            self.ctx.in_network_computation = 0
            self.ctx.use_optimal_param = 0
            self.ctx.horovod = 1
        if args.scattercast:
            args.on_same_rack = 1
            args.num_ps = 0
            args.use_multicast = 1
            self.ctx.use_multicast = 1
            args.in_network_computation = 0
            self.ctx.in_network_computation = 0
            self.ctx.use_optimal_param = 0
            self.ctx.horovod = 0
            self.ctx.scattercast = 1
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
                                                        model_name=args.model_name,
                                                        inbuffer_size=args.worker_inbuffer_size,
                                                        fwd_pass_time=args.fwd_pass_time,
                                                        use_optimal_param=self.ctx.use_optimal_param
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
                                                        model_name=args.model_name,
                                                        inbuffer_size=args.worker_inbuffer_size,
                                                        fwd_pass_time=args.fwd_pass_time,
                                                        use_optimal_param=self.ctx.use_optimal_param
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
                                                     model_name=args.model_name,
                                                     inbuffer_size=args.worker_inbuffer_size,
                                                     fwd_pass_time=args.fwd_pass_time,
                                                     use_optimal_param=self.ctx.use_optimal_param
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
        for objname in self.ctx.objs:
            for objname2 in self.ctx.objs[objname].parents:
                self.ctx.objs[objname].semaphore[objname2] = 1
            for objname2 in self.ctx.objs[objname].children:
                self.ctx.objs[objname].semaphore[objname2] = 1
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
                    switch_obj.send_rate = args.gswitch_send_rate * gigabit #* (layers - layer_num)
                    switch_obj.recv_rate = args.gswitch_recv_rate * gigabit #* (layers - layer_num)
                    switch_obj.rack = -1
                    self.ctx.gswitches.append(name)
                    cur_layer.append(name)
                for parent_name in prev_layer:
                    parent_obj = self.ctx.objs[parent_name]
                    parent_obj.children.append(cur_layer.pop(0))
                    parent_obj.children.append(cur_layer.pop(0))
                    for child_name in parent_obj.children:
                        self.ctx.objs[child_name].parents.append(parent_name)
                        self.ctx.objs[parent_name].semaphore[child_name] = (layers - layer_num)
                        self.ctx.objs[child_name].semaphore[parent_name] = (layers - layer_num)
                        cur_layer.append(child_name)
                prev_layer = cur_layer
            for tor_name in self.ctx.tors:
                tor_obj = self.ctx.objs[tor_name]
                cur_switch_name = cur_layer.pop(0)
                cur_switch_obj = self.ctx.objs[cur_switch_name]
                cur_switch_obj.children.append(tor_name)
                self.ctx.objs[cur_switch_name].semaphore[tor_name] = 1
                self.ctx.objs[tor_name].semaphore[cur_switch_name] = 1
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
            for gswitch in self.ctx.objs:
                if self.ctx.verbosity < 2:
                    continue
                gs_obj = self.ctx.objs[gswitch]
                print str(gs_obj)
                print "\tparents: " + str(gs_obj.parents)
                print "\tchildren: " + str(gs_obj.children)
                for connection, value in gs_obj.semaphore.iteritems():
                    print "\t\t%s: %d" % (connection, value)
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


            for objname in self.ctx.gswitches:
                for objname2 in self.ctx.objs[objname].children:
                    self.ctx.objs[objname].semaphore[objname2] = 1
                    self.ctx.objs[objname2].semaphore[objname] = 1

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
            if args.horovod:
                for src in self.ctx.workers:
                    srcobj = self.ctx.objs[src]
                    for dest in self.ctx.workers:
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
            
        if not self.ctx.horovod and not self.ctx.scattercast:
            self.load_parameter_mapping(jsonname, args)
            self.load_relative_dist_schedule(distribution_trace_base_dir, args)
        self.load_relative_send_schedule(tracename_base_dir, args)

        #print self.ctx.pses
        for ps_name in self.ctx.pses:
            ps_obj = self.ctx.objs[ps_name]
            ps_obj.distribute()
        if self.ctx.horovod:
            #split = num_workers
            split = 1
            #for idx in range(split):
            idx = 0
            for arr in self.ctx.sendschedule["worker"]:
                idx = idx % len(self.ctx.workers)
                #idx = 0
                worker = self.ctx.workers[idx]
                nworker = self.ctx.workers[(idx + 1) % len(self.ctx.workers)]
                wk_obj = self.ctx.objs[worker]
                time_delta = wk_obj.fwd_pass_time + arr[0]
                self.ctx.schedule_send(time_delta, arr[1] / split, worker, nworker, name=arr[3])
                idx += 1
        elif self.ctx.scattercast:
            for worker in self.ctx.workers:
                wk_obj = self.ctx.objs[worker]
                for arr in self.ctx.sendschedule[worker]:
                    time_delta = wk_obj.fwd_pass_time + arr[0]
                    self.ctx.schedule_send(time_delta, arr[1], worker, worker, name=arr[3])

    def load_relative_send_schedule(self, tracename_basedir, args):
        all_worker_names = self.ctx.workers
        num_workers = args.num_workers
        step_num = args.step_num
        
        # Open up individual trace file per worker

        if os.path.exists(tracename_basedir) is False:
            print 'The provided basename directory does not exist'
            exit()
        orig_tracename_basedir = tracename_basedir

        tracename_basedir = tracename_basedir + '{}/'.format(num_workers)
        if self.ctx.horovod:
            csvs = [y for x in os.walk(orig_tracename_basedir) for y in glob.glob(os.path.join(x[0], '*_{}.csv'.format(step_num)))]
            wk_path = random.choice(csvs)
            trace = open(wk_path).readlines()
            self.load_relative_send_schedule_horovod(trace, args)
        elif os.path.exists(tracename_basedir) is True:
            for worker_id in range(num_workers):
                worker_name = 'worker{}'.format(worker_id)
                assert worker_name in all_worker_names
                wk_path = tracename_basedir + 'wk{}_{}.csv'.format(worker_id, step_num)

                if os.path.exists(wk_path) is False:
                    print 'There is no trace data for {} cluster, wkid {}, step_num {}'.format(num_workers, worker_id, step_num)
                    exit()
            
                trace = open(wk_path).readlines()
                self.load_relative_send_schedule_one_worker(trace, worker_name, args)
        else:
            csvs = [y for x in os.walk(orig_tracename_basedir) for y in glob.glob(os.path.join(x[0], '*_{}.csv'.format(step_num)))]
            for worker_id in range(num_workers):
                worker_name = 'worker{}'.format(worker_id)
                assert worker_name in all_worker_names
                wk_path = random.choice(csvs)

                if os.path.exists(wk_path) is False:
                    print 'There is no csv {}'.format(wk_path)
                    exit()
            
                trace = open(wk_path).readlines()
                self.load_relative_send_schedule_one_worker(trace, worker_name, args)
    

    def load_relative_send_schedule_one_worker(self, trace, worker_name, args):
        num_ps = args.num_ps
        use_optimal_ps = self.ctx.use_optimal_param

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
            if self.ctx.scattercast:
                self.ctx.sendschedule[worker_name].append((time / 1000, size, worker_name, edgename))
            elif use_optimal_ps == 0:
                if edgename in self.ctx.pmappings:
                    self.ctx.sendschedule[worker_name].append((time / 1000, size, self.ctx.pmappings[edgename], edgename))
                    self.adjust_in_network(worker_name, self.ctx.pmappings[edgename], edgename)
                elif self.ctx.verbosity:
                    print "%s not assigned a parameter server" % edgename
            elif use_optimal_ps == 1:
                # Split the parameter evenly between all the parameter servers
                revised_size  = size / float(num_ps)
                for ps_index in range(num_ps):
                    new_edgename = edgename + '_ps{}'.format(ps_index)
                    if new_edgename in self.ctx.pmappings:
                        self.ctx.sendschedule[worker_name].append((time / 1000, revised_size, self.ctx.pmappings[new_edgename], new_edgename))
                        self.adjust_in_network(worker_name, self.ctx.pmappings[new_edgename], new_edgename)
                    elif self.ctx.verbosity:
                        print "%s not assigned a parameter server" % edgename
            else:
                print 'Use Optimal PS is invalid. Exiting...'
                exit()
                
    def load_relative_send_schedule_horovod(self, trace, args):
        worker_name = "worker"
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
            self.ctx.sendschedule[worker_name].append((time / 1000, size, worker_name, edgename))
            self.ctx.edge_weights[edgename] = size

    def load_relative_dist_schedule(self, tracename_basedir, args):
        all_ps_names = self.ctx.pses
        num_ps = args.num_ps
        
        # Open up individual trace file per ps

        if os.path.exists(tracename_basedir) is False:
            print 'The provided basename directory does not exist'
            exit()

        if self.ctx.use_optimal_param:
            tracename_basedir = tracename_basedir + '1/'
        else:
            tracename_basedir = tracename_basedir + '{}/'.format(num_ps)
        if os.path.exists(tracename_basedir) is True:
            # Generate random ordering of parameter server IDs
            ps_list = [x for x in range(num_ps)]
            random.shuffle(ps_list)
            for ps_id in ps_list:
                ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_id)
                assert ps_name in all_ps_names
                ps_path = tracename_basedir + 'ps{}.csv'.format(ps_id)
                if self.ctx.use_optimal_param:
                    ps_path = tracename_basedir + 'ps0.csv'
                if os.path.exists(ps_path) is False:
                    print 'There is no trace data for {} cluster, psid {}'.format(num_ps, ps_id)
                    exit()
            
                trace = open(ps_path).readlines()
                self.load_relative_send_schedule_one_ps(trace, ps_name, ps_id, args)
        else:
            print 'There is no trace data in the basename directory for {} cluster'.format(num_ps)
            exit()

    def load_relative_send_schedule_one_ps(self, trace, ps_name, ps_id, args):
        num_ps = args.num_ps
        use_optimal_ps = self.ctx.use_optimal_param

        self.ctx.sendschedule[ps_name] = []
        #print self.ctx.pmappings.keys()
        #print len(self.ctx.pmappings.keys())
        cum_size = 0
        for ev in trace:
            #print ev
            if ev.startswith("//") or ev.startswith('"'):
                continue
            parts = ev.strip().split(',')
            time = float(parts[0]) * (10 ** -18)
            size = float(parts[1])
            if args.inputs_as_bytes:
                size *= 8
            edgename = str(parts[2])
            if use_optimal_ps == 1:
                # Split the parameter evenly between all the parameter servers
                size = size / float(num_ps)
                edgename = edgename + '_ps{}'.format(ps_id)
            send_tuple = (size, edgename)
            if self.ctx.real_distribution:
                dest = str(parts[3])
                send_tuple = (size, edgename, dest)
            self.ctx.sendschedule[ps_name].append(send_tuple)
            self.ctx.num_from_ps += 1
            cum_size += size
        if self.ctx.verbosity:
            print 'Cumm size is {}:\t{}'.format(ps_name, cum_size)

    def adjust_in_network(self, src, dest, edgename):
        self.ctx.ps_num_items[dest] += 1
        path = self.ctx.paths[src+dest]
        for step in path:
            step_obj = self.ctx.objs[step]
            if not isinstance(step_obj, Switch):
                continue
            if edgename not in step_obj.in_network:
                step_obj.in_network[edgename] = 0
            step_obj.in_network[edgename] += 1

    def load_parameter_mapping(self, jsonname, args):
        use_optimal_ps = self.ctx.use_optimal_param
        num_ps = args.num_ps
        
        f = open(jsonname, 'r')
        datastore = json.load(f)
        if use_optimal_ps == 0:
            datastore = datastore[str(len(self.ctx.pses))]
        elif use_optimal_ps == 1:
            datastore = datastore['1']
        self.ctx.pmappings = {}

        if use_optimal_ps == 0:
            for ps, arr in datastore.iteritems():
                self.ctx.ps_num_items[ps] = 0
                for item in arr:
                    event_name = item[5]
                    self.ctx.pmappings[event_name] = ps
                    self.ctx.edge_weights[event_name] = item[1] * 8
                    #print '{} added to pmappings'.format(event_name)
            	    #self.ctx.schedule_send(0, item[1] * 8, ps, ps, name=str(ps)+"."+event_name)
        elif use_optimal_ps == 1:
            # Should only be the results from the first parameter server
            for ps, arr in datastore.iteritems():
                for ps_index in range(num_ps):
                    ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_index)
                    self.ctx.ps_num_items[ps_name] = 0
                    for item in arr:
                        event_name = item[5] + '_ps{}'.format(ps_index)
                        param_size = item[1] / float(num_ps)
                        self.ctx.edge_weights[event_name] = param_size * 8
                        self.ctx.pmappings[event_name] = ps_name
                        #self.ctx.schedule_send(0, param_size* 8.0, ps_name, ps_name, name=str(ps_name)+"."+event_name)
                    
    def Run (self):
        if self.ctx.verbosity:
            print "Starting replay"        
        self.ctx.run()
        if self.ctx.verbosity:
            print "Done replay at %0.3f, left %d items"%(self.ctx.final_time, self.ctx.queue.qsize()) 
        return self.ctx.final_time, self.ctx.worker_receive
