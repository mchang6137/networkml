import sys
import argparse
import csv
import os

from simulator import *

'''
Michael's Means of automating experiments
'''

def vary_bandwidths(args):
    bw_candidates = [10,1]

    for bw in bw_candidates:
        args.ps_send_rate = bw
        args.worker_send_rate = bw
        args.ps_recv_rate = bw
        args.worker_recv_rate = bw

        print 'INFO: tring with bandwidth {}gbps'.format(bw)
        vary_model(args)

# Try various kinds of models and 
def vary_model(args):
    model_candidates = ['inception-v3', 'resnet-200']

    fw_pass_time = {'inception-v3': 0.176,
                    'resnet-200': 0.357,
                    'vgg16': 0.169,
                    'resnet-101': 0.176}

    for model_name in model_candidates:
        args.model_name = model_name
        args.fw_pass_time = fw_pass_time[model_name]
        args.trace_base_dir = 'csv/' + model_name + '/'
        args.json = 'json/' + '{}_param_ps_assignment.json'.format(model_name)
        print 'INFO: trying with model {}'.format(model_name)
        vary_param_optimality(args)
        print 'INFO: DONE WITH MODEL {}'.format(model_name)

def vary_workers_exp_multicast(args, num_workers=[2,4,8,12], num_ps=[1,2,4,8]):
    args_dict = vars(args)

    # Vary the number of workers and ps
    for workers in num_workers:
	for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps

            print 'INFO: {} ps, {} wk, with only multicast'.format(ps, workers)
            args.use_multicast = 1
            args.in_network_computation = 0
            try:
                sim = Simulation()
                sim.Setup(args)
                finish_time = sim.Run()
                write_to_csv(args, finish_time)
            except:
                print 'this experiment failed in multicast fct'

def vary_workers_exp_aggregation(args, num_workers=[2,4,8,12], num_ps=[1,2,4,8]):
    args_dict = vars(args)

    # Vary the number of workers and ps
    for workers in num_workers:
        for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps
            
            print 'INFO: {} ps, {} wk, with aggregation only'.format(ps, workers)
            args.use_multicast = 0
            args.in_network_computation = 1
            try:
                sim = Simulation()
                sim.Setup(args)
                finish_time = sim.Run()
                write_to_csv(args, finish_time)
            except:
                print 'this experiment failed in aggregation part'

def vary_workers_exp(args, num_workers=[2,4,8,12], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    # Vary the number of workers and ps
    for workers in num_workers:
        for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps

            print 'INFO: {} ps, {} wk, with no agg, no multicast'.format(ps, workers)
            args.use_multicast = 0
            args.in_network_computation = 0
            try:
                sim = Simulation()
                sim.Setup(args)
                finish_time = sim.Run()
                write_to_csv(args, finish_time)
            except:
                print 'this experiment failed in no network improvement'

def vary_workers_exp_multicast_aggregation(args, num_workers=[2,4,8,12], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    for workers in num_workers:
        for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps

            print 'INFO: {} ps {} wk, with aggregation and multicast'.format(workers, ps)
            args.use_multicast = 1
            args.in_network_computation = 1
            try:
                sim = Simulation()
                sim.Setup(args)
	        finish_time = sim.Run()
                write_to_csv(args, finish_time)
            except:
                print 'This experiment has failed in both the agg and multicast'

# Try different types of parameters
def vary_param_optimality(args):
    num_workers = [2,4,8,12]
    num_ps = [1,2,4,8]

    print 'Testing with suboptimal (real) parameter distributions'
    args.optimal_param_distribution = 0
    vary_workers_exp(args, num_workers, num_ps)
    vary_workers_exp_multicast_aggregation(args, num_workers, num_ps)
    vary_workers_exp_multicast(args, num_workers, num_ps)
    vary_workers_exp_aggregation(args, num_workers, num_ps)

    print 'Testing with optimal parameter distributions'
    args.optimal_param_distribution = 1
    vary_workers_exp(args, num_workers, num_ps)
    vary_workers_exp_multicast_aggregation(args, num_workers, num_ps)
    vary_workers_exp_multicast(args, num_workers, num_ps)
    vary_workers_exp_aggregation(args, num_workers, num_ps)


