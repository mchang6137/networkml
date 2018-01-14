import csv
import json
import argparse
import os.path
import numpy as np

import matplotlib.pylab as plt

from parse_step_times import *

aggregation_start_dict = {'inception-v3': ['inception_v3/conv0/BatchNorm/moments/Squeeze'],
                     'resnet-200': ['gradients/resnet_v2_200/logits/BiasAdd_grad/tuple/control_dependency_1'],
                     'resnet-101': ['resnet_v2_101/block1/unit_1/bottleneck_v2/preact/FusedBatchNorm', 'resnet_v2_101/block1/unit_1/bottleneck_v2/preact/Const_2', 'resnet_v2_101/postnorm/Const_2'],
	             'vgg16': ['vgg/conv0/BatchNorm/moments/Squeeze']
                     }

aggregation_end_dict = {'inception-v3': ['gradients/AddN_304'],
	           'resnet-200': ['gradients/AddN_269'],
                   'resnet-101': ['gradients/AddN_137'],
                   'vgg16': ['gradients/AddN_41'],
                   }

sync_local_step_time = 'sync_rep_local_step/read'

def plot_variances(all_variance_median, all_variance_90, all_variance_10, model_name):
    all_lines = []
    for edge_key in all_variance_median:
        lists = sorted(all_variance_median[edge_key].items())
        x,y = zip(*lists)
        line = plt.errorbar(x,y, yerr=[all_variance_10[edge_key],all_variance_90[edge_key]], label=edge_key)
        all_lines.append(line)
    plt.title('Send time variance between workers for {}'.format(model_name))
    plt.legend(handles=all_lines)
    plt.xlabel('Number of workers')
    plt.ylabel('Std deviation of event (msec)')
    plt.show()

# Plots a dict of worker -> a list of outputs
def plot_variable_distributions(worker_plot, model_name, title):
    for num_workers in worker_plot:
        plt.hist(worker_plot[num_workers])
        plt.title('{} for {} workers, {}'.format(title, num_workers, model_name))
        plt.xlabel('ms after sync dequeue')
        plt.show()
    
'''
Iterates through all the iterations in a particular run and determines the variance per variable per machine
'''

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_file')
    parser.add_argument('--num_ps')
    parser.add_argument('--num_wk')
    parser.add_argument('--model_name')
    args = parser.parse_args()

    # Collect the asynchrony per setup (i.e., varying the number of workers in the cluster)
    all_results_per_setup = {}
    variance_per_setup = {}
    for num_workers in range(int(args.num_wk)+1):
        base_dir = args.base_file + args.model_name + '/{}_workers/'.format(num_workers)
        if os.path.isdir(base_dir) is False:
            continue
        
        wk_events = {}
        for wk_index in range(num_workers+1):
            file_name = base_dir + 'gpu{}.txt'.format(wk_index)

            if os.path.isfile(file_name) is False:
                file_name_alternate = base_dir + 'wk{}.txt'.format(wk_index)
                if os.path.isfile(file_name_alternate) is False:
                    continue
                else:
                    file_name = file_name_alternate

            # Collect the events that happened by time
            wk_events[wk_index] = parse_result_file_iteration([file_name], args.model_name)

        # Collect all the events that are known to exist per iteration
        # Choose Worker 1
        for step_num in wk_events[1]:
            if step_num < 5:
                continue
            raw_edgename_list = wk_events[1][step_num]

        # Calculate the average variance from all the steps across all the workers
        # Also record the full logs for later consumption
        min_step_num = 16
        max_step_num = len(wk_events[1].keys()) - 1
        edgename_variance = {}
        edgename_raw = {}
        
        for edgename in raw_edgename_list:
            variance_list = []
            edgename_raw[edgename] = {}
            for step_num in range(min_step_num, max_step_num):
                time_occured = []
                edgename_raw[edgename][step_num] = {}
                for wk_id in wk_events:
                    # find the time of the event
                    if step_num in wk_events[wk_id]:
                        edgename_raw[edgename][step_num][wk_id] = wk_events[wk_id][step_num][edgename][0]
                        time_occured.append(wk_events[wk_id][step_num][edgename][0])
                    else:
                        continue
                variance_list.append(np.std(time_occured))
            edgename_variance[edgename] = variance_list

        variance_per_setup[num_workers] = edgename_variance
        all_results_per_setup[num_workers] = edgename_raw

    # Determine the edges for aggregation start and end
    aggregation_start = ''
    aggregation_end = ''

    try:
	aggregation_start_list = aggregation_start_dict[args.model_name]
        aggregation_end_list = aggregation_end_dict[args.model_name]
    except KeyError:
        print 'Invalid Model Name'
        exit()
    
    for candidate in aggregation_start_list:
        if candidate in variance_per_setup[2]:
            aggregation_start = candidate
            break

    for candidate in aggregation_end_list:
        if candidate in variance_per_setup[2]:
            aggregation_end = candidate
            break

    # Calculate the distribution of specific variables relative to a start
    start_latency = {}
    end_latency = {}
    end_start_diff = {}
    
    sync_local_step_time = 'sync_rep_local_step/read'
    for worker_count in all_results_per_setup:
        try:
            start_results = all_results_per_setup[worker_count][aggregation_start]
            end_results = all_results_per_setup[worker_count][aggregation_end]
            scale_down = all_results_per_setup[worker_count][sync_local_step_time]
        except KeyError:
            print worker_count
            continue

        start_latency[worker_count] = []
        end_latency[worker_count] = []
        end_start_diff[worker_count] = []

        for step_num in start_results:
            for wk_id in start_results[step_num]:
                start_latency[worker_count].append(start_results[step_num][wk_id] - scale_down[step_num][wk_id])
                end_latency[worker_count].append(end_results[step_num][wk_id] - scale_down[step_num][wk_id])
                end_start_diff[worker_count].append(end_results[step_num][wk_id] - start_results[step_num][wk_id])

    plot_variable_distributions(start_latency, args.model_name, 'Start latency')
    plot_variable_distributions(end_latency, args.model_name, 'End Latency')
    plot_variable_distributions(end_start_diff, args.model_name, 'Computation Latency')
                
    # Plot the coarse variances
    all_variance_median = {'agg_start': {}, 'agg_end': {}}
    all_variance_90 = {'agg_start': {}, 'agg_end': {}}
    all_variance_10 = {'agg_start': {}, 'agg_end': {}}

    for worker_count in variance_per_setup:
        try:
            all_variance_median['agg_start'][worker_count] = np.percentile(variance_per_setup[worker_count][aggregation_start], 50)
            all_variance_90['agg_start'][worker_count] = np.percentile(variance_per_setup[worker_count][aggregation_start], 90)
            all_variance_10['agg_start'][worker_count] = np.percentile(variance_per_setup[worker_count][aggregation_start], 10)

            all_variance_median['agg_end'][worker_count] = np.percentile(variance_per_setup[worker_count][aggregation_end], 50)
            all_variance_90['agg_end'][worker_count] = np.percentile(variance_per_setup[worker_count][aggregation_end], 90)
            all_variance_10['agg_end'][worker_count] = np.percentile(variance_per_setup[worker_count][aggregation_end], 10)
        except:
            continue

    plot_variances(all_variance_median, all_variance_90, all_variance_10, args.model_name)
    

    
