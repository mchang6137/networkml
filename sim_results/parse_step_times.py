import csv
import argparse

# Example Line that is read: 1510608248590 Send data with estimated 512 bytes. Edge name: edge_19288_gradients/inception_v3/mixed_17x17x768b/branch7x7/Conv/BatchNorm/batchnorm/sub_grad/tuple/control_dependency. src_device: /job:worker/replica:0/task:0/device:GPU:0. dst_device: /job:ps/replica:0/task:0/device:CPU:0
def split_result_line(results):
    results = results.replace('\n', '')
    results = results[1:]
    try:
        send_time = float(results.split(' ')[0])

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
        print 'At time {}, {} bytes were sent from {} to {}'.format(send_time, send_bytes, src_device, dst_device)
        return send_time, send_bytes,src_device,dst_device
    except:
        print 'Skipping this line'
        return None, None, None, None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw_file')
    parser.add_argument('--num_workers')
    parser.add_argument('--num_ps')
    args = parser.parse_args()
    
    result_file_list = [args.raw_file]
    # Present results by device
    src_device_event = {}
    # Present results based on occurance
    time_event = []
    
    for result_file in result_file_list:
        with open(result_file) as f:
            lines = f.readlines()

            for line in lines:

                send_time, send_bytes, src_device, dst_device = split_result_line(line)
                if send_time is None:
                    continue
                
                # Store the results by device
                if src_device not in src_device_event: src_device_event[src_device] = []
                device_event_details = (send_time, send_bytes, dst_device)
                src_device_event[src_device].append(device_event_details)
            
                # Store the results by time
                event_tuple = (send_time, send_bytes, src_device, dst_device)
                time_event.append(event_tuple)

    # Sort the tuple by 
    sorted(time_event, key=lambda x: x[0])
    
    output_filename = 'sorted_time_{}w_{}ps'.format(args.num_workers, args.num_ps)
    with open(output_filename,'wb') as out:
        csv_out=csv.writer(out)
        csv_out.writerow(['time, send_bytes, send_device, rcv_device'])
        for event in time_event:
            csv_out.writerow(event)

    
    
    
