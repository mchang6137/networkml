import csv
from parse_step_times import *

# Plot the spread of send times by flow
def plot_send_times(worker_send_time_bytes):
    all_lines = []
    for flow in worker_send_time_bytes:
        lists = sorted(worker_send_time_bytes[flow].items())
        x,y = zip(*lists)
        line, = plt.plot(x,y,label=str(flow))
        all_lines.append(line)
    plt.legend(handles=all_lines)
    plt.show()

# Separates a single iteration of the update
# Returns the events that occured in each step (in order!)
# Record just for one source device and extrapolate!!!
def separate_one_iteration(time_events):
    accumulation_progress = False
    distr_event = []

    dst_devices = ['/job:worker/replica:0/task:1/device:GPU:0', '/job:worker/replica:0/task:1/device:CPU:0']
    worker_alignment = '/job:worker/replica:0/task:1/device:CPU:0'
    chief_ps = '/job:ps/replica:0/task:0/device:CPU:0'

    time_min = 0
    time_max = 0

    # Find a sync edge
    non_chief_sync_edge = 'sync_replicas/AccumulatorApplyGradient'
    for event in time_events:
        src_device = event[3]
        if src_device != chief_ps:
            if non_chief_sync_edge == event[5]:
                continue
            elif non_chief_sync_edge in event[5]:
                non_chief_sync_edge = event[5]

    # Collect the events from a single iteration
    in_iteration = False
    one_iteration = []
    sync_counter = 0
    found_sync_edge = False
    for event in time_events:
        bytes_sent = event[1]
        src_device = event[3]
        dst_device = event[4]
        event_name = event[5]
        
        if src_device == chief_ps:
            sync_edge = 'global_step'
            if event_name == sync_edge and not in_iteration:
                if dst_device == worker_alignment:
                    in_iteration = True
	    elif event_name != sync_edge and in_iteration:
                one_iteration.append(event)
            elif event_name == sync_edge and in_iteration:
                if dst_device == worker_alignment:
                    in_iteration = False
                    break
        else:
            if event_name == non_chief_sync_edge:
                sync_counter += 1
            if event_name != non_chief_sync_edge and in_iteration:
	        one_iteration.append(event)

            if event_name == non_chief_sync_edge and not in_iteration and sync_counter == 11:
                time_min = event[0]
                in_iteration = True
            elif event_name == non_chief_sync_edge and in_iteration and sync_counter == 13:
                in_iteration = False
                break

    if in_iteration:
        print 'Exited wrong'
        exit()

    # Filter out undesirable events
    distr_event = []
    for event in one_iteration:
        bytes_sent = event[1]
        src_device = event[3]
        dst_device = event[4]
        event_name = event[5]

        if dst_device not in dst_devices:
            continue
        if 'sync_replicas/AccumulatorApplyGradient' in event_name:
            continue
        if bytes_sent == 0:
            continue
        
        distr_event.append(event)
            

        '''

    for event in time_events:
        bytes_sent = event[1]
        src_device = event[3]
        dst_device = event[4]
        event_name = event[5]

        if src_device == chief_ps:
            if event_name == 'global_step' and dst_device == worker_alignment and accumulation_progress:
                distr_event.append(event)
		time_max = event[0]
                break
            elif event_name == 'global_step' and dst_device == worker_alignment and accumulation_progress is False:
                distr_event.append(event)
                accumulation_progress = True
                time_min = event[0]
            elif 'global_step' != event_name and accumulation_progress:
                if dst_device in dst_devices:
                    distr_event.append(event)
        '''

    return distr_event

def measure_cumm_bytes(time_events):
    total_bytes = 0
    for event in time_events:
        bytes_sent = event[1]
        total_bytes += bytes_sent
    return total_bytes

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #parser.add_argument('--base_file')
    parser.add_argument('--max_ps')
    parser.add_argument('--model_name')
    args = parser.parse_args()

    base_dir = './distribution_data/{}/'.format(args.model_name)
    
    for num_ps in range(int(args.max_ps)+1):
        bytes_in_distr = 0
        #num_ps = 2
        ps_base_dir = base_dir + '{}ps/'.format(num_ps)
        for ps_id in range(num_ps):
            #ps_id = 1
            ps_file = ps_base_dir + 'ps' + str(ps_id) + '.txt'
            #print ps_file
            events = parse_result_file([ps_file], args.model_name)
            distr_events = separate_one_iteration(events)
            bytes_in_distr += measure_cumm_bytes(distr_events)
            #print bytes_in_distr / (10 ** 6)
        mb_in_distr = bytes_in_distr / (10 ** 6)
        print 'For {} ps, we use {} MB bytes in total'.format(num_ps, mb_in_distr)

    exit()

    # Calculate initial spreads, etc.
    initial_time = time_event[0][0]
    worker_spread = {}
    worker_time_byte = {}
    worker_byte = {}
    for event in time_event:
        time_delta = event[0] - initial_time
        bytes_to_send = float(event[1])
        edgename = event[5]
        dst = event[4]
        src = event[3]

        if 'worker' not in dst:
            continue
        if 'ps' not in src:
            continue
        
        if dst not in worker_spread:
            worker_spread[dst] = []
            worker_time_byte[dst] = {}

        if dst not in worker_byte:
            worker_byte[dst] = bytes_to_send
        else:
            worker_byte[dst] += bytes_to_send
            
        if time_delta not in worker_time_byte[dst]:
            worker_time_byte[dst][time_delta] = bytes_to_send
        else:
            worker_time_byte[dst][time_delta] += bytes_to_send
            
        worker_spread[dst].append(time_delta)
    print worker_byte

    #for worker in worker_spread:
    #    print 'Worker {}, spread is {}'.format(worker, worker_spread[worker])
    #    print 'Time diff is {}'.format(worker_spread[worker][-1][0] - worker_spread[worker][0][0])


    plot_send_times(worker_time_byte)

        
    '''
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
   '''
