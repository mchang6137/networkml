import statistics
import sys
import csv

if len(sys.argv) < 2:
  print('Need input baseline CSV file name as first argument.')
  exit(1)


if len(sys.argv) < 3:
  print('Need input test CSV file name as second argument.')
  exit(1)

if len(sys.argv) < 4:
  print('Need output CSV file name as third argument.')
  exit(1)

baseline_filename = sys.argv[1]
y_filename = sys.argv[2]
out_filename = sys.argv[3]

with open(baseline_filename, 'r') as f, open(y_filename, 'r') as h, open(out_filename, 'w') as g:
  baseline_data = {}
  step_index = None
  ps_index = None
  worker_index = None
  iter_index = None
  for i, line in enumerate(csv.reader(f, delimiter=',')):
    if i == 0:
      step_index = line.index('step_num')
      ps_index = line.index('num_ps')
      worker_index = line.index('num_workers')
      iter_index = line.index('iteration_time')
    else:
      # data format: [step_num][ps][worker] -> iter_time
      step_num = line[step_index]
      iter_time = float(line[iter_index])
      num_ps = line[ps_index]
      num_workers = line[worker_index]
      temp = baseline_data
      if step_num not in temp:
        temp[step_num] = {}
      temp = temp[step_num]
      if num_ps not in temp:
        temp[num_ps] = {}
      temp = temp[num_ps]
      assert num_workers not in temp
      temp[num_workers] = round(iter_time, 4)

  test_data = {}
  for i, line in enumerate(csv.reader(h, delimiter=',')):
    if i != 0:
      step_num = line[step_index]
      iter_time = float(line[iter_index])
      num_ps = line[ps_index]
      num_workers = line[worker_index]
      temp = test_data
      if step_num not in temp:
        temp[step_num] = {}
      temp = temp[step_num]
      if num_ps not in temp:
        temp[num_ps] = {}
      temp = temp[num_ps]
      assert num_workers not in temp
      temp[num_workers] = round(iter_time, 4)

  for step_num in test_data.keys():
    for ps in ['1', '2', '4', '8']:
      for worker in ['2', '4', '8', '16', '32']:
        if worker in test_data[step_num][ps]:
          test = test_data[step_num][ps][worker]
          baseline_val = baseline_data[step_num][ps][worker]
          percent = (baseline_val - test) / baseline_val
          test_data[step_num][ps][worker] = {}
          test_data[step_num][ps][worker]['test'] = test
          test_data[step_num][ps][worker]['baseline_percent'] = percent * 100

  g.write('num_ps,num_workers,median,neg bar,pos bar\n')
  for ps in ['1', '2', '4', '8']:
    for worker in ['2', '4', '8', '16', '32']:
      vals = []
      for step_num in test_data.keys():
        if worker in test_data[step_num][ps]:
          vals.append(test_data[step_num][ps][worker]['baseline_percent'])
      median = round(statistics.median(vals), 4)
      neg_bar = str(round(abs(median - min(vals)), 4))
      pos_bar = str(round(abs(max(vals) - median), 4))
      out_line = ','.join([ps, worker, str(median), neg_bar, pos_bar])
      g.write(out_line)
      g.write('\n')
    g.write(',,,,,,\n')

