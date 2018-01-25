"""
Fabric file to help with the launching of EC2 instances and running of Tensorflow experiments.

Look at the README for instructions.

"""
from fabric.api import *
from fabric.contrib import project
from time import sleep
import boto3
import os
import time

tgt_ami = 'ami-8ca83fec'
AWS_REGION = 'us-west-2'
AWS_AVAILABILITY_ZONE = 'us-west-2b'

# import ssh public key to AWS
my_aws_key = 'pranay'
worker_base_name = 'g{}u'.format(my_aws_key)
ps_base_name = '{}server'.format(my_aws_key)
NUM_WORKERS=4
NUM_PARAM_SERVERS=4
worker_names = [worker_base_name + str(i) for i in range(NUM_WORKERS)]
ps_names = [ps_base_name + str(i) for i in range(NUM_PARAM_SERVERS)]

MODEL_NAMES = ['vgg', 'alexnet', 'resnet', 'inception']

CONDA_DIR = '$HOME/anaconda'
WORKER_TYPE = 'g3.4xlarge'
PS_TYPE = 'i3.large'
PORT = '2222'

USER = os.environ['USER']

def tags_to_dict(d):
    return {a['Key'] : a['Value'] for a in d}

def get_target_instance():
    role_to_host = {}
    host_to_role = {}
    all_ids = []
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            if i.tags != None:
                d = tags_to_dict(i.tags)
                role = d['Name']
                if my_aws_key in role:
                    if role not in role_to_host:
                        role_to_host[role] = []
                    host = 'ec2-user@{}'.format(i.public_dns_name)
                    role_to_host[role].append(host)
                    host_to_role[host] = role
                    all_ids.append(i.instance_id)
    return role_to_host, host_to_role, all_ids

def get_machine_ips():
    ps_data, worker_data = {}, {}
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)
    for inst_id in ALL_IDS:
        i = ec2.Instance(inst_id)
        role = HOST_TO_ROLE['ec2-user@{}'.format(i.public_dns_name)]
        if worker_base_name in role:
            worker_data[role] = '{}:{}'.format(i.public_ip_address, PORT)
        else:
            ps_data[role] = '{}:{}'.format(i.public_ip_address, PORT)
    return ps_data, worker_data

env.disable_known_hosts = True
env.warn_only = True
ROLE_TO_HOST, HOST_TO_ROLE, ALL_IDS = get_target_instance()
PS_DATA, WORKER_DATA = get_machine_ips()
env.roledefs.update(ROLE_TO_HOST)
print('done getting data\n')

@task
@runs_once
def get_active_instances():
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)
    for inst_id in ALL_IDS:
        i = ec2.Instance(inst_id)
        print(HOST_TO_ROLE['ec2-user@{}'.format(i.public_dns_name)])
        print('{}:{}'.format(i.public_ip_address, PORT))
        print('ec2-user@{}'.format(i.public_dns_name))
    
######################## LAUNCH COMMANDS ################################

def setup_network():
    use_dry_run = False
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    
    # Create a VPC
    vpc = ec2_resource.create_vpc(DryRun=use_dry_run, CidrBlock='10.0.0.0/24')
    ec2_client.enable_vpc_classic_link(VpcId=vpc.vpc_id)
    ec2_client.modify_vpc_attribute(VpcId=vpc.vpc_id, EnableDnsSupport={'Value':True})
    ec2_client.modify_vpc_attribute(VpcId=vpc.vpc_id, EnableDnsHostnames={'Value':True})
    
    # Create an EC2 Security Group
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
    # Create the subnet for the VPC
    subnet = vpc.create_subnet(DryRun=use_dry_run, CidrBlock='10.0.0.0/25', AvailabilityZone=AWS_AVAILABILITY_ZONE)
    ec2_client.modify_subnet_attribute(SubnetId=subnet.subnet_id, MapPublicIpOnLaunch={'Value':True})
    # Create an Internet Gateway
    gateway = ec2_resource.create_internet_gateway(DryRun=use_dry_run)
    gateway.attach_to_vpc(DryRun=use_dry_run, VpcId=vpc.vpc_id)
    # Create a Route table and add the route
    route_table = ec2_client.create_route_table(DryRun=use_dry_run, VpcId=vpc.vpc_id)
    route_table_id = route_table['RouteTable']['RouteTableId']
    ec2_client.associate_route_table(SubnetId=subnet.subnet_id, RouteTableId=route_table_id)
    ec2_client.create_route(DryRun=use_dry_run, DestinationCidrBlock='0.0.0.0/0',RouteTableId=route_table_id,GatewayId=gateway.internet_gateway_id)
    return vpc, subnet, security_group

# Boot Spot Instance
def setup_spot_instance(server_name, server_instance_type, subnet, security_group, instance_count):
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

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
                    'VolumeType': 'standard'
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


# Boot Reserved Instance
def setup_reserved_instance(instance_name, server_instance_type, vpc, subnet, security_group, instance_count, volume_size, is_worker):
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    BlockDeviceMappings=[
        {
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'VolumeSize': 100,
                'DeleteOnTermination': True,
                'VolumeType': 'standard'
            },
        },
    ]
    
    # Create a cluster of reserved instances
    instances = ec2_resource.create_instances(ImageId=tgt_ami, MinCount=instance_count, MaxCount=instance_count,
                                              KeyName=my_aws_key, InstanceType=server_instance_type, SubnetId=subnet.subnet_id, SecurityGroupIds=[security_group['GroupId']],
                                     BlockDeviceMappings = BlockDeviceMappings,
                                     EbsOptimized=is_worker
    )

    instance = instances[0]
    instance_id = instance.instance_id
    instance.wait_until_running()
    instance.reload()
    instance.create_tags(
        Resources=[instance.instance_id],
        Tags=[
            {
                'Key': 'Name',
                'Value': instance_name
            },
        ]
    )

    return instance
    

def ensure_status_checks(ids):
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
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
    vpc, subnet, security_group = setup_network()

    all_instance_ids = []

    # Launch Parameter Servers
    for instance_num in range(NUM_PARAM_SERVERS):
        print('Launching Parameter Server {}...'.format(str(instance_num)))
        inst_name = '{}{}'.format(ps_base_name, instance_num)
        instance = setup_reserved_instance(inst_name, PS_TYPE, vpc, subnet, security_group, 1, 200, False)
        
        all_instance_ids.append(instance.instance_id)
        print 'Parameter Server {} setup at {}'.format(inst_name, instance.public_ip_address)
    
    # Launch Workers
    for instance_num in range(NUM_WORKERS):
        print('Launching Worker {}...'.format(str(instance_num)))
        inst_name = '{}{}'.format(worker_base_name, instance_num)
        instance = setup_reserved_instance(inst_name, WORKER_TYPE, vpc, subnet, security_group, 1, 200, True)

        all_instance_ids.append(instance.instance_id)
        print 'Worker {} setup at {}'.format(inst_name, instance.public_ip_address)

    ensure_status_checks(list(all_instance_ids))

################################################################
        
@task
@parallel
def ssh():
    local('ssh -A ' + env.host_string, capture=False)

@task
@parallel
def basic_setup():
    run('sudo yum update -q -y')
    run('sudo yum groupinstall \'Development Tools\' -q -y')
    run('sudo yum install -q -y emacs tmux gcc g++ dstat htop')
    run('sudo reboot')

@task
@parallel
def bazel_setup():
    run('conda update dask -y')
    run('wget https://github.com/bazelbuild/bazel/releases/download/0.7.0/bazel-0.7.0-installer-linux-x86_64.sh')
    run('chmod +x bazel-0.7.0-installer-linux-x86_64.sh')
    sudo('yum install -y java-1.8.0-openjdk-devel')
    run('JAVA_HOME=/usr/lib/jvm/java-openjdk/')
    run('export JAVA_HOME')
    run('PATH=$PATH:$JAVA_HOME/bin')
    run('export PATH')
    run('./bazel-0.7.0-installer-linux-x86_64.sh --user')

@task
@parallel
def inception_setup():
    run('git clone https://github.com/PranayJuneCS/models.git')
    with cd('~/models/research/inception'):
        run('bazel build inception/imagenet_train')
        run('bazel build inception/imagenet_distributed_train')


@task
@parallel
# To run, ssh into gpu's/ps's, cd into `vgg/distr_vgg` and run the commands saved from basic_setup
# (Make sure to replace starting segment with bazel-bin/vgg/imagenet_distributed_train)
def vgg_setup():
    run('git clone https://github.com/mchang6137/models.git vgg')
    with cd('~/vgg/'):
        run('git checkout -b vgg_impl origin/vgg_impl')
        with cd('distr_vgg/'):
            run('bazel build vgg/imagenet_distributed_train')

@task
@parallel
def vgg_fresh_setup():
    run('git clone https://github.com/mchang6137/models.git vgg')
    with cd('~/vgg/'):
        run('git checkout -b vgg_fresh origin/vgg_fresh')
        with cd('research/inception'):
            run('bazel build inception/imagenet_vgg_train')
            run('bazel build inception/imagenet_vgg_distributed_train')

@task
@parallel
# Go into `resnet/distr_vgg` and run the same commands as you would
# for vgg_setup. It's a little jank with the naming.
# Note: The loss bounces around a ton while you train, so it may seem
# like it's increasing at some points but over a large timeframe
# (on the order of hundreds of steps) it's decreasing.
def resnet_setup():
    run('git clone https://github.com/mchang6137/models.git resnet')
    with cd('~/resnet/'):
        run('git checkout -b resnet_impl origin/resnet_impl')
        with cd('distr_vgg/'):
            run('bazel build vgg/imagenet_distributed_train')

@task
@parallel
# To run, make sure to save the output from launching the instances.
# It'll be the same commands as running the inception model, but run them
# in `alexnet/inception/`
def alexnet_setup():
    run('git clone https://github.com/mchang6137/models.git alexnet')
    with cd('~/alexnet/'):
        run('git checkout -b alexnet_model origin/alexnet_model')
        with cd('inception/'):
            run('bazel build inception/imagenet_distributed_train')

@task
@parallel
def remove_tmp():
    run('rm -rf /tmp/imagenet_train')

@task
@parallel
def reboot():
    run('sudo reboot')

@task
def wait_until_running():
    #### TODO: GET WAIT TILL RUNNING TO WORK ####

    # ec2 = boto3.resource('ec2', region_name=AWS_REGION)
    # print('All instance IDs:')
    # print(ALL_IDS)
    # for instance_id in ALL_IDS:
    #     inst = ec2.Instance(instance_id)
    #     inst.wait_until_running()
    
    sleep(180)

    ensure_status_checks(ALL_IDS)

@task
@parallel
def s3_setup():
    # Install s3cmd
    sudo('yum --enablerepo=epel install -y s3cmd')

    # Configure s3cmd
    s3_config_file = 's3_config_file'

    put(s3_config_file, '~/')
    run('mkdir ~/imagenet-data')

    with cd('~/imagenet-data'):
        run('s3cmd --config=$HOME/s3_config_file --recursive get s3://tf-bucket-mikeypoo/ .')
        run('tar -xzvf validation_of.tar.gz')

    
@task
@parallel
def cuda_setup8():
    run('wget http://us.download.nvidia.com/XFree86/Linux-x86_64/375.66/NVIDIA-Linux-x86_64-375.66.run')
    run('wget https://developer.nvidia.com/compute/cuda/8.0/prod/local_installers/cuda_8.0.44_linux-run')
    run('mv NVIDIA-Linux-x86_64-375.66.run driver.run')
    run('mv cuda_8.0.44_linux-run cuda.run')
    run('chmod +x driver.run')
    run('chmod +x cuda.run')
    sudo('./driver.run --silent') # still requires a few prompts
    sudo('./cuda.run --silent --toolkit --samples')   # Don't install driver, just install CUDA and sample

    sudo('nvidia-smi -pm 1')
    sudo('nvidia-smi -acp 0')
    sudo('nvidia-smi --auto-boost-permission=0')
    sudo('nvidia-smi -ac 2505,875')
    
    # cudnn
    with cd('/usr/local'):

        sudo('wget http://developer.download.nvidia.com/compute/redist/cudnn/v6.0/cudnn-8.0-linux-x64-v6.0.tgz')
        sudo('tar xvf cudnn-8.0-linux-x64-v6.0.tgz')
        sudo('cp -P cuda/include/cudnn.h /usr/local/cuda-8.0/include')
        sudo('cp -P cuda/lib64/libcudnn* /usr/local/cuda-8.0/lib64/')
        sudo('chmod a+r /usr/local/cuda-8.0/lib64/libcudnn*')

        # set environment variables
        run('export PATH=/usr/local/cuda-8.0/bin${PATH:+:${PATH}}')
        run('export LD_LIBRARY_PATH=/usr/local/cuda-8.0/lib64\${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}')

    sudo('echo "/usr/local/cuda/lib64/" >> /etc/ld.so.conf')
    sudo('echo "/usr/local/cuda/extras/CPUTI/lib64/" >> /etc/ld.so.conf')
    sudo('ldconfig')

@task
@parallel
def anaconda_setup():
    run('wget https://repo.continuum.io/archive/Anaconda2-4.2.0-Linux-x86_64.sh')
    run('chmod +x Anaconda2-4.2.0-Linux-x86_64.sh')
    run('./Anaconda2-4.2.0-Linux-x86_64.sh -b -p {}'.format(CONDA_DIR))
    run('echo "export PATH={}/bin:$PATH" >> .bash_profile'.format(CONDA_DIR))
    run('conda upgrade -q -y --all')
    run('conda install -q -y pandas scikit-learn scikit-image matplotlib seaborn ipython')
    sudo('yum --enablerepo=epel install -y iperf iperf3')
    run('pip install ruffus glob2 awscli')
    run('source .bash_profile')

TF_GPU_URL = 'https://raw.githubusercontent.com/mchang6137/tensorflow/master/whl/gpu_whl/tensorflow-1.4.0-cp27-cp27mu-linux_x86_64.whl'
TF_CPU_URL = 'https://raw.githubusercontent.com/mchang6137/tensorflow/master/whl/cpu_whl/tensorflow-1.4.0-cp27-cp27mu-linux_x86_64.whl'
@task
@parallel
def tf_setup(gpu):
    if gpu:
        run('wget {}'.format(TF_GPU_URL))
    else:
        run('wget {}'.format(TF_CPU_URL))

    run('pip install tensorflow-1.4.0-cp27-cp27mu-linux_x86_64.whl')

######### AUTOMATE SETUP ##########

@task
@parallel
def cpu_setup(model_name):
    instance_setup(gpu=False, model=model_name)

@task
@parallel
def gpu_setup(model_name):
    instance_setup(gpu=True, model=model_name)

@task
@parallel
def instance_setup(gpu, model):
    if model not in MODEL_NAMES:
        print('Invalid model: ' + model)
        exit(1)
    print('Basic setup time.\n')
    basic_setup()
    wait_until_running()
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

@task
def obtain_imagenet_data():
    worker_string = ','.join(worker_names)
    local('fab -f fabfile_awsgpu_distributed.py -R {} s3_setup'.format(worker_string))


########## AUTOMATE EXPERIMENT ###############

def get_command(i, dir_string, ps_string, worker_string, is_worker):
    if is_worker:
        return 'bazel-bin{} --batch_size=32 --data_dir=$HOME/imagenet-data --job_name=\'worker\' --task_id={} --ps_hosts={} --worker_hosts={} |& tee wk{}.txt\n'.format(dir_string, i, ps_string, worker_string, i)
    else:
        return 'CUDA_VISIBLE_DEVICES=\'\' bazel-bin{} --batch_size=32 --job_name=\'ps\' --task_id={} --ps_hosts={} --worker_hosts={} |& tee ps{}.txt\n'.format(dir_string, i, ps_string, worker_string, i)

def get_strings(roles):
    ps_string, worker_string = '', ''
    for role in roles:
        is_worker = worker_base_name in role
        if is_worker:
            worker_string += '{},'.format(WORKER_DATA[role])
        else:
            ps_string += '{},'.format(PS_DATA[role])
    ps_string = ps_string[:-1]
    worker_string = worker_string[:-1]
    return ps_string, worker_string

def get_dirs(model):
    cd_string = '~/models/research/inception'
    if model == 'vgg':
        cd_string = '~/vgg/research/inception'
    if model == 'resnet':
        cd_string = '~/resnet/distr_vgg'
    if model == 'alexnet':
        cd_string = '~/alexnet/inception'

    dir_string = '/inception/imagenet_distributed_train'
    if model == 'vgg':
        dir_string = '/inception/imagenet_vgg_distributed_train'
    if model == 'resnet':
        dir_string = '/vgg/imagenet_distributed_train'

    return cd_string, dir_string

@task
@parallel
def run_experiment(model):
    remove_tmp()

    role = HOST_TO_ROLE[env.host_string]
    is_worker = worker_base_name in role
    if str.isdigit(role[-2]):
        index = int(role[-2:])
    else:
        index = int(role[-1])

    cd_string, dir_string = get_dirs(model)
    ps_string, worker_string = get_strings(env.effective_roles)

    command = get_command(index, dir_string, ps_string, worker_string, is_worker)

    with cd(cd_string):
        run(command)

@task
def start_experiment(model, num_ps=NUM_PARAM_SERVERS, num_workers=NUM_WORKERS):
    if not model or model not in MODEL_NAMES:
        print('Invalid model')
        exit(1)

    num_ps, num_workers = int(num_ps), int(num_workers)
    if num_ps > NUM_PARAM_SERVERS or num_ps <= 0:
        print('Invalid number of PS.')
        exit(1)

    if num_workers > NUM_WORKERS or num_workers <= 0:
        print('Invalid number of Workers.')
        exit(1)

    machines = [ps_base_name + str(i) for i in range(num_ps)]
    machines += [worker_base_name + str(i + 2) for i in range(num_workers)]
    machine_string = ','.join(machines)


    print('Running {} with {} PS, {} Workers. Let\'s goooooo.'.format(model.capitalize(), str(num_ps), str(num_workers)))
    sleep(1)

    local('fab -f fabfile_awsgpu_distributed.py -R {} run_experiment:{}'.format(machine_string, model))

@task
@parallel
def shutdown_bazel(model):
    if model not in MODEL_NAMES:
        print('Invalid model: ' + model)
        exit(1)
    cd_string, dir_string = get_dirs(model)
    with cd(cd_string):
        run('bazel shutdown')

@task
@parallel
def get_logs(model, dir_name):
    role = HOST_TO_ROLE[env.host_string]
    cd_string, dir_string = get_dirs(model)
    if str.isdigit(role[-2]):
        index = int(role[-2:])
    else:
        index = int(role[-1])
    machine_type = 'wk' if worker_base_name in role else 'ps'
    file_name = machine_type + str(index)

    get(remote_path='{}/{}.txt'.format(cd_string, file_name), local_path='./{}/{}.txt'.format(dir_name, file_name))

@task
def obtain_logs(model, dir_name, num_ps=NUM_PARAM_SERVERS, num_workers=NUM_WORKERS):
    if not model or model not in MODEL_NAMES:
        print('Invalid model')
        exit(1)

    num_ps, num_workers = int(num_ps), int(num_workers)
    if num_ps > NUM_PARAM_SERVERS or num_ps <= 0:
        print('Invalid number of PS.')
        exit(1)

    if num_workers > NUM_WORKERS or num_workers <= 0:
        print('Invalid number of Workers.')
        exit(1)

    local('mkdir {}'.format(dir_name))

    machines = [ps_base_name + str(i) for i in range(num_ps)]
    machines += [worker_base_name + str(i) for i in range(num_workers)]
    machine_string = ','.join(machines)

    local('fab -f fabfile_awsgpu_distributed.py -R {} get_logs:{},{}'.format(machine_string, model, dir_name))


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

    # Delete security groups
    for security_group in ec2_resource.security_groups.all():
        print 'Security Group {}'.format(security_group.group_id)
        if security_group.vpc_id in all_default_vpc:
            continue
        try:
            ec2_client.delete_security_group(GroupId=security_group.group_id)
            print '{} deleted'.format(security_group.group_id)
        except:
            print '{} not deleted'.format(security_group.group_id)
    # Delete Subnets
    for subnet in ec2_resource.subnets.all():
        if subnet.vpc_id in all_default_vpc:
            continue
        print 'Subnet ID {}'.format(subnet.id)
        try:
            ec2_client.delete_subnet(SubnetId=subnet.id)
            print '{} deleted'.format(subnet.id)
        except:
            print '{} not deleted'.format(subnet.id)

    # Detach Gateways
    for vpc in ec2_resource.vpcs.all():
        if vpc in all_default_vpc:
            continue
        for gateway in ec2_resource.internet_gateways.all():
            try:
                ec2_client.detach_internet_gateway(InternetGatewayId=gateway.id, VpcId=vpc.id)
                print '{} detached'.format(gateway.id)
            except:
                print '{} not detached'.format(gateway.id)

    # Delete Gateways
    for gateway in ec2_resource.internet_gateways.all():
        try:
            ec2_client.delete_internet_gateway(InternetGatewayId=gateway.id)
            print '{} deleted'.format(gateway.id)
        except:
            print '{} not deleted'.format(gateway.id)

    # Release IP Address
    for address in ec2_client.describe_addresses()['Addresses']:
        allocation_id = address['AllocationId']
        try:
            ec2_client.release_address(AllocationId=allocation_id)
            print '{} deleted'.format(allocation_id)
        except:
            print '{} not deleted'.format(allocation_id)

    # Delete Router Table
    for route_table in ec2_resource.route_tables.all():
        if route_table.vpc_id in all_default_vpc:
            continue
        try:
            ec2_client.delete_route_table(RouteTableId=route_table.id)
            print '{} deleted'.format(route_table.id)
        except:
            print '{} not deleted'.format(route_table.id)
            
    # Finally, Delete VPC
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
def terminate():
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    for inst_id in ALL_IDS:
        i = ec2.Instance(inst_id)
        print('Shutting down {}'.format(HOST_TO_ROLE['ec2-user@{}'.format(i.public_dns_name)]))
        i.terminate()

    print('Sleeping for 2 minutes to let machines shut down. VPC Cleanup afterwards.')
    sleep(120)
    print('Running VPC Cleanup.')
    vpc_cleanup()
