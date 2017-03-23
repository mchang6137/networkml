# networkml

Fabric file to help with launching EC2 P2 instances and
getting GPU support set up for distributed tensorflow.
Also installs latest anaconda and then tensorflow.

## Launching Cluster

First go into the file, set the aws_public key, aws availability zone, number of workers (NUM_GPUs), and number of parameter servers (NUM_PARAM_SERVERS).

fab -f fabfile_awsgpu_distributed.py launch

This command will also output commands to run in each machine.

## Installing TF GPU Dependencies
Wait until you can ssh into the machines before installing dependencies
fab -f fabfile_awsgpu_distributed.py -H mygpu ssh

#For example, if you set NUM_GPUS=4 and NUM_PARAM_SERVERS=2, you would start in the following way
fab -f fabfile_awsgpu_distributed.py -H mygpu0,mygpu1,mygpu2,mygpu3,ps0,ps1 basic_setup cuda_setup8 anaconda_setup tf_setup inception_setup
#Ignore the Name lookup error!

## Setting up s3 bucket download
To download from s3, create a file in the same directory as this script, titled s3_config_file
The file should look like
access_key = YOUR ACCESS KEY
secret_key = YOUR SECRET KEY
bucket_location = YOUR BUCKET ZONE

Just on the WORKER side, do the following. You do not need to download the training data on the parameter server.

fab -f fabfile_awsgpu_distributed.py -H mygpu0,mygpu1,mygpu2,mygpu3,ps0 s3_setup

## Cleaning up

When you're done, terminate. This will terminate all machines!
fab -f fabfile_awsgpu_distributed.py terminate
fab -f fabfile_awsgpu_distributed.py vpc_cleanup