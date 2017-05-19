from fabric.api import *
from fabric.contrib import project
import time
import boto3
import os

#Experiment Settings
exp_wait_time = 700
worker_per_machine = 4
batch_size = 32

#Environment settings that were originally setup
tgt_ami = 'ami-8ca83fec'
AWS_REGION = 'us-west-2'
AWS_AVAILABILITY_ZONE = 'us-west-2b'
my_aws_key = 'michael'
worker_base_name = "mygpu"
ps_base_name = "ps"
NUM_GPUS=2
NUM_PARAM_SERVERS=4
all_instance_names = [worker_base_name + str(x) for x in range(NUM_GPUS)] + [ps_base_name + str(x) for x in range(NUM_PARAM_SERVERS)]

CONDA_DIR = "$HOME/anaconda"
WORKER_TYPE = 'p2.8xlarge'
#Parameter Server with 10Gpbs
PS_TYPE = 'c4.8xlarge'

USER = os.environ['USER']

# this is a dumb hack but whatever
if os.path.exists("fabfile_{}.py".format(USER)):
    exec("from fabfile_{} import *".format(USER))

def tags_to_dict(d):
    return {a['Key'] : a['Value'] for a in d}

#Roles and hosts should have the same names
def get_target_instance():
    role_to_host = {}
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    host_list = []
    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            d = tags_to_dict(i.tags)
            if d['Name'] in env.hosts:
                role_to_host[d['Name']] = 'ec2-user@{}'.format(i.public_dns_name)
                host_list.append('ec2-user@{}'.format(i.public_dns_name))
            elif len(env.hosts) == 0:
                role_to_host[d['Name']] = 'ec2-user@{}'.format(i.public_dns_name)
                host_list.append('ec2-user@{}'.format(i.public_dns_name))
    env.hosts.extend(host_list)
    print "found", role_to_host
    return role_to_host

env.disable_known_hosts = True
env.warn_only = True
env.roledefs.update(get_target_instance())

#Start the parameter servers before starting the workers
@task
@parallel
def run_ps():
    run("rm -rf /tmp/tf_run; mkdir /tmp/tf_run; rm -rf /tmp/imagenet_train/")
    run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches")
    
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    host_string = ''

    if env.hosts[0][:2] == 'ps':
        host_string = env.hosts[0]
    else:
        print 'exiting!!!!'
        exit()
    
    all_worker = get_all_workers()
    all_ps = get_all_ps()
    
    #Start all the parameter servers across all machines
    my_ip = get_my_ip(host_string)
    task_id = all_ps.index(my_ip)

    #Start all the parameter servers, it doesn't matter how many they are registering
    ps_str = ''
    ps_str = ",".join(x + ":2222" for x in all_ps)

    #Assign 
    wkr_str = ''
    for worker in all_worker:
        wkr_str += ','.join(worker+':'+str(x+2200) for x in range(worker_per_machine))
        wkr_str += ','
    wkr_str = wkr_str[:-1]

    command = "CUDA_VISIBLE_DEVICES='' nohup $HOME/models/inception/bazel-bin/inception/imagenet_distributed_train --batch_size=%s --job_name='ps' --task_id=%s --ps_hosts=%s --worker_hosts=%s &> /tmp/tf_run/ps%s.log &" % (batch_size, task_id, ps_str, wkr_str, task_id)
    print command
    import sys
    run(command, shell=True, shell_escape=True, stderr=sys.stdout, pty=False)

def get_all_workers():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    all_worker = []
    all_reservations = [x for x in ec2_client.describe_instances()['Reservations']]
    for reservation in all_reservations:
        try:
            instance_type = reservation['Instances'][0]['InstanceType']
            ip = ''
            if instance_type != PS_TYPE:
                ip = reservation['Instances'][0]['PublicIpAddress']
                all_worker.append(ip)
        except:
            continue
    return all_worker

def get_all_ps():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    #Start all the parameter servers across all machines
    all_ps = []

    all_reservations = [x for x in ec2_client.describe_instances()['Reservations']]
    for reservation in all_reservations:
        try:
            instance_type = reservation['Instances'][0]['InstanceType']
            ip = ''
            if instance_type == PS_TYPE:
                ip = reservation['Instances'][0]['PublicIpAddress']
                all_ps.append(ip)
        except:
            continue

    return all_ps

def get_my_ip(host_string):
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    all_reservations = [x for x in ec2_client.describe_instances()['Reservations']]
    for reservation in all_reservations:
        try:
            ip = reservation['Instances'][0]['PublicIpAddress']
            instance_name = reservation['Instances'][0]['Tags'][0]['Value']
            if instance_name == host_string:
                return ip
        except:
            print 'SIGH'

@task
@parallel
def run_worker():
    num_workers_per_machine = 2
    num_ps = [1,2,4,8]
    for ps in num_ps:
        execute(32, num_workers_per_machine, ps)

def execute(batch_size, n_worker, n_ps):
    wait_time = 700
    run_dist(n_ps)
    time.sleep(wait_time)
    run("pkill -f imagenet_distributed_train.py")
    
    r = collect()
    r_str = "%s %s %s %s %s %s" % (time.time(), batch_size, n_worker, n_ps, r[0], r[1])
    print r_str
    run("echo \"%s\" >> result.txt" % r_str)

def collect():
  s = []
  #with open("/tmp/tf_run/worker0.log") as f:
  with open("$HOME/models/inception") as f:
    for l in f:
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

def run_dist(n_ps):
    run("rm -rf /tmp/tf_run; mkdir /tmp/tf_run; rm -rf /tmp/imagenet_train/")
    run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches")
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    
    host_string = ''
    if env.hosts[0][:2] == 'my':
        host_string = env.hosts[0]
    else:
        print 'exiting!!!!'
        exit()

    #Task range should be based on mygpuX, where X is an integer.
    #The tasks on a particular machine should be given by X * workers_per_machine to (X+1) * workers_per_machine

    all_worker = get_all_workers()
    all_ps = get_all_ps()

    #Start all the parameter servers across all machines
    my_ip = get_my_ip(host_string)
    gpu_num = int(host_string[-1])
    task_id = gpu_num * worker_per_machine

    #Start all the parameter servers, it doesn't matter how many they are registering
    ps_str = ''
    ps_str = ",".join(x + ":2222" for x in all_ps[:n_ps])

    #Assign
    wkr_str = ''
    for worker in all_worker:
        wkr_str += ','.join(worker+':'+str(x+2200) for x in range(worker_per_machine))
        wkr_str += ','
    wkr_str = wkr_str[:-1]

    for i in range(worker_per_machine):
        print "worker", i
        core_str = str(i) + "," + str(i + 16) + ","
        core_str += str(i+8) + "," + str(i + 24)
        taskid = task_id + i
    
        m = run("CUDA_VISIBLE_DEVICES=%s taskset -c %s nohup /home/ec2-user/models/inception/bazel-bin/inception/imagenet_distributed_train --batch_size=%s --data_dir=$HOME/imagenet-data --job_name='worker' --task_id=%s --ps_hosts=%s --worker_hosts=%s &> /tmp/tf_run/worker%s.log &" % (i, core_str, batch_size, taskid, ps_str, wkr_str, taskid), pty=False, shell=True, stderr-sys.stdout,shell_escape=True)
        run("echo 512 > hi.txt &")
        run("sleep 1")
