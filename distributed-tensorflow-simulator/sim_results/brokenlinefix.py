result_file = "1ps_2wk/ps0"
fin = open(result_file)
fout = open(result_file + "fixed", "w")
lines = fin.readlines()
total_events = 0
for raw_events in lines:
    num_events = raw_events.count('Send')
    total_events += num_events
    if num_events == 0:
        continue
    elif num_events == 1:
        fout.write(raw_events)
    else:
        # assumes all these times are the same unmber of sigfigs
        
        send_time_str = raw_events.split(' ')[0]
        send_time_len = len(send_time_str)

        for event in range(num_events - 1):
            split_string = ' Send'
            split_index = raw_events.index(split_string, raw_events.index(split_string)+1)
            split_index = split_index - send_time_len
            fout.write(raw_events[:split_index] + "\n")
            raw_events = raw_events[split_index:]

        fout.write(raw_events)