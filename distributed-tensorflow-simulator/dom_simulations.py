import sys
import argparse
import csv
import os

from simulator import *

'''
Dom's Means of automating experiments
'''

def run_sim(args):
    print "{}:\t{} wk, {} ps, {} multicast, {} in-network computation, {} step".format(args.model_name,
	args.num_workers, args.num_ps, args.use_multicast, args.in_network_computation, args.step_num)
    sim = Simulation()
    sim.Setup(args)
    finish_time, worker_receive_times = sim.Run()
    write_to_csv(args, finish_time, worker_receive_times)

def vary_args(args):
    model_candidates = ['inception-v3']
    others = ['resnet-200', 'vgg16','resnet-101']
    fw_pass_time = {'inception-v3': 0.176,
                    'resnet-200': 0.357,
                    'vgg16': 0.169,
                    'resnet-101': 0.176}
    for model_name in model_candidates:
        args.model_name = model_name
        args.fw_pass_time = fw_pass_time[model_name]
        args.trace_base_dir = 'csv/' + model_name + '/'
        args.distribution_trace_base_dir = 'distribution_csv/{}/'.format(args.model_name)
        args.json = 'json/' + '{}_param_ps_assignment.json'.format(model_name)
        for step in range(10, 30):
	    args.step_num = step
	    for workers in [2, 4, 8, 12, 16, 32]:
		args.num_workers = workers
		for ps in [1, 2, 4, 8]:
		    args.num_ps = ps
		    for mc in [0, 1]:
			args.use_multicast = mc
			for inc in [0, 1]:
			    args.in_network_computation = inc
	            	    try:
		        	run_sim(args)
                    	    except:
				pass

