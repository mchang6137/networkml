import os
import numpy as np
import time

ps_list = ['34.210.149.71:2222', '54.68.71.35:2222', '52.10.74.229:2222', '34.210.167.242:2222']
#Comment out the worker from the worker list that is not running the experiments
worker_list = ['34.208.216.67', '35.164.63.183']
worker_cores = 32

def run(cmd):
  print cmd
  os.system(cmd)

#Parameter servers are located at another machine
def run_dist(batch_size, n_worker, n_ps):
  run("rm -rf /tmp/tf_run; mkdir /tmp/tf_run; rm -rf /tmp/imagenet_train/")
  run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches")
  wk_str = ",".join(["localhost:222" + str(i) for i in range(n_worker)])
  wk_str += ","
  for worker in worker_list:
    wk_str += ",".join(["{}:222".format(worker) + str(i) for i in range(n_worker)])
    wk_str += ","
  wk_str = wk_str[:-1]
    
  ps_str = ''
  for ps_ip in ps_list[:n_ps]:
    ps_str += ps_ip + ','
  ps_str = ps_str[:-1]

  for i in range(n_worker):
    print "worker", i
    core_str = str(i) + "," + str(i + 16) + ","
    core_str += str(i+8) + "," + str(i + 16 + 8)
    
    run("CUDA_VISIBLE_DEVICES=%s taskset -c %s $HOME/models/inception/bazel-bin/inception/imagenet_distributed_train --batch_size=%s --data_dir=$HOME/imagenet-data --job_name='worker' --task_id=%s --ps_hosts=%s --worker_hosts=%s &> /tmp/tf_run/worker%s.log &" % (i, core_str, batch_size, i, ps_str, wk_str, i))
    run("sleep 1")

def run_one(batch_size, n_worker):
  run("rm -rf /tmp/tf_run; mkdir /tmp/tf_run; rm -rf /tmp/imagenet_train/")
  run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches")
  run("export LD_LIBRARY_PATH=/usr/local/cuda/extras/CUPTI/lib64:$LD_LIBRARY_PATH; unbuffer bazel-bin/inception/imagenet_train --num_gpus=%s --batch_size=%s --train_dir=/tmp/imagenet_train --data_dir=$HOME/imagenet-data &> /tmp/tf_run/worker0.log &" % (n_worker, batch_size * n_worker))

def collect():
  s = []
  with open("/tmp/tf_run/worker0.log") as f:
    for l in f:
      #INFO:tensorflow:Worker 0: 2017-04-15 00:14:43.948375: step 19, loss = 12.85(17.0 examples/sec; 1.888  sec/batch)
      #2017-04-15 03:57:55.735478: step 0, loss = 13.09 (2.1 examples/sec; 15.070 sec/batch)
      try:
        if l.endswith("sec/batch)\n"):
          a = l.split(" ")
          #print l
          if a[4] == "step" and int(a[5].replace(",","")) > 40:
            s.append(float(a[10]))
          elif a[2] == "step" and int(a[3].replace(",","")) > 40:
            s.append(float(a[9]))
      except Exception as e:
          print "Err %s" % e, l
  return [np.mean(s), np.std(s)]

def collect_json(b, w, p, dist):
  path = "json/%s_batch_%s_worker_%s_ps_%s/" % ("emu" if dist else "single", b, w, p)
  run("rm -rf %s" % path)
  run("mkdir -p %s" % path)
  run("mv *.json %s" % path)
  print "json file at %s" % path

def execute(batch_size, n_worker, n_ps, dist, json):
  wait_time = 400 if json else 600
  wait_time += 0 if dist else 300
  if not dist:
    run_one(batch_size, n_worker)
    time.sleep(wait_time)
    run("pkill -f imagenet_train.py")
  else:
    run_dist(batch_size, n_worker, n_ps)
    time.sleep(wait_time)
    run("pkill -f imagenet_distributed_train.py")
  #run("for i in `ps aux | grep imagenet_distributed_train.py | awk '{print $2}'`; do kill -9 $i; done")
  if json:
    collect_json(batch_size, n_worker, n_ps, dist)
  else:
    r = collect()
    r_str = "%s %s %s %s %s %s %s" % (time.time(), dist, batch_size, n_worker, n_ps, r[0], r[1])
    print r_str
    run("echo \"%s\" >> result.txt" % r_str)

def run_all(dist, json):
  run("echo \"\n\n\nTime dist batch worker ps avg std\" >> result.txt")
  num_workers_per_machine = 4
  num_ps = [1,2,3,4]
  for num_ps in num_ps:
    execute(32, num_workers_per_machine, num_ps, dist, json)
    #Wait 200 seconds between experiments when running distributed
    time.sleep(200)
    

run_all(dist = True, json = False)

