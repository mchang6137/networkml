import csv
import argparse

import matplotlib.pylab as plt

# Instructions: Include the results of the send time over TWO ITERATIONS.

# Example Line that is read: 1510608248590 Send data with estimated 512 bytes. Edge name: edge_19288_gradients/inception_v3/mixed_17x17x768b/branch7x7/Conv/BatchNorm/batchnorm/sub_grad/tuple/control_dependency. src_device: /job:worker/replica:0/task:0/device:GPU:0. dst_device: /job:ps/replica:0/task:0/device:CPU:0

# Model Types
supported_models = ['vgg16', 'inception-v3']

# Parses the full edge name
# Deprecate this
def parse_edge_name(train_op, model_name):
    if model_name == 'vgg16':
        return parse_vgg_model(train_op)
    elif model_name == 'inception-v3':
        return parse_inception_model(train_op)
    elif model_name = 'resnet':
        return parse_resnet_model(train_op)
    else:
        print 'Invalid model name'
        exit()
    return edge_name

def parse_inception_model(train_op):
    # Parse the weights of the VGG model
    operation_hierarchy = train_op.split('/')

    edge_name = {'type': None,
                 'variable_scope': None,
                 'operation_scope': None,
                 'operation': None,
    }

    # General tasks
    # group_deps, sync_token_q_Dequeue, Assign_1, train_op, ExponentialDecay
    if len(operation_hierarchy) == 1:
        edge_name['variable_scope'] = train_op
    # Finds the AddN Operation
    elif len(operation_hierarchy) == 2:
        if operation_hierarchy[1].split('_') == 'AddN':
            edge_name['op_scope'] = operation_hierarchy[1]
    # Forward pass in the direction of wk -> ps
    elif operation_hierarchy[0] == 'inception_v3':
	try:
            edge_name['variable_scope'] = operation_hierarchy[1]
            edge_name['operation_scope'] = operation_hierarchy[2]
            edge_name['operation'] = operation_hierarchy[3]
        except:
            print operation_hierarchy
            print 'Failed to parse the above'
            exit()
    # Backwards pass in the direction of wk -> ps
    elif operation_hierarchy[0] == 'gradients':
         # Finds the AddN Operation that occurs to send gradients
        if len(operation_hierarchy) == 2:
            if operation_hierarchy[1].split('_') == 'AddN':
                edge_name['operation_scope'] = operation_hierarchy[1]
        # wk -> ps, Forward pass
        elif operation_hierarchy[1] == 'inception_v3':
            edge_name['variable_scope'] = operation_hierarchy[2]
            edge_name['operation_scope'] = operation_hierarchy[3]
            edge_name['operation'] = operation_hierarchy[4]
    # Gradient updates from ps -> wk
    elif 'weights' in operation_hierarchy:
        print 'Weights: {}'.format(operation_hierarchy)
        edge_name['variable_scope'] = operation_hierarchy[0]
	edge_name['operation_scope'] = operation_hierarchy[1]
        edge_name['operation'] = operation_hierarchy[2]

    return edge_name

# Parse the weights of the VGG model
def parse_vgg_model(train_op):
    operation_hierarchy = train_op.split('/')

    edge_name = {'type': None,
                 'variable_scope': None,
                 'operation_scope': None,
                 'operation': None,
    }
    
    # General tasks
    # group_deps, sync_token_q_Dequeue, Assign_1, train_op, ExponentialDecay
    if len(operation_hierarchy) == 1:
        edge_name['variable_scope'] = train_op
    # Finds the AddN Operation
    elif len(operation_hierarchy) == 2:
        if operation_hierarchy[1].split('_') == 'AddN':
            edge_name['op_scope'] = operation_hierarchy[1]
    # Forward pass in the direction of wk -> ps
    elif operation_hierarchy[0] == 'inception_v3':
	try:
            edge_name['variable_scope'] = operation_hierarchy[1]
            edge_name['operation_scope'] = operation_hierarchy[2]
            edge_name['operation'] = operation_hierarchy[3]
        except:
            print operation_hierarchy
            print 'Failed to parse the above'
            exit()
    # Backwards pass in the direction of wk -> ps
    elif operation_hierarchy[0] == 'gradients':
         # Finds the AddN Operation that occurs to send gradients
	if len(operation_hierarchy) == 2:
            if operation_hierarchy[1].split('_') == 'AddN':
                edge_name['operation_scope'] = operation_hierarchy[1]
        # wk -> ps, Forward pass
        elif operation_hierarchy[1] == 'inception_v3':
            edge_name['variable_scope'] = operation_hierarchy[2]
            edge_name['operation_scope'] = operation_hierarchy[3]
            edge_name['operation'] = operation_hierarchy[4]
    # Gradient updates from ps -> wk
    elif 'weights' in operation_hierarchy:
        print 'Weights: {}'.format(operation_hierarchy)
        edge_name['variable_scope'] = operation_hierarchy[0]
        edge_name['operation_scope'] = operation_hierarchy[1]
        edge_name['operation'] = operation_hierarchy[2]

    return edge_name

# Sorted events should only be from a single worker
def detect_distribution_events(sorted_events,
                               model_name,
                               worker_device_set,
                               ps_device_set,
                               project_more_workers=False):
    
    distribution_events = []
    in_distribution = False
    close_event_count = 0
    
    for event in sorted_events:
        # First event is the batch normalization
        # SAVE RAW EDGE NAME IN EVENT INFO
        raw_edge_name = event[5]
        src_device = event[3]
        dst_device = event[4]

        # Distribution events start with a global step
        # Should not be model specific
        if raw_edge_name == 'sync_token_q_Dequeue':
            in_distribution = True

        if src_device in ps_device_set and dst_device in worker_device_set:
            if in_distribution:
                distribution_events.append(event)

            # Distribution events end with specific operation
            # This IS MODEL SPECIFIC
            if in_distribution:
                if  model_name == 'vgg16':
                    # Hard code this!
                    if raw_edge_name == 'fc1/weights/Regularizer/L2Regularizer/value':
                        return distribution_events
                elif model_name == 'inception-v3':
                    if raw_edge_name == 'mixed_35x35x256a/branch5x5/Conv/weights/Regularizer/L2Regularizer/value':
                        return distribution_events

    print 'A Valid distribution set of events have not been found'
    exit()

# Detect aggregation events will automatically project more workers
def detect_aggregation_events(sorted_events,
                              model_name,
                              worker_device_set,
                              ps_device_set,
                              project_more_workers=False):
    aggregation_events = []
    in_aggregation = False

    for event in sorted_events:
        # First event is the batch normalization
        # SAVE RAW EDGE NAME IN EVENT INFO
        raw_edge_name = event[5]
        src_device = event[3]
        dst_device = event[4]

        if src_device in worker_device_set and dst_device in ps_device_set:
            # Aggregation events start with a global step
            # Not model specific
            
            if model_name == 'inception-v3' and raw_edge_name == 'inception_v3/conv0/BatchNorm/moments/Squeeze':
                in_aggregation = True
            elif model_name == 'vgg16' and raw_edge_name == 'vgg/conv0/BatchNorm/moments/Squeeze':
                in_aggregation = True

            if in_aggregation:
                aggregation_events.append(event)

            # Distribution events end with specific operation
	    # This IS MODEL SPECIFIC
            if in_aggregation:
                if model_name == 'vgg16':
                    # Hard code this!
                    if raw_edge_name == 'gradients/AddN_41':
                        return aggregation_events
                elif model_name == 'inception-v3':
                    if raw_edge_name == 'gradients/AddN_304':
                        return aggregation_events

    print 'There is no complete aggregation grouping in this dataset. Exiting..'
    exit()


# Filters down all the events to the events in a single iteration
# sorted_event_list is the list of all events that were sent between machines
# Start of the iteration is the receipt of the global step on the chief worker machine (task:0)
def separate_one_iteration(sorted_event_list, worker_device_set, ps_device_set):
    events_in_iteration = []
    in_iteration = False
    
    for event in sorted_event_list:
        time = event[0]
        src_device = event[3]
        event_dict = event[2]

        if event_dict['variable_scope'] == 'global_step:0' and src_device == '/job:worker/replica:0/task:0/device:CPU:0':
            if in_iteration:
                return events_in_iteration
            else:
                print 'starting test'
                print event
                in_iteration = True
                
        if in_iteration:
            events_in_iteration.append(event)

    print 'Only one iteration present here. Exiting here for unexpected behavior.'
    exit()

# Find the events associated with various nodes in the graph
# Used to model the time until aggregation
def time_until_aggregation(event_list, worker_device_list, ps_device_list):
    edge_set = []
    for event in event_list:
        edge_dict = event[2]
        if edge_dict not in edge_set:
            edge_set.append(frozenset(edge_dict.items()))

    weight_lifetime = {}
    for edge in edge_set:
        weight_lifetime[edge] = {
            'ps_to_worker': [],
            'worker_to_ps': [],
        }

    for event in event_list:
        send_time, send_bytes, edge_dict, src_device, dst_device = event
        edge = frozenset(edge_dict.items())
        if src_device in ps_device_list and dst_device in worker_device_list:
            weight_lifetime[edge]['ps_to_worker'].append(send_time)
        elif src_device in worker_device_list and dst_device in ps_device_list:
            weight_lifetime[edge]['worker_to_ps'].append(send_time)

    time_diff = []
    for edge in weight_lifetime:
        if len(weight_lifetime[edge]['ps_to_worker']) == 0 or len(weight_lifetime[edge]['worker_to_ps']) == 0:
            continue
        diff = max(weight_lifetime[edge]['ps_to_worker']) - max(weight_lifetime[edge]['worker_to_ps'])
        time_diff.append(diff)

    print time_diff

# Parses the datapoint from the graph
def split_result_line(raw_events, model_name):
    event_list = []
    raw_events = raw_events.replace('\n', '')

    if raw_events == '':
        return [(None, None, None, None, None, None)]

    # Begin by checking to see if the line spacing is messed up
    job_count = raw_events.count('job')
    num_events = job_count / 2

    if num_events == 1:
        if raw_events[0].isdigit() is False:
            raw_events = raw_events[1:]
        event_list.append(raw_events)
        send_time_str = raw_events.split(' ')[0]
    else:
        # assumes all these times are the smae unmber of sigfigs
        send_time_str = raw_events.split(' ')[0]
        send_time_len = len(send_time_str)

        for event in range(num_events - 1):
            split_string = ' Send data with estimated'
            split_index = raw_events.index(split_string, 100)
            split_index = split_index - send_time_len
            event_list.append(raw_events[:split_index])
            raw_events = raw_events[split_index:]

        event_list.append(raw_events)

    event_result = []
    for results in event_list:
        print results
        
        # Retrieve the send time
        send_time_str = raw_events.split(' ')[0]
        try:
            send_time = float(send_time_str)
        except:
            continue

        # Retrieve the edge of the message
        import re
        try:
            regex = re.compile('edge_([0-9]*)')
            edge_num = int(regex.findall(results)[0])
            initial_string = 'edge_' + str(edge_num) + '_'
            initial_index = results.index(initial_string)
            end_string = '. src_device'
            end_index = results.index(end_string)
        
            full_edgename = results[initial_index + len(initial_string):end_index]
            edge_dict = parse_edge_name(full_edgename, model_name)
        except:
            if 'edge' in results:
                initial_string = 'Edge name: '
                initial_index = results.index(initial_string)
                end_string = '. src_device'
                end_index = results.index(end_string)

                full_edgename = results[initial_index + len(initial_string):end_index]
                edge_dict = parse_edge_name(full_edgename, model_name)
            else:
                continue

        # Retrieve the message size
        previous_string = 'estimated '
	previous_index = results.index(previous_string)
        subsequent_index = results.index(' bytes')
        send_bytes = float(results[previous_index + len(previous_string):subsequent_index])

	# Retrieve the src and dst devices
	src_string = 'src_device: '
	src_index = results.index(src_string)
	end_index = results.index('. dst_device')
	src_device = results[src_index + len(src_string):end_index]

	dst_string = 'dst_device: '
        dst_index = results.index(dst_string)
	dst_device = results[dst_index + len(dst_string):]

        event_result.append((send_time, send_bytes, edge_dict, src_device, dst_device, full_edgename))

    return event_result

# Compare the bytes sent between the nodes
def compare_bytes_sent(sorted_time_events):
    worker_device = '/job:worker/replica:0/task:1/device:GPU:0'
    ps_device = '/job:ps/replica:0/task:0/device:CPU:0'

    total_bytes_worker_ps = 0
    for event in sorted_time_events:
        send_time, send_bytes, edge_num, src_device, dst_device = event
        if src_device == worker_device and dst_device == ps_device:
            total_bytes_worker_ps += send_bytes

    total_bytes_ps_worker = 0
    for event in sorted_time_events:
        send_time, send_bytes, edge_num, src_device, dst_device = event
        if src_device == ps_device and dst_device == worker_device:
            total_bytes_ps_worker += send_bytes

    print 'Worker to Parameter server is {}'.format(total_bytes_worker_ps / (10 ** 9))
    print 'Parameter Server to worker is {}'.format(total_bytes_ps_worker / (10 ** 9))


# Calculate the amount of time leftover as a result of network contention
def compare_times(sorted_time_events, num_workers, ps_bandwidth, for_aggregation=True):
    most_recent_send_event = 0

    time_byte = {}

    # Data Cleaning
    for event in sorted_time_events:
        send_time, send_bytes, edge_num, src_device, dst_device, raw_edge = event
        # Combine events that happened at the same time
        if send_time in time_byte:
            time_byte[send_time] += send_bytes
        else:
            time_byte[send_time] = send_bytes

    outstanding_gb = 0
    
    sorted_times = sorted(time_byte.keys())
    time_to_bandwidth = {}

    for time_index in range(len(sorted_times) - 1):
        times_to_send = sorted_times[time_index+1] - sorted_times[time_index]
        # Hardcoded since the results are being returned in milliseconds
        times_to_send = times_to_send / 1000

        bytes_to_send = time_byte[sorted_times[time_index]]
        bits_to_send = bytes_to_send * 8
        gb_to_send = num_workers * bits_to_send / (10 ** 9)
        gb_to_send += outstanding_gb

        bandwidth = gb_to_send / float(times_to_send)

        if bandwidth > ps_bandwidth:
            outstanding_gb = gb_to_send - (ps_bandwidth * times_to_send)
        else:
            outstanding_gb = 0

        print 'Required bandwidth is bandwidth {} Gbps'.format(bandwidth)
        print 'Amount sent is {}'.format(gb_to_send)
        print 'Amount of time is {}'.format(times_to_send)
        print 'Outstanding Gb is {}'.format(outstanding_gb)
        outstanding_time = outstanding_gb / ps_bandwidth
        print 'Time to send outstanding gb is {}'.format(outstanding_time)

    bytes_to_send = time_byte[sorted_times[-1]]
    bits_to_send = bytes_to_send * 8
    gb_to_send = num_workers * bits_to_send / (10 ** 9)
    gb_to_send += outstanding_gb
    
    print 'The last message is sent with {} gb with {} gb outstanding'.format(gb_to_send, outstanding_gb)
    time_to_send = gb_to_send / ps_bandwidth
    
    print 'It will take {} seconds'.format(time_to_send)
    remaining_time = outstanding_gb / ps_bandwidth
    print 'This Step has concluded. Time it takes to transmit remaining {} Gbits is {}'.format(outstanding_gb, remaining_time)

    return remaining_time

# Plots the amount of bytes sent by each flow at each point in time
def plot_send_times(flow_event_time, worker_device, ps_device):
    all_lines = []
    for flow in flow_event_time:
        src = flow[0]
        dst = flow[1]

        if (src not in worker_device and src not in ps_device) or (dst not in worker_device and dst not in ps_device):
            continue

        lists = sorted(flow_event_time[flow].items())
        x,y = zip(*lists)
        line, = plt.plot(x,y,label=str(flow))
        all_lines.append(line)
    plt.legend(handles=all_lines)
    plt.show()

# plots the amount of remaining bits
def plot_worker_remaining_bits(distr_events, agg_events, bandwidth, model_name):
    all_lines = []
    
    distr_lists = sorted(distr_events.items())
    x,y = zip(*distr_lists)
    distr_line, = plt.plot(x,y,label='Distribution')
    all_lines.append(distr_line)

    agg_lists = sorted(agg_events.items())
    x,y = zip(*agg_lists)
    agg_line, = plt.plot(x,y,label='Aggregation')
    all_lines.append(agg_line)

    plt.legend(handles=all_lines)
    plt.title('{}, Param server bandwidth = {}gbps'.format(model_name, bandwidth))
    plt.xlabel('Number of workers')
    plt.ylabel('Network overhead (sec)')
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_file')
    parser.add_argument('--num_workers')
    parser.add_argument('--num_ps')
    parser.add_argument('--model_name')
    parser.add_argument('--ps_bandwidth')
    args = parser.parse_args()

    assert args.model_name in supported_models

    result_file_list = []
    base_file = args.base_file
    
    for wk_index in range(int(args.num_workers)):
        file_name = base_file + '/wk' + str(wk_index)
        result_file_list.append(file_name)

    for ps_index in range(int(args.num_ps)):
        file_name = base_file + '/ps' + str(ps_index)
        result_file_list.append(file_name)

    # Present results by device
    device_set = []
    src_device_event = {}
    src_dst_count = {}
    src_dst_bytes = {}
    # Present results based on occurance
    time_event = []

    for result_file in result_file_list:
        with open(result_file) as f:
            lines = f.readlines()

            for line in lines:
                split_line = split_result_line(line, args.model_name)

                for result in split_line:
                    send_time, send_bytes, edge_dict, src_device, dst_device, raw_edgename = result
                    if send_time is None:
                        continue

                    if src_device not in device_set: device_set.append(src_device)
                    if dst_device not in device_set: device_set.append(dst_device)

                    # Record per-flow information
                    flow = (src_device, dst_device)
                    if flow not in src_dst_count: src_dst_count[flow] = 0
                    if flow not in src_dst_bytes: src_dst_bytes[flow] = 0
                    src_dst_count[flow] += 1
                    src_dst_bytes[flow] += (send_bytes * 8 / (10 ** 9))
                
                    # Store the results by time
                    event_tuple = (send_time, send_bytes, edge_dict, src_device, dst_device, raw_edgename)
                    time_event.append(event_tuple)
                    
    # Sort the tuple by 
    time_event = sorted(time_event, key=lambda x: x[0])

    # Sort the tuple by time_event
    worker_device_set = []
    ps_device_set = []

    for device in device_set:
        # Change to CPU if doing per core training
        if 'GPU' in device and 'job:worker' in device:
            worker_device_set.append(device)
        elif 'CPU' in device and 'job:ps' in device:
            ps_device_set.append(device)
        else:
            print 'Device {} not an important device'.format(device)

    distribution_events = detect_distribution_events(time_event,
                                                     args.model_name,
                                                     worker_device_set,
                                                     ps_device_set,
                                                     project_more_workers=False)
    
    # For aggregation, just aggregate across workers
    aggregation_events = detect_aggregation_events(time_event,
                                                   args.model_name,
                                                   ['/job:worker/replica:0/task:1/device:GPU:0'],
                                                   ps_device_set,
                                                   project_more_workers=False)

    num_workers_to_consider = range(16)
    # In Gbps
    ps_bandwidth_to_consider = float(args.ps_bandwidth)

    distr_wk_bits = {}
    agg_wk_bits = {}

    for num_workers in num_workers_to_consider:
        distr_wk_bits[num_workers] = compare_times(distribution_events, num_workers, ps_bandwidth_to_consider, for_aggregation=False)
        agg_wk_bits[num_workers] = compare_times(aggregation_events, num_workers, ps_bandwidth_to_consider, for_aggregation=True)

    plot_worker_remaining_bits(distr_wk_bits, agg_wk_bits, ps_bandwidth_to_consider, args.model_name)
    exit()

            
    '''
    Plotting section of the code!!

    Parse for plotting
    '''
    flow_for_plot = {}
    for event in time_event:
        send_bytes = event[1]
        send_time = event[0]
        src = event[3]
        dst = event[4]
        flow = (src,dst)

        if flow not in flow_for_plot: flow_for_plot[flow] = {}
        
        if send_time not in flow_for_plot[flow]:
            flow_for_plot[flow][send_time] = send_bytes
        else:
            flow_for_plot[flow][send_time] += send_bytes

    print flow_for_plot
    
    with open(output_filename,'wb') as out:
        csv_out=csv.writer(out)
        csv_out.writerow(['time, send_bytes, edge_num, send_device, rcv_device'])
        for event in time_event:
            csv_out.writerow(event)

    plot_send_times(flow_for_plot, worker_device_set, ps_device_set)

    
    
    
