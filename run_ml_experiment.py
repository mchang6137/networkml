from fabric.api import *
from fabric.contrib import project
import time
import boto3
import os
import numpy as np

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
dns_hostname = {}

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
                dns_hostname[i.public_dns_name] = d['Name']
                role_to_host[d['Name']] = 'ec2-user@{}'.format(i.public_dns_name)
                host_list.append('ec2-user@{}'.format(i.public_dns_name))
            elif len(env.hosts) == 0:
                dns_hostname[i.public_dns_name] = d['Name']
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
def run_ps(worker_per_machine=8, batch_size=32, num_ps=4, num_machines=1):
    run("pkill -f imagenet_distributed_train.py")
    worker_per_machine = int(worker_per_machine)
    batch_size = int(batch_size)
    num_ps = int(num_ps)
    num_machines = int(num_machines)
    
    try:
        dns_result = env.host_string.split('@')[1]
	host_string = dns_hostname[dns_result]
    except:
        exit()
        
    run("rm -rf /tmp/tf_run; mkdir /tmp/tf_run; rm -rf /tmp/imagenet_train/")
    run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches")
    
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    
    all_worker = get_all_workers()
    all_ps = get_all_ps()

    task_id = int(host_string[-1])
    
    #Start all the parameter servers across all machines
    my_ip = get_my_ip(host_string)

    ps_str = ''
    for	ps_index in range(num_ps):
	ps_ip =	all_ps['ps' + str(ps_index)]
	ps_str += (ps_ip + ':2222,')
    ps_str = ps_str[:-1]

    #Assign
    wkr_str = ''
    for machine_index in range(num_machines):
        worker = all_worker['mygpu' + str(machine_index)]
        wkr_str += ','.join(worker+':'+str(x+2200) for x in range(worker_per_machine))
        wkr_str += ','
    wkr_str = wkr_str[:-1]
    
    command = "CUDA_VISIBLE_DEVICES='' nohup $HOME/models/inception/bazel-bin/inception/imagenet_distributed_train --batch_size=%s --job_name='ps' --task_id=%s --ps_hosts=%s --worker_hosts=%s &> /tmp/tf_run/ps%s.log &" % (batch_size, task_id, ps_str, wkr_str, task_id)
    print command
    import sys
    run(command, shell=True, shell_escape=True, stderr=sys.stdout, pty=False)

#Returns a dict from hoststring -> IP Address
def get_all_workers():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    all_worker = {}
    all_reservations = [x for x in ec2_client.describe_instances()['Reservations']]
    for reservation in all_reservations:
        try:
            instance_type = reservation['Instances'][0]['InstanceType']
            ip = ''
            if instance_type != PS_TYPE:
                ip = reservation['Instances'][0]['PublicIpAddress']
                instance_name = reservation['Instances'][0]['Tags'][0]['Value']
                all_worker[instance_name] = ip
        except:
            continue
    return all_worker

#Returns a dict from hoststring -> IP address
def get_all_ps():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    #Start all the parameter servers across all machines
    all_ps = {}

    all_reservations = [x for x in ec2_client.describe_instances()['Reservations']]
    for reservation in all_reservations:
        try:
            instance_type = reservation['Instances'][0]['InstanceType']
            ip = ''
            if instance_type == PS_TYPE:
                ip = reservation['Instances'][0]['PublicIpAddress']
                instance_name = reservation['Instances'][0]['Tags'][0]['Value']
                all_ps[instance_name] = ip
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
def cleanup():
    run("pkill -f imagenet_distributed_train.py")
    
@task
@parallel
def run_worker(worker_per_machine, batch_size, num_ps, num_machines):
    run("pkill -f imagenet_distributed_train.py")
    worker_per_machine = int(worker_per_machine)
    batch_size = int(batch_size)
    num_ps = int(num_ps)
    num_machines = int(num_machines)
    execute(worker_per_machine, batch_size, num_ps, num_machines)

def execute(worker_per_machine, batch_size, num_ps, num_machines):
    wait_time = 700
    run_dist(worker_per_machine, batch_size, num_ps, num_machines)
    time.sleep(wait_time)
    run("pkill -f imagenet_distributed_train.py")
    
    r = collect()
    r_str = "%s %s %s %s %s %s" % (time.time(), batch_size, n_worker, n_ps, r[0], r[1])
    print r_str
    run("echo \"%s\" >> result.txt" % r_str)

@task
@parallel
def collect():
  s = []
  results_file = '/tmp/tf_run/worker0log_{}permachine_{}ps_{}machines'.format(worker_per_machine, num_ps,num_machines)
  path = get('/tmp/tf_run/worker0.log', results_file)

  with open(results_file) as f:
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

def run_dist(worker_per_machine, batch_size, num_ps, num_machines):
    try:
        dns_result = env.host_string.split('@')[1]
        host_string = dns_hostname[dns_result]
    except:
	exit()
    
    run("rm -rf /tmp/tf_run; mkdir /tmp/tf_run; rm -rf /tmp/imagenet_train/")
    run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches")
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    #Task range should be based on mygpuX, where X is an integer.
    #The tasks on a particular machine should be given by X * workers_per_machine to (X+1) * workers_per_machine

    all_worker = get_all_workers()
    all_ps = get_all_ps()

    my_ip = get_my_ip(host_string)
    print 'host string is {}'.format(host_string)
    import re
    gpu_num = int(re.findall(r'\d+',host_string)[0])
    task_id = gpu_num * worker_per_machine

    #Start all the parameter servers, it doesn't matter how many they are registering
    ps_str = ''
    for ps_index in range(num_ps):
        ps_ip = all_ps['ps' + str(ps_index)]
        ps_str += (ps_ip + ':2222,')
    ps_str = ps_str[:-1]

    #Assign
    wkr_str = ''
    for machine_index in range(num_machines):
        worker = all_worker['mygpu' + str(machine_index)]
        wkr_str += ','.join(worker+':'+str(x+2200) for x in range(worker_per_machine))
        wkr_str += ','
    wkr_str = wkr_str[:-1]

    for i in range(worker_per_machine):
        print "worker", i
        taskid = task_id + i

        #Assign 4 cores per process
        core_start = i * 4
        core_str = str(core_start) + "," #+ str(core_start + 16) 
        core_str += str(core_start + 1) + "," #+ str(core_start + 17)
        core_str += str(core_start + 2) + "," #+ str(core_start + 18) + ","
        core_str += str(core_start + 3) #+ "," + str(core_start + 19) 

        #command = "CUDA_VISIBLE_DEVICES=%s nohup /home/ec2-user/models/distr_vgg/bazel-bin/vgg/imagenet_distributed_train --batch_size=%s --data_dir=$HOME/imagenet-data --job_name='worker' --task_id=%s --ps_hosts=%s --worker_hosts=%s &> /tmp/tf_run/worker%s.log &" % (i, batch_size, taskid, ps_str, wkr_str, taskid)
                
        command = "CUDA_VISIBLE_DEVICES=%s taskset -c %s nohup /home/ec2-user/models/inception/bazel-bin/inception/imagenet_distributed_train --batch_size=%s --data_dir=$HOME/imagenet-data --job_name='worker' --task_id=%s --ps_hosts=%s --worker_hosts=%s &> /tmp/tf_run/worker%s.log &" % (i, core_str, batch_size, taskid, ps_str, wkr_str, taskid)

        import sys
        run(command, shell=True, shell_escape=True, stderr=sys.stdout, pty=False)
        run("echo 512 > hi.txt &")
        run("sleep 1")

@task
@parallel
def tester():
    print dns_hostname
    print ' this is the host string' + env.host_string
    print env.hosts

