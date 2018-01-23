import csv
import json
import argparse
import os.path
import numpy as np

import matplotlib.pylab as plt

from parse_step_times import *

aggregation_start_dict = {'inception-v3': ['inception_v3/conv0/BatchNorm/moments/Squeeze'],
                          'resnet-200': ['resnet_v2_200/block4/unit_2/bottleneck_v2/conv1/BatchNorm/Const_2'],
                          'resnet-101': ['resnet_v2_101/block4/unit_3/bottleneck_v2/conv1/BatchNorm/Const_2'],
	                  'vgg16': ['vgg/conv0/BatchNorm/moments/Squeeze']
}

aggregation_end_dict = {'inception-v3': ['gradients/AddN_304'],
	           'resnet-200': ['gradients/AddN_269'],
                   'resnet-101': ['gradients/AddN_137'],
                   'vgg16': ['gradients/AddN_41'],
                   }

# Worker indicates to parameter servers that it is ready to receive the
# updated parameters. Same for all models.
trigger_variables = 'sync_rep_local_step/read'

# First step in the back propagation step
# Actually use the last squeeze from the forward propagation step
first_back_prop = {'inception-v3': ['gradients/inception_v3/mixed_8x8x2048b/branch_pool/Conv/BatchNorm/batchnorm/sub_grad/tuple/control_dependency'],
                   'resnet-200': ['gradients/resnet_v2_200/logits/BiasAdd_grad/tuple/control_dependency_1'],
                   'resnet-101': ['gradients/resnet_v2_101/logits/BiasAdd_grad/tuple/control_dependency_1'],
                   'vgg16': ['gradients/vgg/logits/xw_plus_b_grad/tuple/control_dependency_1', 'gradients/AddN'],
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
    base_dir = 'async_analysis/{}/'.format(model_name)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    num_rows = 2
    num_columns = (len(worker_plot.keys()) / 2) + (len(worker_plot.keys()) % 2)
    fig, ax = plt.subplots(num_rows, num_columns)

    row_counter = 0
    col_counter = 0
    for num_workers in worker_plot:
        ax[row_counter, col_counter].hist(worker_plot[num_workers])
        ax[row_counter, col_counter].set_title('{} workers'.format(num_workers))

        col_counter += 1
        if col_counter == num_columns:
            row_counter += 1
            col_counter = 0

    plt.tight_layout()
    plt.suptitle('{} for {}'.format(title, model_name))
    plt.savefig('{}_{}_{}_ALL'.format(base_dir, model_name, title))
    plt.show()

# Plots a dict of worker -> a list of outputs
def plot_variable_distributions_by_worker(worker_plot, model_name, title):
    base_dir = 'async_analysis/{}/'.format(model_name)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    '''
    worker_stack = {}
    for num_workers in worker_plot:
        worker_stack[num_workers] = []
        for worker_id in worker_plot[num_workers]:
            worker_plot = worker_plot[num_workers][worker_id]
            for result in worker_plot:
                worker_stack[num_workers][
    '''

    num_rows = 2
    num_columns = (len(worker_plot.keys()) / 2) + (len(worker_plot.keys()) % 2)
    fig, ax = plt.subplots(num_rows, num_columns)

    row_counter = 0
    col_counter = 0
    for num_workers in worker_plot:
        list_to_plot = []
        for wk_id in worker_plot[num_workers]:
            list_to_plot.append(worker_plot[num_workers][wk_id])
        ax[row_counter, col_counter].hist(list_to_plot, stacked=True)
        ax[row_counter, col_counter].set_title('{} workers'.format(num_workers))

        col_counter += 1
        if col_counter == num_columns:
            row_counter += 1
            col_counter = 0

    plt.tight_layout()
    plt.suptitle('{} for {}'.format(title, model_name))
    plt.savefig('{}_{}_{}_ALL'.format(base_dir, model_name, title))
    plt.show()

def get_mean_var_distr_by_worker(worker_result):
    for num_workers in worker_result:
        print 'Cluster of {}'.format(num_workers)
        for wk_id in worker_result[num_workers]:
            median = np.percentile(worker_result[num_workers][wk_id], 50)
            percentile90 = np.percentile(worker_result[num_workers][wk_id], 90)
            percentile10 = np.percentile(worker_result[num_workers][wk_id], 10)

            increase90 = 100 * (percentile90 - median) / float(median)
            increase10 = 100 * (percentile10 - median) / float(median)

            print 'Worker {}, median = {}, 10th = {}, 90th = {}'.format(wk_id, median, increase90, increase10)
        print '\n\n\n'
    
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

    # Calculate the distribution of the time between
    # 1.) sync_local_step and first backpropagation step
    # 2.) first back_propagation step and last back_propagation step
    sync_local_step_time = 'sync_rep_local_step/read'
    first_back_prop_event = first_back_prop[args.model_name][0]
    start_to_first_grad = {}
    first_grad_to_last_grad = {}

    start_to_first_grad_wk = {}
    first_grad_to_last_grad_wk = {}
    for worker_count in all_results_per_setup:
        try:
            sync_local_step = all_results_per_setup[worker_count][sync_local_step_time]
            first_grad = all_results_per_setup[worker_count][first_back_prop_event]
            last_grad = all_results_per_setup[worker_count][aggregation_end]
        except KeyError:
            print worker_count
            continue

        start_to_first_grad[worker_count] = []
        first_grad_to_last_grad[worker_count] = []

        first_grad_to_last_grad_wk[worker_count] = {}
        start_to_first_grad_wk[worker_count] = {}
        
        for step_num in first_grad:
            for wk_id in first_grad[step_num]:
                start_to_first_grad[worker_count].append(first_grad[step_num][wk_id] - sync_local_step[step_num][wk_id])
                first_grad_to_last_grad[worker_count].append(last_grad[step_num][wk_id] - first_grad[step_num][wk_id])

                if wk_id not in first_grad_to_last_grad_wk[worker_count]:
                    start_to_first_grad_wk[worker_count][wk_id] = [first_grad[step_num][wk_id] - sync_local_step[step_num][wk_id]]
                    first_grad_to_last_grad_wk[worker_count][wk_id] = [last_grad[step_num][wk_id] - first_grad[step_num][wk_id]]
                else:
                    start_to_first_grad_wk[worker_count][wk_id].append(first_grad[step_num][wk_id] - sync_local_step[step_num][wk_id])
                    first_grad_to_last_grad_wk[worker_count][wk_id].append(last_grad[step_num][wk_id] - first_grad[step_num][wk_id])

    print 'Start to first grad data'
    get_mean_var_distr_by_worker(start_to_first_grad_wk)
    print '\n\n\n First to last grad'
    get_mean_var_distr_by_worker(first_grad_to_last_grad_wk)

    plot_variable_distributions_by_worker(start_to_first_grad_wk, args.model_name, 'Start to first grad stacked')
    plot_variable_distributions_by_worker(first_grad_to_last_grad_wk, args.model_name, 'First to Last grad stacked')

    plot_variable_distributions(start_to_first_grad, args.model_name, 'Start to first grad')
    plot_variable_distributions(first_grad_to_last_grad, args.model_name, 'First to last grad')
    print 'Exiting after last plot'
    exit()

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
    

    
