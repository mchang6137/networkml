import statistics
import sys
import csv

if len(sys.argv) < 2:
  print('Need input CSV file name as first argument.')
  exit(1)

if len(sys.argv) < 3:
  print('Need output CSV file name as second argument.')
  exit(1)

in_filename = sys.argv[1]
out_filename = sys.argv[2]

with open(in_filename, 'r') as f, open(out_filename, 'w') as g:
  data = {}
  step_index = None
  multi_index = None
  agg_index = None
  ps_index = None
  worker_index = None
  iter_index = None
  striping_index = None
  even_index = None
  rack_index = None
  bw_index = None
  for i, line in enumerate(csv.reader(f, delimiter=',')):
    if i == 0:
      step_index = line.index('step_num')
      multi_index = line.index('use_multicast')
      agg_index = line.index('in_network_computation')
      ps_index = line.index('num_ps')
      worker_index = line.index('num_workers')
      iter_index = line.index('iteration_time')
      striping_index = line.index('striping')
      even_index = line.index('optimal_param_distribution')
      rack_index = line.index('on_same_rack')
      bw_index = line.index('worker_send_rate')
    else:
      if i == 5:
        # collect bw, rack, striping, param_distr info
        data['bw'] = line[bw_index]
        data['stripe'] = line[striping_index]
        data['rack'] = line[rack_index]
        data['even'] = line[even_index]

      # data format: [multicast][agg][step_num][ps][worker] -> iter_time

      step_num = line[step_index]
      multicast = line[multi_index]
      agg = line[agg_index]
      iter_time = float(line[iter_index])
      num_ps = line[ps_index]
      num_workers = line[worker_index]
      temp = data
      if multicast not in temp:
        temp[multicast] = {}
      temp = temp[multicast]
      if agg not in temp:
        temp[agg] = {}
      temp = temp[agg]
      if step_num not in temp:
        temp[step_num] = {}
      temp = temp[step_num]
      if num_ps not in temp:
        temp[num_ps] = {}
      temp = temp[num_ps]
      assert num_workers not in temp
      temp[num_workers] = round(iter_time, 4)

  # find percent improvement over baseline
  for multicast in ['0', '1']:
    for agg in ['0', '1']:
      arr = data[multicast][agg]
      baseline = data['0']['0']
      if multicast == '1' or agg == '1':
        for step_num in arr.keys():
          for ps in ['1', '2', '4', '8']:
            for worker in ['2', '4', '8', '16', '32']:
              if worker in arr[step_num][ps]:
                test = arr[step_num][ps][worker]
                baseline_val = baseline[step_num][ps][worker]
                percent = (baseline_val - test) / baseline_val
                arr[step_num][ps][worker] = {}
                arr[step_num][ps][worker]['test'] = test
                arr[step_num][ps][worker]['baseline_percent'] = percent * 100

  # aggregate data properly (multicast/agg vs. baseline)
  g.write('multicast,aggregation,num_ps,num_workers,median,neg bar,pos bar\n')
  g.write('BW: {}Gbps, Striping: {}, Optimal Param Distribution: {}, On Same Rack: {},,,\n'.format(data['bw'], data['stripe'], data['even'], data['rack']))
  for multicast in ['0', '1']:
    for agg in ['0', '1']:
      if multicast == '1' or agg == '1':
        arr = data[multicast][agg]
        g.write('{} Multicast,{} Agg,,,,,\n'.format(multicast, agg))
        for ps in ['1', '2', '4', '8']:
          for worker in ['2', '4', '8', '16', '32']:
            vals = []
            for step_num in arr.keys():
              if worker in arr[step_num][ps]:
                vals.append(arr[step_num][ps][worker]['baseline_percent'])
            median = round(statistics.median(vals), 4)
            neg_bar = str(round(abs(median - min(vals)), 4))
            pos_bar = str(round(abs(max(vals) - median), 4))

            out_line = ','.join([multicast, agg, ps, worker, str(median), neg_bar, pos_bar])
            g.write(out_line)
            g.write('\n')
          g.write(',,,,,,\n')


  # multicast+agg vs. multicast: obtain data
  g.write('multicast + aggregation vs. multicast info\n')
  arr = data['1']['1']
  baseline = data['1']['0']
  for step_num in arr.keys():
    for ps in ['1', '2', '4', '8']:
      for worker in ['2', '4', '8', '16', '32']:
        if worker in arr[step_num][ps]:
          test = arr[step_num][ps][worker]['test']
          baseline_val = baseline[step_num][ps][worker]['test']
          percent = (baseline_val - test) / baseline_val
          arr[step_num][ps][worker]['multi_percent'] = percent * 100

  # multicast+agg vs. multicast: write data
  arr = data['1']['1']
  for ps in ['1', '2', '4', '8']:
    for worker in ['2', '4', '8', '16', '32']:
      vals = []
      for step_num in arr.keys():
        if worker in arr[step_num][ps]:
          vals.append(arr[step_num][ps][worker]['multi_percent'])
      median = round(statistics.median(vals), 4)
      neg_bar = str(round(abs(median - min(vals)), 4))
      pos_bar = str(round(abs(max(vals) - median), 4))

      out_line = ','.join([multicast, agg, ps, worker, str(median), neg_bar, pos_bar])
      g.write(out_line)
      g.write('\n')
    g.write(',,,,,,\n')

