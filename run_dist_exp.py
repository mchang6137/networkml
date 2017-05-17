import os
import random
import time

pses = ["52.40.55.52"]
workers = [
"52.42.39.139",
"35.167.227.91",
"52.43.106.54",
"54.70.21.171",
"52.32.101.224",
"52.27.133.231",
"52.39.60.209"
        ]

def run(m, cmd):
  f = "/tmp/cmd" + str(random.randint(0,100000))
  c = "ssh ec2-user@" + m + " \"{ source ~/.bash_profile;" + cmd + "; } &> " + f + " &\""
  print c
  os.system(c)
  return (m, f)

def run_pses(cmd):
  for m in pses:
    run(m, cmd)

def run_workers(cmd):
  for m in workers:
    run(m, cmd)

def run_all(cmd):
  run_pses(cmd)
  run_workers(cmd)

def prepare():
  run_all("rm -rf /home/ec2-user/models")
  run_all("cd ~; git clone https://github.com/pxgao/models.git; cd models; git checkout distributed_breakdown; cd inception; bazel build inception/imagenet_distributed_train")
  time.sleep(4)

def run_exp(n_ps, n_w, batch_size):
  ps_str = ",".join([ pses[i] + ":221" + str(i)  for i in range(n_ps)])
  wk_str = ",".join([ workers[i] + ":222" + str(i) for i in range(n_w)])
  ps_result = []
  wk_result = []
  for i in range(n_ps):
    cmd = "killall -9 python; cd /home/ec2-user/models/inception; CUDA_VISIBLE_DEVICES='' bazel-bin/inception/imagenet_distributed_train --batch_size=%s --job_name='ps' --task_id=%s --ps_hosts=%s --worker_hosts=%s" % (batch_size, i, ps_str, wk_str)
    r = run(pses[i], cmd)
    ps_result.append(r)
  for i in range(n_w):
    cmd = "killall -9 python; cd /home/ec2-user/models/inception ;bazel-bin/inception/imagenet_distributed_train --batch_size=%s --data_dir=/home/ec2-user/imagenet-data --job_name='worker' --task_id=%s --ps_hosts=%s --worker_hosts=%s" % (batch_size, i, ps_str, wk_str)
    r = run(workers[i], cmd)
    wk_result.append(r)
  return (ps_result, wk_result)

#prepare()
run_exp(1, 1, 32)



