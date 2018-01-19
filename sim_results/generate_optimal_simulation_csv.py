import csv
import argparse
import os.path
import re

from parse_step_times import *
from find_async_variance import *

'''
Generates the csv for the simulator to use
python generate_simulation_csv.py --base_file async_measurements/gpu/ --num_workers 4 --num_ps 4 --model_name inception-v3
'''

def write_agg_as_csv(model_name, aggregation_events, cluster_size, wk_index, num_ps, step_num):
    initial_agg_time = -1
    aggregation_start_edge = aggregation_start_dict[model_name][0]
    
    for event in aggregation_events:
        raw_edgename = event[5]
	if raw_edgename == aggregation_start_edge:
            initial_agg_time = event[0]
            break

    if initial_agg_time == -1:
	print 'Aggregation initiation not started'
	exit()

    optimal_aggregation_events = []
    for event in aggregation_events:
        send_bytes = event[1]
        edgename = event[5]

        for ps_index in range(int(args.num_ps)):
            new_edgename = edgename + '_ps{}'.format(ps_index)
	    new_bytes  = send_bytes / float(args.num_ps)
            dummy_event = (event[0], new_bytes, event[2], event[3], event[4], new_edgename)
            optimal_aggregation_events.append(dummy_event)

    base_dir = 'sim_csv_ps_optimal/{}/{}/'.format(model_name, cluster_size)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    output_filename = base_dir + 'wk{}_{}.csv'.format(wk_index, step_num)
    with open(output_filename, 'wb') as out:
	csv_out = csv.writer(out)
	csv_out.writerow(['relative_time, bits_sent, raw_edgename'])

	for event in optimal_aggregation_events:
            relative_time = event[0] - initial_agg_time
            if relative_time < 0:
		continue
            bits_sent = event[1] * 8
            raw_edgename = event[5]

            csv_out.writerow((relative_time, bits_sent, raw_edgename))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_file')
    parser.add_argument('--num_workers')
    parser.add_argument('--num_ps')
    parser.add_argument('--model_name')
    args = parser.parse_args()

    all_results_per_setup = {}
    for num_workers in range(int(args.num_workers)+1):
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
            wk_events[wk_index] = parse_result_file_iteration_list([file_name], args.model_name)
        
        # wk_events is a mapping:
        # worker index number -> current_step -> list of events
        min_step_num = 10
        max_step_num = len(wk_events[1].keys())

        # Identify the device set
        device_set = []
        for event in wk_events[1][min_step_num]:
            src_device = event[3]
            dst_device = event[4]
            if src_device not in device_set:
                device_set.append(src_device)
            if dst_device not in device_set:
                device_set.append(dst_device)
        worker_device_set, ps_device_set = separate_device_list(device_set)

        # Filter out the aggregation events
        for wk_index in wk_events:
            for step_num in range(min_step_num, max_step_num):
                events = sorted(wk_events[wk_index][step_num])
                agg_worker_extrapolate = ['/job:worker/replica:0/task:{}/device:GPU:0'.format(wk_index)]
                
                aggregation_events = detect_aggregation_events(events,
                                                               args.model_name,
                                                               agg_worker_extrapolate,
                                                               ps_device_set)

                write_agg_as_csv(args.model_name, aggregation_events, num_workers, args.num_ps, wk_index, step_num)
                print 'Finished Cluster size {}, worker number {}, step number {}'.format(num_workers, wk_index, step_num)
                
    
