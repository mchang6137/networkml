# When to Run Distributed Tensorflow?
Michael Alan Chang

Fabric file to help with launching EC2 P2 instances and getting GPU support set up for distributed tensorflow. 

## Launching Cluster

First go into the file, set the aws_public_key, aws availability zone, number of workers (`NUM_GPUs`), and number of parameter servers (`NUM_PARAM_SERVERS`).

`fab -f fabfile_awsgpu_distributed.py launch`

This will output the IP addresses of each of the machines in the cluster as well as the commands to run the Inception network in each of the machines. This will save you a lot of time. I promise.

For example, you'll get the following. After compiling the inception framework (shouldn't take more than a few seconds), you'll be able to run the output directly into the command line inside your machines. For example, you'll get the following:

`bazel-bin/inception/imagenet_distributed_train --batch_size=32 --data_dir=$HOME/imagenet-data --job_name='worker' --task_id=0 --ps_hosts=52.39.229.61:2222,52.42.52.251:2222,52.42.62.149:2222,35.161.217.103:2222 --worker_hosts=52.35.4.26:2222,35.161.245.253:2222,52.42.69.24:2222,52.42.51.73:2222,52.35.60.20:2222,52.27.160.29:2222,34.208.113.168:2222,35.161.206.237:2222`

Save all these outputted commands somewhere.

## Single Machine Training

The outputted commands you get are for distributed training. For single machine training, you can still run the `fabfile_awsgpu_distributed.py` file. Set `NUM_GPUs` to 1, and `NUM_PARAM_SERVERS` to 0. Launch the machine, and a command will get printed out, like this:

`bazel-bin/inception/imagenet_distributed_train --batch_size=32 --data_dir=$HOME/imagenet-data --job_name='worker' --task_id=0 --ps_hosts= --worker_hosts=52.35.4.26:2222`

Change this command to look like this:

`bazel-bin/inception/imagenet_distributed_train --batch_size=<32 * num_gpus> --num_gpus=<num_gpus> --data_dir=$HOME/imagenet-data`

num_gpus represents how many workers you want to use to train the model in this single machine case.

## Installing TF GPU Dependencies
Wait until you can ssh into the machines before installing dependencies:

`fab -f fabfile_awsgpu_distributed.py -R mygpu0 ssh`

To install dependencies, if you set NUM_GPUS=4 and NUM_PARAM_SERVERS=2, you would start in the following way:

`fab -f fabfile_awsgpu_distributed.py -R mygpu0,mygpu1,mygpu2,mygpu3,ps0,ps1 <setup_name>` 

Run the setups in this order:

`basic_setup`,

`cuda_setup8`,

`anaconda_setup`,

`tf_setup`,

`inception_setup`

## Setting up s3 bucket download

To download from s3, create a file in the same directory as this script, titled s3_config_file. This will be uploaded to the remote machine and then create a config file.

The file should look like
```
access_key = YOUR ACCESS KEY
secret_key = YOUR SECRET KEY
bucket_location = YOUR BUCKET ZONE
```

Just on the WORKER side, do the following. You do not need to download the training data on the parameter server.

`fab -f fabfile_awsgpu_distributed.py -R mygpu0,mygpu1,mygpu2,mygpu3 s3_setup`

If you want other people to access your machine, simply go the .ssh/credentials and add their ssh public key to that file.

## Cleaning up

When you're done, terminate. This will terminate all machines and clean up the VPC that you set up.

`fab -f fabfile_awsgpu_distributed.py terminate`

`fab -f fabfile_awsgpu_distributed.py vpc_cleanup`

# Go do better things in your life than setting up AWS machines.
