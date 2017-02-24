"""
fabric file to help with launching EC2 P2 instancesand
getting GPU support set up. Also installs latest
anaconda and then tensorflow. Use:

fab -f fabfile_awsgpu.py launch

# wait until you can ssh into the instance with
fab -f fabfile_awsgpu.py -R mygpu ssh

# install everything
fab -f fabfile_awsgpu.py -R mygpu basic_setup cuda_setup8 anaconda_setup tf_setup inception_setup


# when you're done, terminate
fab -f fabfile_awsgpu.py -R mygpu terminate


Took inspiration from:
https://aws.amazon.com/blogs/aws/new-p2-instance-type-for-amazon-ec2-up-to-16-gpus/

"""


from fabric.api import local, env, run, put, cd, task, \
    sudo, settings, warn_only, lcd, path, get
from fabric.contrib import project
from time import sleep
import boto3
import os

tgt_ami = 'ami-b04e92d0'
AWS_REGION = 'us-west-2'
AWS_AVAILABILITY_ZONE = 'us-west-2b'
#import ssh public key to AWS
my_aws_key = 'michael'
instance_name = "mygpu"
role_name = instance_name
param_server = "param_server"
num_gpus = 2
CONDA_DIR = "$HOME/anaconda"
INSTANCE_TYPE = 'p2.xlarge'
PARAM_SERVER_TYPE = 'm4.large'
USER = os.environ['USER']
# this is a dumb hack but whatever
if os.path.exists("fabfile_{}.py".format(USER)):
    exec("from fabfile_{} import *".format(USER))


def tags_to_dict(d):
    return {a['Key'] : a['Value'] for a in d}

def get_target_instance():
    res = []
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)

    for i in ec2.instances.all():
        if i.state['Name'] == 'running':
            d = tags_to_dict(i.tags)
            if d['Name'] == instance_name:
                res.append('ec2-user@{}'.format(i.public_dns_name))
    print "found", res
    return {role_name : res}

#env.roledefs.update(get_target_instance())
#env.hosts = ['ec2-35-167-153-191.us-west-2.compute.amazonaws.com']
#env.disable_known_hosts = True

@task
def vpc_cleanup():
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    #Delete Subnets
    for subnet in ec2_resource.subnets.all():
        print 'Subnet ID {}'.format(subnet.id)
        try:
            ec2_client.delete_subnet(SubnetId=subnet.id)
            print '{} deleted'.format(subnet.id)
        except:
            print '{} not deleted'.format(subnet.id)

    #Detach Gateways
    for vpc in ec2_resource.vpcs.all():
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
        try:
            ec2_client.delete_route_table(RouteTableId=route_table.id)
            print '{} deleted'.format(route_table.id)
        except:
            print '{} not deleted'.format(route_table.id)
            
    #Finally, Delete VPC
    for vpc in ec2_resource.vpcs.all():
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
    #Crete Network ACL -- probably don't need this right? default is to allow all inbound and outbound traffic
    # create_network_acl(VpcId=vpc.id)
    #Create the subnet for the VPC
    subnet = vpc.create_subnet(DryRun=use_dry_run, CidrBlock='10.0.0.0/25', AvailabilityZone=AWS_AVAILABILITY_ZONE)
    ec2_client.modify_subnet_attribute(SubnetId=subnet.subnet_id, MapPublicIpOnLaunch={'Value':True})
    #Create an Internet Gateway
    gateway = ec2_resource.create_internet_gateway(DryRun=use_dry_run)
    gateway.attach_to_vpc(DryRun=use_dry_run, VpcId=vpc.vpc_id)
    #Create a Route table and add the route
    route_table = ec2_client.create_route_table(DryRun=use_dry_run, VpcId=vpc.vpc_id)
    route_table_id = route_table['RouteTable']['RouteTableId']
    ec2_client.create_route(DryRun=use_dry_run, DestinationCidrBlock='0.0.0.0/0',RouteTableId=route_table_id,GatewayId=gateway.internet_gateway_id)
    return vpc, subnet

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
                    'SnapshotId' : 'snap-c87f35ec'
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
def setup_reserved_instance(ec2_client, ec2_resource, instance_name, server_instance_type, subnet, instance_count):
    use_dry_run = False

    BlockDeviceMappings=[
        {
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'VolumeSize': 100,
                'DeleteOnTermination': True,
                'VolumeType': 'standard',
                'SnapshotId' : 'snap-c87f35ec'
            },
        },
    ]
    
    #Create a cluster of p2.xlarge instances
    instances = ec2_resource.create_instances(ImageId=tgt_ami, MinCount=instance_count, MaxCount=instance_count,
                                     KeyName=my_aws_key, InstanceType=server_instance_type, SubnetId=subnet.subnet_id,
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
        #Associate addreses with the instance
        #elastic_ip = ec2_client.allocate_address(Domain='vpc')
        #print 'IP address is {}'.format(elastic_ip)
        #elastic_public = elastic_ip['PublicIp']
        #elastic_allocation = elastic_ip['AllocationId']
        #ec2_client.associate_address(InstanceId=inst.instance_id, AllocationId=elastic_allocation)

    return instances
    
@task
def launch():
    #For Debugging
    use_dry_run = False
    
    ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    vpc,subnet = setup_network()

    #Create a parameter server connected to the VPC
    #setup_spot_instance(ec2_client, ec2_resource, 'param_server', 'm4.large', subnet, 2)
    setup_reserved_instance(ec2_client, ec2_resource, 'param_server', 'm4.large', subnet, 2)
    
    return

@task
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
def basic_setup():
    print env.host_string
    print env.hosts
    run("sudo yum update -q -y")
    run("sudo yum groupinstall 'Development Tools' -q -y")
    run("sudo yum install -q -y emacs tmux  gcc g++ dstat htop")
    run("sudo yum install -y kernel-devel-`uname -r`")



@task
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
def inception_setup():
    #Install bazel
    run("wget https://github.com/bazelbuild/bazel/releases/download/0.4.3/bazel-0.4.3-jdk7-installer-linux-x86_64.sh")
    run("chmod +x bazel-0.4.3-jdk7-installer-linux-x86_64.sh")
    sudo("yum install java-1.7.0-openjdk-devel")
    run("JAVA_HOME=/usr/lib/jvm/java-openjdk/")
    run("export JAVA_HOME")
    run("PATH=$PATH:$JAVA_HOME/bin")
    run("export PATH")
    run("./bazel-0.4.3-jdk7-installer-linux-x86_64.sh --user")

    #Install s3cmd
    sudo("yum --enablerepo=epel install s3cmd")
    

    #Install TF0.12.1
    run("TF_BINARY_URL=https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow_gpu-0.12.1-cp27-none-linux_x86_64.whl")
    sudo("sudo pip install --upgrade $TF_BINARY_URL")

    #Download inception
    #May need to checkout a different version
    run("git clone https://github.com/tensorflow/models.git")
    with cd("~/models/inception/"):
        run("git checkout 91c7b91f834a5a857e8168b96d6db3b93d7b9c2a")
    
@task
def cuda_setup8():

    run("wget http://us.download.nvidia.com/XFree86/Linux-x86_64/370.28/NVIDIA-Linux-x86_64-370.28.run")
    run("wget https://developer.nvidia.com/compute/cuda/8.0/prod/local_installers/cuda_8.0.44_linux-run")
    run("mv NVIDIA-Linux-x86_64-370.28.run driver.run")
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
def anaconda_setup():
    run("wget https://repo.continuum.io/archive/Anaconda2-4.2.0-Linux-x86_64.sh")
    run("chmod +x Anaconda2-4.2.0-Linux-x86_64.sh")
    run("./Anaconda2-4.2.0-Linux-x86_64.sh -b -p {}".format(CONDA_DIR))
    run('echo "export PATH={}/bin:$PATH" >> .bash_profile'.format(CONDA_DIR))
    run("conda upgrade -q -y --all")
    run("conda install -q -y pandas scikit-learn scikit-image matplotlib seaborn ipython")
    run("pip install ruffus glob2 awscli")

#TF_URL = "https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow-0.11.0rc1-cp27-none-linux_x86_64.whl"
#TF_URL="https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow_gpu-0.12.0rc0-cp27-none-linux_x86_64.whl"
TF_URL="https://storage.googleapis.com/tensorflow/linux/gpu/tensorflow_gpu-0.12.1-cp27-none-linux_x86_64.whl"
@task
def tf_setup():
    run("pip install --ignore-installed --upgrade {}".format(TF_URL))

@task
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
            #d = tags_to_dict(i.tags)
            #if d['Name'] == instance_name:
            i.terminate()
            insts.append(i)

@task
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
