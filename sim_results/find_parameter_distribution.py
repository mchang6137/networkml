import csv
import json
import argparse
import os.path

import matplotlib.pylab as plt

from parse_step_times import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_file')
    parser.add_argument('--max_ps')
    parser.add_argument('--model_name')
    parser.add_argument('--opt_params')
    args = parser.parse_args()

    result_file_list = []
    base_file = args.base_file

    numps_results = {}
    ps_to_paramlist = {}
    
    for ps_index in range(int(args.max_ps) + 1):
        file_name = base_file + '{}ps'.format(ps_index)
        if os.path.isfile(file_name) is False:
            continue

        events, device_set = parse_result_file([file_name], args.model_name)
        sorted_events = sorted(events, key=lambda x: x[0])

        worker_device_set, ps_device_set = separate_device_list(device_set)
        agg_worker_extrapolate = '/job:worker/replica:0/task:1/device:GPU:0'

        # For aggregation, just aggregate across workers
        aggregation_events = detect_aggregation_events(sorted_events,
                                                       args.model_name,
                                                       agg_worker_extrapolate,
                                                       ps_device_set,
                                                       project_more_workers=False)
        ps_to_paramlist[ps_index] = {}
        for ps_num in range(ps_index):
            ps_name = '/job:ps/replica:0/task:{}/device:CPU:0'.format(ps_num)
            ps_to_paramlist[ps_index][ps_name] = []

        for event in aggregation_events:
            src_device = event[3]
            dst_device = event[4]
            if src_device == agg_worker_extrapolate and dst_device in ps_device_set:
                ps_to_paramlist[ps_index][dst_device].append(event)

        ps_to_bytes, ps_to_count = find_ps_partition(aggregation_events, agg_worker_extrapolate, ps_device_set)
        numps_results[ps_index] = (ps_to_bytes, ps_to_count)

    for num_ps in numps_results:
        print '{} parameter server, {}'.format(num_ps, numps_results[num_ps])

    # Write the distribution of bytes based on parameter server
    file_name = 'ps_split_{}'.format(args.model_name)
    with open(file_name, 'w') as outfile:
        json.dump(numps_results, outfile)

    # Write to which parameter server the particular parameter is sent to
    file_name = '{}_param_ps_assignment'.format(args.model_name)
    with open(file_name, 'w') as outfile:
        json.dump(ps_to_paramlist, outfile)
    
    

    
