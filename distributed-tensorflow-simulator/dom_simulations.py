import sys
import argparse
import csv
import os

from simulator import *

'''
Dom's Means of automating experiments
'''

# Average results over multiple steps
def vary_model_and_steps(args):
    step_num = {'inception-v3': [41,42,43,44,45,46,47],
                'resnet-200': [41,42,43,44,45,46,47],
                'resnet-101': [41,42,43,44,45,46,47],
                'vgg16': [24,25,26,27,28]}

    model_candidates = ['inception-v3','vgg16','resnet-200', 'resnet-101']
    model_candidates = ['resnet-200']
    #step_num['resnet-200'] = [42]
    bandwidths = [10, 25, 50, 100]
    for bandwidth in bandwidths:
        args = set_bandwidth(args, bandwidth)
        for model_name in model_candidates:
            print 'Trying with model name {}'.format(model_name)
            args = set_model(args, model_name)
            step_list = step_num[args.model_name]
            for step in step_list:
                print 'Trying step number {}'.format(step)
                args.step_num = step
                vary_param_optimality(args)
                print 'Finished with step number {}'.format(step)
            print 'Finished simulating with model name {}'.format(model_name)

def run_sim(args):
    sim = Simulation()
    sim.Setup(args)
    finish_time, worker_receive_times = sim.Run()
    write_to_csv(args, finish_time, worker_receive_times)

def set_bandwidth(args, bw):
    args.ps_send_rate = bw
    args.worker_send_rate = bw
    args.ps_recv_rate = bw
    args.worker_recv_rate = bw
    return args

def set_model(args, model_name):
    fw_pass_time = {'inception-v3': 0.176,
                    'resnet-200': 0.357,
                    'vgg16': 0.169,
                    'resnet-101': 0.176}
    
    args.model_name = model_name
    args.fwd_pass_time = fw_pass_time[model_name]
    args.trace_base_dir = 'csv/' + model_name + '/'
    args.distribution_trace_base_dir = 'distribution_csv/{}/'.format(args.model_name)
    args.json = 'json/' + '{}_param_ps_assignment.json'.format(model_name)
    return args

def vary_bandwidths(args):
    bw_candidates = [10]

    for bw in bw_candidates:
        args.ps_send_rate = bw
        args.worker_send_rate = bw
        args.ps_recv_rate = bw
        args.worker_recv_rate = bw

        print 'INFO: trying with bandwidth {}gbps'.format(bw)
        vary_model(args)
        print 'INFO: Done trying with bandwidth {}gbps'.format(bw)

# Try various kinds of models and 
def vary_model(args):
    model_candidates = ['inception-v3', 'resnet-200', 'vgg16','resnet-101']

    fw_pass_time = {'inception-v3': 0.176,
                    'resnet-200': 0.357,
                    'vgg16': 0.169,
                    'resnet-101': 0.176}
    
    for model_name in model_candidates:
        args.model_name = model_name
        args.fwd_pass_time = fw_pass_time[model_name]
        args.trace_base_dir = 'csv/' + model_name + '/'
        args.distribution_trace_base_dir = 'distribution_csv/{}/'.format(args.model_name)
        args.json = 'json/' + '{}_param_ps_assignment.json'.format(model_name)
        print 'INFO: trying with model {}'.format(model_name)
        vary_param_optimality(args)
        print 'INFO: DONE WITH MODEL {}'.format(model_name)

def vary_workers_exp_multicast(args, num_workers=[2,4,8,16,32], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    model_name = args.model_name
    
    # Vary the number of workers and ps
    for workers in num_workers:
	for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps

            print '{}: {} ps, {} wk, with only multicast'.format(model_name, ps, workers)
            args.use_multicast = 1
            args.in_network_computation = 0
            args.horovod = 0
            try:
                run_sim(args)
            except:
                print 'this experiment failed in multicast fct'

def vary_workers_exp_aggregation(args, num_workers=[2,4,8,16,32], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    model_name = args.model_name

    # Vary the number of workers and ps
    for workers in num_workers:
        for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps
            
            print '{}: {} ps, {} wk, with aggregation only'.format(model_name, ps, workers)
            args.use_multicast = 0
            args.in_network_computation = 1
            args.horovod = 0
            try:
                run_sim(args)
            except:
                print 'this experiment failed in aggregation part'

def vary_workers_exp(args, num_workers=[2,4,8,16,32], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    model_name = args.model_name
    # Vary the number of workers and ps
    for workers in num_workers:
        for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps

            print '{}: {} ps, {} wk, with no agg, no multicast'.format(model_name, ps, workers)
            args.use_multicast = 0
            args.in_network_computation = 0
            args.horovod = 0
            try:
                run_sim(args)
            except:
                print 'this experiment failed in no network improvement'

def vary_workers_exp_multicast_aggregation(args, num_workers=[2,4,8,16,32], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    model_name = args.model_name
    for workers in num_workers:
        for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps

            print '{}: {} ps {} wk, with aggregation and multicast'.format(model_name, ps, workers)
            args.use_multicast = 1
            args.in_network_computation = 1
            args.horovod = 0
            try:
                run_sim(args)
            except:
                print 'This experiment has failed in both the agg and multicast'

def vary_workers_exp_horovod(args, num_workers=[2,4,8,16,32], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    model_name = args.model_name
    for workers in num_workers:
        args.num_workers = workers
        args.num_ps = ps

        print '{}: {} ps {} wk, with aggregation and multicast'.format(model_name, ps, workers)
        args.use_multicast = 0
        args.in_network_computation = 0
        args.horovod = 1
        try:
            run_sim(args)
        except:
            print 'This experiment has failed in the horovod'

def vary_workers_exp_horovod_multicast(args, num_workers=[2,4,8,16,32], num_ps=[1,2,4,8]):
    args_dict = vars(args)
    model_name = args.model_name
    for workers in num_workers:
        args.num_workers = workers
        args.num_ps = ps

        print '{}: {} ps {} wk, with aggregation and multicast'.format(model_name, ps, workers)
        args.use_multicast = 1
        args.in_network_computation = 0
        args.horovod = 1
        try:
            run_sim(args)
        except:
            print 'This experiment has failed in both the horovod and multicast'

# Try different types of parameters
def vary_param_optimality(args):
    model_name = args.model_name
    num_workers = [2,4,8,16,32]
    num_ps = [1,8]
    
    print '{} Testing with suboptimal (real) parameter distributions'.format(model_name)
    args.optimal_param_distribution = 0
    vary_workers_exp(args, num_workers, num_ps)
    vary_workers_exp_multicast(args, num_workers, num_ps)
    vary_workers_exp_multicast_aggregation(args, num_workers, num_ps)
    vary_workers_exp_aggregation(args, num_workers, num_ps)
    vary_workers_exp_horovod(args, num_workers, num_ps)
    vary_workers_exp_horovod_multicast(args, num_workers, num_ps)
    '''
    print '{} Testing with optimal parameter distributions'.format(model_name)
    args.optimal_param_distribution = 1
    vary_workers_exp(args, num_workers, num_ps)
    vary_workers_exp_multicast(args, num_workers, num_ps)
    vary_workers_exp_aggregation(args, num_workers, num_ps)
    vary_workers_exp_multicast_aggregation(args, num_workers, num_ps)
    '''
