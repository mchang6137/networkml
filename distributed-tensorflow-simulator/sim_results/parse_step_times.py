import csv
import argparse

# Example Line that is read: 1510608248590 Send data with estimated 512 bytes. Edge name: edge_19288_gradients/inception_v3/mixed_17x17x768b/branch7x7/Conv/BatchNorm/batchnorm/sub_grad/tuple/control_dependency. src_device: /job:worker/replica:0/task:0/device:GPU:0. dst_device: /job:ps/replica:0/task:0/device:CPU:0
def split_result_line(raw_events):
    event_list = []
    raw_events = raw_events.replace('\n', '')

    if raw_events == '':
        return [(None, None, None, None, None)]

    # Begin by checking to see if the line spacing is messed up
    job_count = raw_events.count('job')
    num_events = job_count / 2

    if num_events == 1:
        raw_events = raw_events[1:]
        event_list.append(raw_events)
        send_time_str = raw_events.split(' ')[0]
    else:
        # assumes all these times are the same unmber of sigfigs
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
        # Retrieve the send time
        send_time_str = raw_events.split(' ')[0]
        send_time = float(send_time_str)

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
        #print 'At time {}, {} bytes were sent from {} to {}'.format(send_time, send_bytes, src_device, dst_device)

        edge_string = 'Edge name: '
        edge_index = results.index(edge_string)
        edge_end = results.index('. src_device')
        edge_name = results[edge_index + len(edge_string):edge_end]

        event_result.append((send_time, send_bytes, src_device, dst_device, edge_name))

    return event_result

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

    print(result_file_list)

    # Present results by device
    src_device_event = {}
    # Present results based on occurance
    time_event = []
    
    for result_file in result_file_list:
        with open(result_file) as f:
            lines = f.readlines()

            for line in lines:
                split_line = split_result_line(line)

                for result in split_line:
                    send_time, send_bytes, src_device, dst_device, edge_name = result
                    if send_time is None:
                        continue
                
                    # Store the results by device
                    if src_device not in src_device_event: src_device_event[src_device] = []
                    device_event_details = (send_time, send_bytes, dst_device)
                    src_device_event[src_device].append(device_event_details)
            
                    # Store the results by time
                    event_tuple = (send_time, send_bytes, src_device, dst_device, edge_name)
                    time_event.append(event_tuple)

    # Sort the tuple by 
    time_event = sorted(time_event, key=lambda x: x[0])

    print(list(src_device_event.keys()))
    #exit()
    
    output_filename = 'sorted_time_{}w_{}ps'.format(args.num_workers, args.num_ps)
    with open(output_filename,'wb') as out:
        csv_out=csv.writer(out)
        csv_out.writerow(['time, send_bytes, send_device, rcv_device, edge_name'])
        for event in time_event:
            csv_out.writerow(event)

    occurances = {}
    for event in time_event:
        if "ps" not in  event[2]:
            a=0
            continue
        if "ps" not in event[3]:
            b=0
            continue
        if event[4] not in occurances:
            occurances[event[4]] = "[{} : {}]".format(event[2], event[3])
        else:
            occurances[event[4]] += "[{} : {}]".format(event[2], event[3])
    klist = []
    for key in list(occurances.keys()):
        bloop = ["", 0]
        bloop[0] = key
        try:
            bloop[1] = int(key[5:key.replace('_', '-', 1).index('_')])
        except:
            bloop[1] = 999999999999999
        klist.append(bloop)
    klist.sort(key=lambda bloop: bloop[1])
    f = open("ps2ps.txt", "w")
    for key in klist:
        f.write("%s, \t%s\n" % (key[0], occurances[key[0]]))

    
    
    
