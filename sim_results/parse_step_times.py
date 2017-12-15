import csv
import argparse

import matplotlib.pylab as plt

# Example Line that is read: 1510608248590 Send data with estimated 512 bytes. Edge name: edge_19288_gradients/inception_v3/mixed_17x17x768b/branch7x7/Conv/BatchNorm/batchnorm/sub_grad/tuple/control_dependency. src_device: /job:worker/replica:0/task:0/device:GPU:0. dst_device: /job:ps/replica:0/task:0/device:CPU:0

# Edge Type Constants
GRADIENT_EDGE = 0
FORWARD_PROP_EDGE = 1
AGG_EDGE = 2
DISTRIBUTE_WEIGHTS = 3

# Parses the full edge name 
def parse_edge_name(train_op):
    print train_op
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
    if len(operation_hierarchy) == 2:
        if operation_hierarchy[1].split('_') == 'AddN':
            edge_name['type'] = 'AGG_EDGE'
            edge_name['op_scope'] = operation_hierarchy[1]
    # Forward pass in the direction of wk -> ps
    elif operation_hierarchy[0] == 'inception_v3':
        try:
            edge_name['variable_scope'] = operation_hierarchy[1]
            edge_name['operation_scope'] = operation_hierarchy[2]
            edge_name['operation'] = operation_hierarchy[3]
            edge_name['type'] = FORWARD_PROP_EDGE
        except:
            print operation_hierarchy
            print 'Failed to parse the above'
            exit()
    # Backwards pass in the direction of wk -> ps
    elif operation_hierarchy[0] == 'gradients':
         # Finds the AddN Operation that occurs to send gradients
        if len(operation_hierarchy) == 2:
            if operation_hierarchy[1].split('_') == 'AddN':
                edge_name['type'] = AGG_EDGE
                edge_name['operation_scope'] = operation_hierarchy[1]
        # wk -> ps, Forward pass
        elif operation_hierarchy[1] == 'inception_v3':
            edge_name['type'] = GRADIENT_EDGE
            edge_name['operation_scope'] = operation_hierarchy[2]
            edge_name['variable_scope'] = operation_hierarchy[3]
    # Gradient updates from ps -> wk
    elif 'weights' in operation_hierarchy:
        edge_name['type'] = DISTRIBUTE_WEIGHTS
        edge_name['variable_scope'] = operation_hierarchy[0]
        edge_name['operation_scope'] = operation_hierarchy[1]
        edge_name['operation'] = operation_hierarchy[2]

    return edge_name

# Find the events associated with various nodes in the graph
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

    print weight_lifetime

    time_diff = []
    for edge in weight_lifetime:
        if len(weight_lifetime[edge]['ps_to_worker']) == 0 or len(weight_lifetime[edge]['worker_to_ps']) == 0:
            continue
        diff = max(weight_lifetime[edge]['ps_to_worker']) - max(weight_lifetime[edge]['worker_to_ps'])
        time_diff.append(diff)

    print time_diff
                    
    exit()
        

def split_result_line(raw_events):
    event_list = []
    raw_events = raw_events.replace('\n', '')

    if raw_events == '':
        return [(None, None, None, None, None)]

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
            edge_dict = parse_edge_name(full_edgename)
        except:
            if 'edge' not in results:
                print 'This is a special train op'
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


        event_result.append((send_time, send_bytes, edge_dict, src_device, dst_device))

        '''
        except:
            print results
            continue

            previous_string = 'estimated '
            previous_index = results.index(previous_string)
            subsequent_index = results.index(' bytes')
            send_bytes = float(results[previous_index + len(previous_string):subsequent_index])
            if send_bytes <= 4:
                continue
            else:
                print 'Failed, must consider significant number of bytes'
                print results
                exit()
        '''

    return event_result

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
    print (total_bytes_ps_worker/total_bytes_worker_ps)

def compare_times(sorted_time_events):
    worker_device = '/job:worker/replica:0/task:0/device:GPU:0'
    ps_device = '/job:ps/replica:0/task:0/device:CPU:0'

    #ps_device = '/job:worker/replica:0/task:1/device:GPU:0'
    #worker_device = '/job:ps/replica:0/task:0/device:CPU:0'
    
    most_recent_send_event = 0

    time_byte = {}

    # Data Cleaning
    for event in sorted_time_events:
        send_time, send_bytes, edge_num, src_device, dst_device = event
        if src_device != worker_device or dst_device != ps_device:
            continue

        if send_bytes == 0:
            continue

        # Combine events that happened together
        if send_time in time_byte:
            time_byte[send_time] += send_bytes
        else:
            time_byte[send_time] = send_bytes

    # Current network throughput in Gbps        
    CURRENT_THROUGHPUT = 10.0
    outstanding_gb = 0

    num_workers = 16
    
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

        if bandwidth > CURRENT_THROUGHPUT:
            outstanding_gb = gb_to_send - (CURRENT_THROUGHPUT * times_to_send)
        else:
            outstanding_gb = 0

        print 'Required bandwidth is bandwidth {} Gbps'.format(bandwidth)
        print 'Amount sent is {}'.format(gb_to_send)
        print 'Amount of time is {}'.format(times_to_send)
        print 'Outstanding Gb is {}'.format(outstanding_gb)
        outstanding_time = outstanding_gb / CURRENT_THROUGHPUT
        print 'Time to send outstanding gb is {}'.format(outstanding_time)

    bytes_to_send = time_byte[sorted_times[-1]]
    bits_to_send = bytes_to_send * 8
    gb_to_send = num_workers * bits_to_send / (10 ** 9)
    gb_to_send += outstanding_gb
    
    print 'The last message is sent with {} bytes with {} bytes outstanding'.format(gb_to_send, outstanding_gb)
    time_to_send = gb_to_send / CURRENT_THROUGHPUT
    
    print 'It will take {} seconds'.format(time_to_send)
    remaining_time = outstanding_gb / CURRENT_THROUGHPUT
    print 'This Step has concluded. Time it takes to transmit remaining {} Gbits is {}'.format(outstanding_gb, remaining_time)

def plot_send_times(flow_event_time):
    all_lines = []
    for flow in flow_event_time:
        #if flow[0] != '/job:ps/replica:0/task:0/device:CPU:0' or flow[1] != '/job:worker/replica:0/task:1/device:GPU:0':
        #    continue

        print flow_event_time[flow]
        if len(flow_event_time[flow].keys()) < 10:
            continue

        lists = sorted(flow_event_time[flow].items())
        x,y = zip(*lists)
        line, = plt.plot(x,y,label=str(flow))
        all_lines.append(line)
    plt.legend(handles=all_lines)
    plt.show()
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_file')
    parser.add_argument('--num_workers')
    parser.add_argument('--num_ps')
    args = parser.parse_args()

    result_file_list = []
    base_file = args.base_file
    
    for wk_index in range(int(args.num_workers)):
        file_name = base_file + '/wk' + str(wk_index)
        result_file_list.append(file_name)

    for ps_index in range(int(args.num_ps)):
        file_name = base_file + '/ps' + str(ps_index)
        result_file_list.append(file_name)

    print result_file_list

    # Present results by device
    device_set = []
    src_device_event = {}
    src_dst_count = {}
    src_dst_bytes = {}
    # Present results based on occurance
    time_event = []

    flow_for_plot = {}
    
    for result_file in result_file_list:
        with open(result_file) as f:
            lines = f.readlines()

            for line in lines:
                split_line = split_result_line(line)

                for result in split_line:
                    send_time, send_bytes, edge_dict, src_device, dst_device = result
                    if send_time is None:
                        continue

                    if src_device not in device_set: device_set.append(src_device)
                    if dst_device not in device_set: device_set.append(dst_device)

                    flow = (src_device, dst_device)
                    if flow not in src_dst_count: src_dst_count[flow] = 0
                    if flow not in src_dst_bytes: src_dst_bytes[flow] = 0
                    src_dst_count[flow] += 1
                    src_dst_bytes[flow] += (send_bytes * 8 / (10 ** 9))
                
                    # Store the results by device
                    if src_device not in src_device_event: src_device_event[src_device] = []
                    device_event_details = (send_time, send_bytes, dst_device)
                    src_device_event[src_device].append(device_event_details)
            
                    # Store the results by time
                    event_tuple = (send_time, send_bytes, edge_dict, src_device, dst_device)
                    time_event.append(event_tuple)

                    # Store the events for the purpose of plotting
                    if flow not in flow_for_plot: flow_for_plot[flow] = {}
                    if send_time not in flow_for_plot[flow]:
                        flow_for_plot[flow][send_time] = send_bytes
                    else:
                        flow_for_plot[flow][send_time] += send_bytes
    
    # Sort the tuple by 
    time_event = sorted(time_event, key=lambda x: x[0])

    # Sort the tuple by time_event
    print device_set
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

    time_until_aggregation(time_event, worker_device_set, ps_device_set)

    compare_bytes_sent(time_event)
    compare_times(time_event)

    print 'Source->Dst counts are {}'.format(src_dst_count)
    
    output_filename = 'sorted_time_{}w_{}ps'.format(args.num_workers, args.num_ps)
    with open(output_filename,'wb') as out:
        csv_out=csv.writer(out)
        csv_out.writerow(['time, send_bytes, edge_num, send_device, rcv_device'])
        for event in time_event:
            csv_out.writerow(event)

    plot_send_times(flow_for_plot)

    
    
    
