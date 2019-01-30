import os
import csv

average_traces = {'vgg16' : 'vgg16/8/wk7_26.csv',
                      'resnet-200' : 'resnet-200/4/wk1_42.csv',
                      'resnet-101' : 'resnet-101/12/wk0_43.csv',
                      'inception-v3' : 'inception-v3/8/wk0_43.csv'}

model_names = average_traces.keys()
basedir = './csv'
bws = [x * (10 ** 9) for x in [10, 25]]

for model in model_names:
    for bw in bws:
        print(model)
        wk_path = os.path.join(basedir, average_traces[model])
        trace = open(wk_path).readlines()
        bits_added = {}
        model_size = 0.0
        for ev in trace:
            if ev.startswith("//") or ev.startswith('"'):
                continue
            parts = ev.strip().split(',')
            time = float(parts[0])
            size = float(parts[1])
            if time not in bits_added:
                bits_added[time] = 0.0
            bits_added[time] += size
            model_size += size
        time = 0.0
        queue = 0.0
        keys = bits_added.keys()
        dest_path = os.path.join("./dom_results", model + "_net_use_{}.csv".format(str(bw)))
        with open(dest_path, "wb") as f:
            writer = csv.writer(f, delimiter=",")
            writer.writerow(["time", "queue", "compute"])
            while time <= max(keys) or queue > 0.0:
                queue -= bw * 0.001
                if queue < 0.0:
                    queue = 0.0
                if time in bits_added:
                    queue += bits_added[time]
                writer.writerow([time, queue / model_size, "" if time != max(keys) else 1.0])
                time += 1.0

