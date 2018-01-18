import csv
import argparse
import os.path
import re

import matplotlib.pylab as plt

'''
Keys in csv
inputs_as_bytes,gswitch_recv_rate,tor_inbuffer_size,tor_send_rate,latency,gswitch_inbuffer_size,num_gswitches,use_multicast,json,worker_send_rate,worker_inbuffer_size,step_num,num_ps,worker_recv_rate,num_workers,iteration_time,MTU,latency_std,ps_send_rate,on_same_rack,topology,gswitch_send_rate,tor_recv_rate,ps_inbuffer_size,gradient_size,trace_base_dir,timeout,ps_recv_rate,latency_distribution
'''

# Used to plot experiment 1: varying number of workers and parameter servers
def plot_vary_wk_vary_ps(result_csv_dict, model_name):
    ps_worker_time = {}
    multicast_ps_worker_time = {}
    for result in result_csv_dict:
        num_workers = int(result['num_workers'])
        num_ps = int(result['num_ps'])
        is_multicast = int(result['use_multicast'])
        if is_multicast == 0:
            iteration_time = float(result['iteration_time'])
            
            if num_ps not in ps_worker_time:
                ps_worker_time[num_ps] = {}
            ps_worker_time[num_ps][num_workers] = iteration_time
        elif is_multicast == 1:
            iteration_time = float(result['iteration_time'])
            
            if num_ps not in multicast_ps_worker_time:
                multicast_ps_worker_time[num_ps] = {}
            multicast_ps_worker_time[num_ps][num_workers] = iteration_time

    percent_improvement = {}
    for num_ps in multicast_ps_worker_time:
        percent_improvement[num_ps] = {}
        for num_workers in multicast_ps_worker_time[num_ps]:
            multicast_time = multicast_ps_worker_time[num_ps][num_workers]
            no_multicast_time = ps_worker_time[num_ps][num_workers]
            print multicast_time
            print no_multicast_time
            percent_improvement[num_ps][num_workers] = 100.0 * (no_multicast_time - multicast_time)/float(no_multicast_time) 

    all_lines = []
    for num_ps in multicast_ps_worker_time:
        results = multicast_ps_worker_time[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps, Multicast'.format(num_ps))
        all_lines.append(distr_line)

    for	num_ps in ps_worker_time:
	results = ps_worker_time[num_ps]
	distr_lists = sorted(results.items())
	x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y,label='{} ps, Unicast'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Performance subject to different workers and parameter servers')
    plt.xlabel('Number of Workers')
    plt.ylabel('Iteration time')
    plt.show()

    all_lines = []
    for num_ps in percent_improvement:
        results = percent_improvement[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps, Multicast'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Percent improvement of using Multicast')
    plt.xlabel('Number of workers')
    plt.ylabel('Percent Improvement in Performance with Multicast')
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--result_csv')
    parser.add_argument('--model_name')
    args = parser.parse_args()
    
    file_exists = os.path.isfile(args.result_csv)
    if not file_exists:
        print 'This data file does not exist'
        exit()

    result_csv_dict = csv.DictReader(open(args.result_csv))
    plot_vary_wk_vary_ps(result_csv_dict, args.model_name)
