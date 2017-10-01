"""
fabric file to help with launching EC2 P2 instancesand
getting GPU support set up. Also installs latest
anaconda and then tensorflow. Use:

fab -f fabfile_awsgpu_distributed.py launch

# wait until you can ssh into the instance with
fab -f fabfile_awsgpu_distributed.py -H mygpu ssh

# install everything except S3
#For example, if you set NUM_GPUS=4 and NUM_PARAM_SERVERS=2, you would start in the following way
fab -f fabfile_awsgpu_distributed.py -H mygpu0,mygpu1,mygpu2,mygpu3,ps0,ps1 basic_setup cuda_setup8 anaconda_setup tf_setup inception_setup
#Ignore the Name lookup error!

#To download from s3, create a file in the same directory as this script, titled s3_config_file
The file should look like 
access_key = YOUR ACCESS KEY
secret_key = YOUR SECRET KEY
bucket_location = YOUR BUCKET ZONE

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

#tgt_ami = 'ami-b04e92d0'
tgt_ami = 'ami-8ca83fec'
AWS_REGION = 'us-west-2'
AWS_AVAILABILITY_ZONE = 'us-west-2b'

#import ssh public key to AWS
my_aws_key = 'michael'
worker_base_name = "mygpu"
ps_base_name = "ps"
NUM_GPUS=1
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
print env.roles
print env.hosts


@task
def get_active_instances():
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            d = tags_to_dict(i.tags)
            print d['Name']

@task
def vpc_cleanup():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    all_default_vpc = []
    vpc_response = ec2_client.describe_account_attributes(AttributeNames=['default-vpc'])
    
    for account_information in vpc_response['AccountAttributes']:
        if account_information['AttributeName'] == 'default_vpc':
            for attribute_value in account_information['AttributeValues']:
                all_default_vpc.append(attribute_value['AttributeValue']):

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
#    ec2_client.authorize_security_group_egress(GroupId=group_id, IpPermissions=ip_permissions)
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
def setup_spot_instance(ec2_client, ec2_resource, server_name, server_instance_type, subnet, instance_count):
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
        'SubnetId': subnet.subnet_id,
        'EbsOptimized': True,
        'Placement': {
            'AvailabilityZone': AWS_AVAILABILITY_ZONE,
        },
    }

    param_instances = ec2_client.request_spot_instances(DryRun=use_dry_run,SpotPrice=param_spot_bid, InstanceCount=instance_count,
                                                 LaunchSpecification=launch_specification)
    spot_request_id = param_instances['SpotInstanceRequests']

    all_instances = []
    while all_instances == []:
        all_instances = ec2_client.describe_spot_instance_requests()['SpotInstanceRequests']
        print all_instances
        print 'checked describe spot instances'
        sleep(10)
        
    return param_instances

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

    for inst in instances:
        inst.wait_until_running()
        inst.reload()
        inst.create_tags(
            Resources=[
                inst.instance_id
	    ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': instance_name
                },
            ]
        )
    return instances

@task
def launch():
    #For Debugging
    use_dry_run = False
    
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    vpc, subnet, security_group = setup_network()

    all_param_server_ips = []
    all_worker_ips = []
    
    #Launch Parameter servers
    for param_servers in range(NUM_PARAM_SERVERS):
        inst_name = '{}{}'.format(ps_base_name, param_servers)
        instances = setup_reserved_instance(ec2_client, ec2_resource, inst_name, PS_TYPE, vpc, subnet, security_group, 1, 200)
        for instance in instances:
            print 'Parameter server setup at {}'.format(instance.public_ip_address)
            all_param_server_ips.append(instance)
    
    #Launch GPUs
    for instance_num in range(NUM_GPUS):
        inst_name = '{}{}'.format(worker_base_name, instance_num)
        instances = setup_reserved_instance(ec2_client, ec2_resource, inst_name, WORKER_TYPE, vpc, subnet, security_group, 1, 200)
        for instance in instances:
            print 'GPU setup at {}'.format(instance.public_ip_address)
            all_worker_ips.append(instance)

    worker_string = ''
    for worker in all_worker_ips:
        worker_string += '{}:2222,'.format(worker.public_ip_address)
    worker_string = worker_string[:-1]

    ps_string = ''
    for param_server in all_param_server_ips:
        ps_string += '{}:2222,'.format(param_server.public_ip_address)
    ps_string = ps_string[:-1]
            
    #Print Command to Run Tensorflow 
    worker_count = 0
    for worker in all_worker_ips:
        print 'bazel-bin/inception/imagenet_distributed_train --batch_size=32 --data_dir=$HOME/imagenet-data --job_name=\'worker\' --task_id={} --ps_hosts={} --worker_hosts={}'.format(worker_count, ps_string, worker_string)
        worker_count += 1

    param_count = 0
    for param_server in all_param_server_ips:
        print 'CUDA_VISIBLE_DEVICES=\'\' bazel-bin/inception/imagenet_distributed_train --batch_size=32 --job_name=\'ps\' --task_id={} --ps_hosts={} --worker_hosts={}'.format(param_count, ps_string, worker_string)
        param_count += 1

#Automates the running of the experiment
@task
@parallel
def run_worker_experiment():
    with cd("~/models/inception/"):
        print 'hi'

@task
@parallel
def run_ps_experiment():
    with cd("~/models/inception/"):
	print 'hi'


@task
@parallel
def stop_inception_experiment():
    print 'hi'
        
@task
@parallel
def ssh():
    print env.host_string
    local("ssh -A " + env.host_string)
    print env.host_string

@task
def tensorboard():
    local("open http://"+env.host_string+":6006")

@task
def copy_model():
    local("scp " + env.host_string+":/tmp/model.ckpt /tmp/")

@task
@parallel
def basic_setup():
    print env.host_string
    print env.hosts
    run("sudo yum update -q -y")
    run("sudo yum groupinstall 'Development Tools' -q -y")
    run("sudo yum install -q -y emacs tmux  gcc g++ dstat htop")
    run("sudo yum install -y kernel-devel-`uname -r`")

@task
@parallel
def cuda_setup():
    run("wget http://us.download.nvidia.com/XFree86/Linux-x86_64/352.99/NVIDIA-Linux-x86_64-352.99.run")
    run("wget http://developer.download.nvidia.com/compute/cuda/7.5/Prod/local_installers/cuda_7.5.18_linux.run")
    run("chmod +x NVIDIA-Linux-x86_64-352.99.run")
    run("chmod +x cuda_7.5.18_linux.run")
    sudo("./NVIDIA-Linux-x86_64-352.99.run --silent") # still requires a few prompts
    sudo("./cuda_7.5.18_linux.run --silent --toolkit --samples")   # Don't install driver, just install CUDA and sample
    #
    sudo("nvidia-smi -pm 1")
    sudo("nvidia-smi -acp 0")
    sudo("nvidia-smi --auto-boost-permission=0")
    sudo("nvidia-smi -ac 2505,875")

    # cudnn
    with cd("/usr/local"):
        sudo("wget http://people.eecs.berkeley.edu/~jonas/cudnn-8.0-linux-x64-v5.1.tgz")
        sudo("tar xvf cudnn-8.0-linux-x64-v5.1.tgz")

    sudo('echo "/usr/local/cuda/lib64/" >> /etc/ld.so.conf')
    sudo('echo "/usr/local/cuda/extras/CPUTI/lib64/" >> /etc/ld.so.conf')
    sudo('ldconfig')

#Still need to configure s3cmd through s3cmd --configure
@task
@parallel
def inception_setup():
    #Install bazel
    run("wget https://github.com/bazelbuild/bazel/releases/download/0.4.3/bazel-0.4.3-jdk7-installer-linux-x86_64.sh")
    run("chmod +x bazel-0.4.3-jdk7-installer-linux-x86_64.sh")
    sudo("yum install -y java-1.7.0-openjdk-devel")
    run("JAVA_HOME=/usr/lib/jvm/java-openjdk/")
    run("export JAVA_HOME")
    run("PATH=$PATH:$JAVA_HOME/bin")
    run("export PATH")
    run("./bazel-0.4.3-jdk7-installer-linux-x86_64.sh --user")

    run("git clone https://github.com/tensorflow/models.git")
    with cd("~/models/inception/"):
        run("git checkout 91c7b91f834a5a857e8168b96d6db3b93d7b9c2a")
        run("bazel build inception/imagenet_train")
        run("bazel build inception/imagenet_distributed_train")

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
    #run("wget http://us.download.nvidia.com/XFree86/Linux-x86_64/370.28/NVIDIA-Linux-x86_64-370.28.run")
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
        sudo("wget http://people.eecs.berkeley.edu/~jonas/cudnn-8.0-linux-x64-v5.1.tgz")
        sudo("tar xvf cudnn-8.0-linux-x64-v5.1.tgz")

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

#TF_URL = "https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow-0.11.0rc1-cp27-none-linux_x86_64.whl"
#TF_URL="https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow_gpu-0.12.0rc0-cp27-none-linux_x86_64.whl"
TF_URL="https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow_gpu-0.12.1-cp27-none-linux_x86_64.whl"
@task
@parallel
def tf_setup():
    run("pip install --ignore-installed --upgrade {}".format(TF_URL))


@task
@parallel
def modified_tf_setup():
    run("git clone -b r0.12 https://github.com/Joranson/modifiedTF.git")
    run("mv modifiedTF tensorflow")
    run("pip install --ignore-installed --upgrade ~/tensorflow/wheel/tensorflow-0.12.1-cp27-cp27mu-linux_x86_64.whl")

@task
@parallel
def modified_inception_setup():
    #Install bazel
    run("wget https://github.com/bazelbuild/bazel/releases/download/0.4.3/bazel-0.4.3-jdk7-installer-linux-x86_64.sh")
    run("chmod +x bazel-0.4.3-jdk7-installer-linux-x86_64.sh")
    sudo("yum install -y java-1.7.0-openjdk-devel")
    run("JAVA_HOME=/usr/lib/jvm/java-openjdk/")
    run("export JAVA_HOME")
    run("PATH=$PATH:$JAVA_HOME/bin")
    run("export PATH")
    run("./bazel-0.4.3-jdk7-installer-linux-x86_64.sh --user")

    #Install TF0.12.1 GPU Version
    #TODO: install only the CPU version on Tensorflow
#    run("TF_BINARY_URL=https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow_gpu-0.12.1-cp27-none-linux_x86_64.whl")
#    sudo("sudo pip install --upgrade $TF_BINARY_URL")

    #Download inception
    #May need to checkout a different version
    run("git clone -b fewerLayers https://github.com/Joranson/modifiedInception.git")
    run("mv modifiedInception models")
    with cd("/home/ec2-user/models/inception"):
        run("bazel build inception/imagenet_distributed_train")

@task
@parallel
def keras_setup():
    run("conda install -y h5py")
    run("pip install keras")


@task
def terminate():
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    insts = []
    for i in ec2.instances.all():
        print i
        print i.state['Name']
        if i.state['Name'] == 'running':
            d = tags_to_dict(i.tags)
            if d['Name'] in env.hosts:
                i.terminate()
                insts.append(i)
            #Remove all hosts if no roles specified
            elif len(env.hosts) == 0:
                i.terminate()
                print 'terminated'
                insts.append(i)

@task
@parallel
def torch_setup():
    # TODO: make this idempotent. Add a line here to check if 
    # there's a torch directory, and, if so, delete it.

    # Install libjpeg-8d from source
    with cd('/tmp'):
        run('wget http://www.ijg.org/files/jpegsrc.v8d.tar.gz')
        run('tar xvf jpegsrc.v8d.tar.gz') 
    with cd('/tmp/jpeg-8d'):
        run('./configure')
        sudo('make')
        sudo('make install')
        sudo('ldconfig')
    run('echo export LD_PRELOAD="/usr/local/lib/libjpeg.so" >> ~/.bashrc')

    # Install torch 
    run("git clone https://github.com/torch/distro.git ~/torch --recursive")
    with shell_env(LD_PRELOAD="/usr/local/lib/libjpeg.so"):
        with cd('~/torch'):
            run('bash install-deps')
            run('./install.sh -b')

@task
@parallel
def torch_preroll():
    # Install libjpeg-8d from source
    with cd('/tmp'):
        run('wget http://www.ijg.org/files/jpegsrc.v8d.tar.gz')
        run('tar xvf jpegsrc.v8d.tar.gz') 
    with cd('/tmp/jpeg-8d'):
        run('./configure')
        sudo('make')
        sudo('make install')
        sudo('ldconfig')
    run('echo export LD_PRELOAD="/usr/local/lib/libjpeg.so" >> ~/.bashrc')

    # Install torch dependencies
    with shell_env(LD_PRELOAD="/usr/local/lib/libjpeg.so"):
        sudo('yum install -y cmake curl readline-devel ncurses-devel \
              gcc-c++ gcc-gfortran git gnuplot unzip libjpeg-turbo-devel \
              libpng-devel ImageMagick GraphicsMagick-devel fftw-devel \
              libgfortran python27-pip git openssl-devel')
        sudo('yum --enablerepo=epel install -y zeromq3-devel')
        sudo('pip install ipython')

@task
@parallel
def torch_setup_solo():
    # TODO: make this idempotent. Add a line here to check if 
    # there's a torch directory, and, if so, delete it.
    run("git clone https://github.com/torch/distro.git ~/torch --recursive")
    with shell_env(LD_PRELOAD="/usr/local/lib/libjpeg.so"):
        with cd('~/torch'):
            run('./install.sh -b')


# @task
# def efs_mount():
#     import boto.ec2
#     TGT_DIR = "/data"
#     EFS_SECURITY_GROUP="sg-a927bdcc"
#     FILESYSTEM_ID = "fs-bbd72012"

#     # add instance to the security group
#     instance_id = run("curl -s http://169.254.169.254/latest/meta-data/instance-id").strip()


#     ec2 = boto.ec2.connect_to_region(AWS_REGION)

#     instances = ec2.get_only_instances(instance_ids=[instance_id])
#     instance = instances[0]
#     EFS_SECURITY_GROUP = "sg-a927bdcc"
#     existing_groups = [g.id for g in instance.groups]
#     instance.modify_attribute("groupSet",existing_groups + [EFS_SECURITY_GROUP])


#     sudo("yum install -y -q nfs-utils")
#     sudo("mkdir -p %s" % TGT_DIR)
#     with warn_only():
#         sudo("umount -f %s" % TGT_DIR)

#     sudo("mount -t nfs4 -o nfsvers=4.1 $(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone).%s.efs.us-west-2.amazonaws.com:/ %s" % (FILESYSTEM_ID,  TGT_DIR))
#     sudo("chown ec2-user /data")
