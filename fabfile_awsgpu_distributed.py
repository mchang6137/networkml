"""
fabric file to help with launching EC2 P2 instancesand
getting GPU support set up. Also installs latest
anaconda and then tensorflow. Use:

fab -f fabfile_awsgpu_distributed.py launch

After launch completes, the commands necessary to run the inception model will be printed out.
Store them somewhere, as you'll need them to run the experiments.

# wait until you can ssh into the instance with
fab -f fabfile_awsgpu_distributed.py ssh -R mygpu0

# install everything except S3
#For example, if you set NUM_GPUS=4 and NUM_PARAM_SERVERS=2, you would run the setups in the following way
fab -f fabfile_awsgpu_distributed.py -R mygpu0,mygpu1,mygpu2,mygpu3,ps0,ps1 <setup_name>

# Run the setups on both the parameter servers and the gpus in this order:

basic_setup
cuda_setup8
anaconda_setup
tf_setup
inception_setup

#To download from s3, create a file in the same directory as this script, titled s3_config_file
The file should look like 
access_key = YOUR ACCESS KEY
secret_key = YOUR SECRET KEY
bucket_location = YOUR BUCKET ZONE

# Then, to obtain the data from the s3 bucket, run s3_setup on ONLY gpus, like this:
# fab -f fabfile_awsgpu_distributed.py -R mygpu0,mygpu1,mygpu2,mygpu3 s3_setup

# when you're done, terminate. This will terminate all machines!
fab -f fabfile_awsgpu_distributed.py terminate
fab -f fabfile_awsgpu_distributed.py vpc_cleanup

Took inspiration from:
https://aws.amazon.com/blogs/aws/new-p2-instance-type-for-amazon-ec2-up-to-16-gpus/

"""
from fabric.api import *
from fabric.contrib import project
from time import sleep
import boto3
import os
import time

#tgt_ami = 'ami-b04e92d0'
tgt_ami = 'ami-8ca83fec'
# tgt_ami = 'ami-bec91fc6'
# tgt_ami = 'ami-bec91fc6'
# tgt_ami = 'ami-0d7da775' # -- OUR AMI
AWS_REGION = 'us-west-2'
AWS_AVAILABILITY_ZONE = 'us-west-2b'

#import ssh public key to AWS
my_aws_key = 'pranay'
worker_base_name = "gpranayu"
ps_base_name = "pranayserver"
NUM_GPUS=4
NUM_PARAM_SERVERS=4
worker_names = [worker_base_name + str(x) for x in range(NUM_GPUS)]
ps_names = [ps_base_name + str(x) for x in range(NUM_PARAM_SERVERS)]

CONDA_DIR = "$HOME/anaconda"
WORKER_TYPE = 'g3.4xlarge'
PS_TYPE = 'i3.large'

USER = os.environ['USER']

def tags_to_dict(d):
    return {a['Key'] : a['Value'] for a in d}

def get_target_instance():
    role_to_host = {}
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    host_list = []
    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            if i.tags != None:
                d = tags_to_dict(i.tags)
                role = d['Name']
                if role not in role_to_host:
                    role_to_host[role] = []
                role_to_host[role].append('ec2-user@{}'.format(i.public_dns_name))
                host_list.append('ec2-user@{}'.format(i.public_dns_name))
    print role_to_host
    print("\n")
    return role_to_host

env.disable_known_hosts = True
env.warn_only = True
env.roledefs.update(get_target_instance())


@task
@runs_once
def get_active_instances():
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            if i.tags != None:
                d = tags_to_dict(i.tags)
                print d['Name']
                print('{}:2222,'.format(i.public_ip_address)[:-1])
                print('ec2-user@{}'.format(i.public_dns_name))


######################## LAUNCH COMMANDS ################################

def setup_network():
    use_dry_run = False
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    
    #Create a VPC
    vpc = ec2_resource.create_vpc(DryRun=use_dry_run, CidrBlock='10.0.0.0/24')
    ec2_client.enable_vpc_classic_link(VpcId=vpc.vpc_id)
    ec2_client.modify_vpc_attribute(VpcId=vpc.vpc_id, EnableDnsSupport={'Value':True})
    ec2_client.modify_vpc_attribute(VpcId=vpc.vpc_id, EnableDnsHostnames={'Value':True})
    
    #Create an EC2 Security Group
    ip_permissions = [
        {
            'IpProtocol': '-1',
            'FromPort': -1,
            'ToPort': -1,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }]
    security_group = ec2_client.create_security_group(GroupName='gpu_group', Description='Allow_all_ingress_egress', VpcId=vpc.vpc_id)
    group_id = security_group['GroupId']
    ec2_client.authorize_security_group_ingress(GroupId=group_id, IpPermissions=ip_permissions) 
    #Create the subnet for the VPC
    subnet = vpc.create_subnet(DryRun=use_dry_run, CidrBlock='10.0.0.0/25', AvailabilityZone=AWS_AVAILABILITY_ZONE)
    ec2_client.modify_subnet_attribute(SubnetId=subnet.subnet_id, MapPublicIpOnLaunch={'Value':True})
    #Create an Internet Gateway
    gateway = ec2_resource.create_internet_gateway(DryRun=use_dry_run)
    gateway.attach_to_vpc(DryRun=use_dry_run, VpcId=vpc.vpc_id)
    #Create a Route table and add the route
    route_table = ec2_client.create_route_table(DryRun=use_dry_run, VpcId=vpc.vpc_id)
    route_table_id = route_table['RouteTable']['RouteTableId']
    ec2_client.associate_route_table(SubnetId=subnet.subnet_id, RouteTableId=route_table_id)
    ec2_client.create_route(DryRun=use_dry_run, DestinationCidrBlock='0.0.0.0/0',RouteTableId=route_table_id,GatewayId=gateway.internet_gateway_id)
    return vpc, subnet, security_group

#Boot Spot Instance 
def setup_spot_instance(ec2_client, ec2_resource, server_name, server_instance_type, subnet, security_group, instance_count):
    use_dry_run = False
    param_server_name = server_name
    param_server_type = server_instance_type
    param_spot_bid = '3'
    launch_specification = {
        'ImageId': tgt_ami,
        'KeyName': my_aws_key,
        'InstanceType': param_server_type,
        'BlockDeviceMappings':[
            {
                'DeviceName': '/dev/xvda',
                'Ebs': {
                    'VolumeSize': 50,
                    'DeleteOnTermination': True,
                    'VolumeType': 'standard',
                    #'SnapshotId' : 'snap-c87f35ec'
                },
            },
        ],
        'SecurityGroupIds': [security_group['GroupId']],
        'SubnetId': subnet.subnet_id,
        'EbsOptimized': False,
        'Placement': {
            'AvailabilityZone': AWS_AVAILABILITY_ZONE,
        },
    }

    param_instances = ec2_client.request_spot_instances(DryRun=use_dry_run,SpotPrice=param_spot_bid, InstanceCount=instance_count,
                                                 LaunchSpecification=launch_specification)

    spot_request_id = param_instances['SpotInstanceRequests'][0]['SpotInstanceRequestId']

    all_instances = []
    while all_instances == [] or all_instances['State'] == 'open':
        all_instances = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=[spot_request_id])
        all_instances = all_instances['SpotInstanceRequests'][0]
        
    return all_instances

#Boot Reserved Instance
def setup_reserved_instance(ec2_client, ec2_resource, instance_name, server_instance_type, vpc, subnet, security_group, instance_count, volume_size):
    use_dry_run = False

    BlockDeviceMappings=[
        {
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'VolumeSize': 100,
                'DeleteOnTermination': True,
                'VolumeType': 'standard',
                #'SnapshotId' : 'snap-c87f35ec'
            },
        },
    ]
    
    #Create a cluster of p2.xlarge instances
    instances = ec2_resource.create_instances(ImageId=tgt_ami, MinCount=instance_count, MaxCount=instance_count,
                                              KeyName=my_aws_key, InstanceType=server_instance_type, SubnetId=subnet.subnet_id, SecurityGroupIds=[security_group['GroupId']],
                                     BlockDeviceMappings = BlockDeviceMappings,
                                     EbsOptimized=True
    )

    instance = instances[0]
    instance_id = instance.instance_id
    instance.wait_until_running()
    instance.reload()
    instance.create_tags(
        Resources=[
            instance.instance_id
    ],
        Tags=[
            {
                'Key': 'Name',
                'Value': instance_name
            },
        ]
    )

    return instance
    

def ensure_status_checks(ec2_client, ids):
    print('Checking System Status of ' + str(len(ids)) + ' instances.')
    current_ids = ids

    while len(current_ids) > 0:
        time.sleep(5)
        print('Polling to check all instance statuses...')
        statuses = ec2_client.describe_instance_status(
            Filters=[
                {
                    'Name': 'system-status.status',
                    'Values': ['ok', 'initializing']
                }
            ],
            InstanceIds=current_ids
        )

        for status in statuses['InstanceStatuses']:
            inst_id = status['InstanceId']
            system_check = status['SystemStatus']['Status'] == 'ok'
            instance_check = status['InstanceStatus']['Status'] == 'ok'
            if system_check and instance_check:
                current_ids.remove(inst_id)

        if len(current_ids) > 0:
            print(str(len(current_ids)) + ' instances still initializing.')

    print('All instances are initialized. Let\'s go baby.')

@task
def launch():
    #For Debugging
    use_dry_run = False
    
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    vpc, subnet, security_group = setup_network()

    ps_instances = []
    worker_instances = []
    all_instance_ids = []
    
    #Launch Parameter Servers
    for param_servers in range(NUM_PARAM_SERVERS):

        try:
            inst_name = '{}{}'.format(ps_base_name, param_servers)
            instance_obj = setup_spot_instance(ec2_client, ec2_resource, inst_name, PS_TYPE, subnet, security_group, 1)
            
            instance_id = instance_obj['InstanceId']
            all_instance_ids.append(instance_id)
            
            spot_instance = ec2_resource.Instance(instance_id)
            spot_instance.wait_until_running()
            spot_instance.reload()
            spot_instance.create_tags(
                Resources=[
                    instance_id
            ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': inst_name
                    },
                ]
            )
            print 'Parameter server setup at {}'.format(spot_instance.public_ip_address)
            ps_instances.append(spot_instance)
        except Exception as e:
            print e
            print 'Error setting up Parameter Server spot instance. Terminating'
            return

    
    #Launch GPUs
    for instance_num in range(NUM_GPUS):
        inst_name = '{}{}'.format(worker_base_name, instance_num)
        instance = setup_reserved_instance(ec2_client, ec2_resource, inst_name, WORKER_TYPE, vpc, subnet, security_group, 1, 200)
        
        all_instance_ids.append(instance.instance_id)
        print 'GPU setup at {}'.format(instance.public_ip_address)
        worker_instances.append(instance)

    ensure_status_checks(ec2_client, list(all_instance_ids))

    worker_string = ''
    for worker in worker_instances:
        worker_string += '{}:2222,'.format(worker.public_ip_address)
    worker_string = worker_string[:-1]

    ps_string = ''
    for param_server in ps_instances:
        ps_string += '{}:2222,'.format(param_server.public_ip_address)
    ps_string = ps_string[:-1]
            
    with open('commands.txt', 'w') as f:
        for i, worker in enumerate(worker_instances):
            f.write('bazel-bin/inception/imagenet_distributed_train --batch_size=32 --data_dir=$HOME/imagenet-data --job_name=\'worker\' --task_id={} --ps_hosts={} --worker_hosts={} |& tee wk{}.txt\n'.format(i, ps_string, worker_string, i))
        f.write('\n')
        for i, param_server in enumerate(ps_instances):
            f.write('CUDA_VISIBLE_DEVICES=\'\' bazel-bin/inception/imagenet_distributed_train --batch_size=32 --job_name=\'ps\' --task_id={} --ps_hosts={} --worker_hosts={} |& tee ps{}.txt\n'.format(i, ps_string, worker_string, i))
        

    with open('all_instance_ids.txt', 'w') as f:
        for instance_id in all_instance_ids:
            f.write(instance_id)
            f.write('\n')

################################################################

@task
@parallel
def ssh():
    local("ssh -A " + env.host_string, capture=False)

@task
@parallel
def add_to_known_hosts(): # Lets you ssh without having to type in "yes" the first time
    local("ssh -A -oStrictHostKeyChecking=no " + env.host_string, capture=False)
    run("exit")

@task
@parallel
def basic_setup():
    print env.host_string
    run("sudo yum update -q -y")
    run("sudo yum groupinstall 'Development Tools' -q -y")
    run("sudo yum install -q -y emacs tmux gcc g++ dstat htop")
    run("sudo reboot")

@task
@parallel
def bazel_setup():
    run("wget https://github.com/bazelbuild/bazel/releases/download/0.7.0/bazel-0.7.0-installer-linux-x86_64.sh")
    run("chmod +x bazel-0.7.0-installer-linux-x86_64.sh")
    sudo("yum install -y java-1.8.0-openjdk-devel")
    run("JAVA_HOME=/usr/lib/jvm/java-openjdk/")
    run("export JAVA_HOME")
    run("PATH=$PATH:$JAVA_HOME/bin")
    run("export PATH")
    run("./bazel-0.7.0-installer-linux-x86_64.sh --user")

@task
@parallel
def inception_setup():
    run("git clone https://github.com/PranayJuneCS/models.git")
    with cd("~/models/research/inception"):
        run("bazel build inception/imagenet_train")
        run("bazel build inception/imagenet_distributed_train")


@task
@parallel
# To run, ssh into gpu's/ps's, cd into `vgg/distr_vgg` and run the commands saved from basic_setup
# (Make sure to replace starting segment with bazel-bin/vgg/imagenet_distributed_train)
def vgg_setup():
    run("git clone https://github.com/mchang6137/models.git vgg")
    with cd("~/vgg/"):
        run("git checkout -b vgg_impl origin/vgg_impl")
        with cd("distr_vgg/"):
            run("bazel build vgg/imagenet_distributed_train")

@task
@parallel
def vgg_fresh_setup():
    run("git clone https://github.com/mchang6137/models.git vgg")
    with cd("~/vgg/"):
        run("git checkout -b vgg_fresh origin/vgg_fresh")
        with cd("research/inception"):
            run("bazel build inception/imagenet_vgg_distributed_train")

@task
@parallel
# Go into `resnet/distr_vgg` and run the same commands as you would
# for vgg_setup. It's a little jank with the naming.
# Note: The loss bounces around a ton while you train, so it may seem
# like it's increasing at some points but over a large timeframe
# (on the order of hundreds of steps) it's decreasing.
def resnet_setup():
    run("git clone https://github.com/mchang6137/models.git resnet")
    with cd("~/resnet/"):
        run("git checkout -b resnet_impl origin/resnet_impl")
        with cd("distr_vgg/"):
            run("bazel build vgg/imagenet_distributed_train")

@task
@parallel
# To run, make sure to save the output from launching the instances.
# It'll be the same commands as running the inception model, but run them
# in `alexnet/inception/`
def alexnet_setup():
    run("git clone https://github.com/mchang6137/models.git alexnet")
    with cd("~/alexnet/"):
        run("git checkout -b alexnet_model origin/alexnet_model")
        with cd("inception/"):
            run("bazel build inception/imagenet_distributed_train")

@task
@parallel
def remove_tmp():
    run("rm -rf /tmp/imagenet_train")

@task
@parallel
def reboot():
    run("sudo reboot")

def unpack_instance_ids():
    return open("all_instance_ids.txt").read().splitlines()

@task
def wait_until_running():
    #### TODO: GET WAIT TILL RUNNING TO WORK ####

    # ec2 = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    all_instance_ids = unpack_instance_ids()
    # print('All instance IDs:')
    # print(all_instance_ids)
    # for instance_id in all_instance_ids:
    #     inst = ec2.Instance(instance_id)
    #     inst.wait_until_running()
    
    sleep(180)

    # ensure_status_checks(ec2_client, all_instance_ids)

@task
@parallel
def s3_setup():
    #Install s3cmd
    sudo("yum --enablerepo=epel install -y s3cmd")

    #Configure s3cmd
    s3_config_file = 's3_config_file'

    put(s3_config_file, '~/')
    run('mkdir ~/imagenet-data')

    with cd("~/imagenet-data"):
        run('s3cmd --config=$HOME/s3_config_file --recursive get s3://tf-bucket-mikeypoo/ .')
        run('tar -xzvf validation_of.tar.gz')

    
@task
@parallel
def cuda_setup8():
    run("wget http://us.download.nvidia.com/XFree86/Linux-x86_64/375.51/NVIDIA-Linux-x86_64-375.51.run")
    run("wget https://developer.nvidia.com/compute/cuda/8.0/prod/local_installers/cuda_8.0.44_linux-run")
    run("mv NVIDIA-Linux-x86_64-375.51.run driver.run")
    run("mv cuda_8.0.44_linux-run cuda.run")
    run("chmod +x driver.run")
    run("chmod +x cuda.run")
    sudo("./driver.run --silent") # still requires a few prompts
    sudo("./cuda.run --silent --toolkit --samples")   # Don't install driver, just install CUDA and sample
    #
    sudo("nvidia-smi -pm 1")
    sudo("nvidia-smi -acp 0")
    sudo("nvidia-smi --auto-boost-permission=0")
    sudo("nvidia-smi -ac 2505,875")

    # cudnn
    with cd("/usr/local"):
        # sudo("wget http://people.eecs.berkeley.edu/~jonas/cudnn-8.0-linux-x64-v5.1.tgz")
        # sudo("tar xvf cudnn-8.0-linux-x64-v5.1.tgz")

        # CUDNN_TAR_FILE="cudnn-8.0-linux-x64-v6.0.tgz"
        sudo("wget http://developer.download.nvidia.com/compute/redist/cudnn/v6.0/cudnn-8.0-linux-x64-v6.0.tgz")
        sudo("tar xvf cudnn-8.0-linux-x64-v6.0.tgz")
        sudo("cp -P cuda/include/cudnn.h /usr/local/cuda-8.0/include")
        sudo("cp -P cuda/lib64/libcudnn* /usr/local/cuda-8.0/lib64/")
        sudo("chmod a+r /usr/local/cuda-8.0/lib64/libcudnn*")

        # set environment variables
        run("export PATH=/usr/local/cuda-8.0/bin${PATH:+:${PATH}}")
        run("export LD_LIBRARY_PATH=/usr/local/cuda-8.0/lib64\${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}")

    sudo('echo "/usr/local/cuda/lib64/" >> /etc/ld.so.conf')
    sudo('echo "/usr/local/cuda/extras/CPUTI/lib64/" >> /etc/ld.so.conf')
    sudo('ldconfig')

@task
@parallel
def anaconda_setup():
    run("wget https://repo.continuum.io/archive/Anaconda2-4.2.0-Linux-x86_64.sh")
    run("chmod +x Anaconda2-4.2.0-Linux-x86_64.sh")
    run("./Anaconda2-4.2.0-Linux-x86_64.sh -b -p {}".format(CONDA_DIR))
    run('echo "export PATH={}/bin:$PATH" >> .bash_profile'.format(CONDA_DIR))
    run("conda upgrade -q -y --all")
    run("conda install -q -y pandas scikit-learn scikit-image matplotlib seaborn ipython")
    run("pip install ruffus glob2 awscli")
    run("source .bash_profile")

TF_GPU_URL = "https://raw.githubusercontent.com/mchang6137/tensorflow/master/whl/gpu_whl/tensorflow-1.4.0-cp27-cp27mu-linux_x86_64.whl"
TF_CPU_URL = "https://raw.githubusercontent.com/mchang6137/tensorflow/master/whl/cpu_whl/tensorflow-1.4.0-cp27-cp27mu-linux_x86_64.whl"
@task
@parallel
def tf_setup(gpu):
    if gpu:
        run("wget {}".format(TF_GPU_URL))
    else:
        run("wget {}".format(TF_CPU_URL))

    run("pip install tensorflow-1.4.0-cp27-cp27mu-linux_x86_64.whl")

@task
@parallel
def cpu_setup(model_name):
    instance_setup(gpu=False, model=model_name)

@task
@parallel
def gpu_setup(model_name):
    instance_setup(gpu=True, model=model_name)

MODEL_NAMES = ['vgg', 'alexnet', 'resnet', 'inception']

@task
@parallel
def instance_setup(gpu, model):
    if model not in MODEL_NAMES:
        print('Invalid model: ' + model)
        exit(1)
    print('Basic setup time.\n')
    basic_setup()
    wait_until_running()
    # add_to_known_hosts()
    if gpu:
        cuda_setup8()
    print('Anaconda time.\n')
    anaconda_setup()
    print('TF time.\n')
    tf_setup(gpu)
    print('Bazel time.\n')
    bazel_setup()
    remove_tmp()
    print(model + ' setup time.\n')
    if model == 'vgg':
        vgg_fresh_setup()
    elif model == 'alexnet':
        alexnet_setup()
    elif model == 'inception':
        inception_setup()
    elif model == 'resnet':
        resnet_setup()


############################################################################

@task
@runs_once
def vpc_cleanup():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    all_default_vpc = []
    vpc_response = ec2_client.describe_account_attributes(AttributeNames=['default-vpc'])
    
    for account_information in vpc_response['AccountAttributes']:
        if account_information['AttributeName'] == 'default-vpc':
            for attribute_value in account_information['AttributeValues']:
                all_default_vpc.append(attribute_value['AttributeValue'])

    print 'Default VPCs are {}'.format(all_default_vpc)
    if len(all_default_vpc) == 0:
        print 'There are no default VPCs detected! Exiting to prevent fucking irreparable damage'
        exit()

    #Delete security groups
    for security_group in ec2_resource.security_groups.all():
        print 'Security Group {}'.format(security_group.group_id)
        if security_group.vpc_id in all_default_vpc:
            continue
        try:
            ec2_client.delete_security_group(GroupId=security_group.group_id)
            print '{} deleted'.format(security_group.group_id)
        except:
            print '{} not deleted'.format(security_group.group_id)
    #Delete Subnets
    for subnet in ec2_resource.subnets.all():
        if subnet.vpc_id in all_default_vpc:
            continue
        print 'Subnet ID {}'.format(subnet.id)
        try:
            ec2_client.delete_subnet(SubnetId=subnet.id)
            print '{} deleted'.format(subnet.id)
        except:
            print '{} not deleted'.format(subnet.id)

    #Detach Gateways
    for vpc in ec2_resource.vpcs.all():
        if vpc in all_default_vpc:
            continue
        for gateway in ec2_resource.internet_gateways.all():
            try:
                ec2_client.detach_internet_gateway(InternetGatewayId=gateway.id, VpcId=vpc.id)
                print '{} detached'.format(gateway.id)
            except:
                print '{} not detached'.format(gateway.id)

    #Delete Gateways
    for gateway in ec2_resource.internet_gateways.all():
        try:
            ec2_client.delete_internet_gateway(InternetGatewayId=gateway.id)
            print '{} deleted'.format(gateway.id)
        except:
            print '{} not deleted'.format(gateway.id)

    #Release IP Address
    for address in ec2_client.describe_addresses()['Addresses']:
        allocation_id = address['AllocationId']
        try:
            ec2_client.release_address(AllocationId=allocation_id)
            print '{} deleted'.format(allocation_id)
        except:
            print '{} not deleted'.format(allocation_id)

    #Delete Router Table
    for route_table in ec2_resource.route_tables.all():
        if route_table.vpc_id in all_default_vpc:
            continue
        try:
            ec2_client.delete_route_table(RouteTableId=route_table.id)
            print '{} deleted'.format(route_table.id)
        except:
            print '{} not deleted'.format(route_table.id)
            
    #Finally, Delete VPC
    for vpc in ec2_resource.vpcs.all():
        if vpc.id in all_default_vpc:
            continue
        try:
            ec2_client.delete_vpc(VpcId=vpc.id)
            print '{} deleted'.format(vpc.id)
        except:
            print '{} not deleted'.format(vpc.id)

@task
@runs_once
def terminate(everything=False):
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            if everything:
                print(i)
                i.terminate()
            elif i.tags != None:
                d = tags_to_dict(i.tags)
                if my_aws_key in d['Name']:
                    i.terminate()
