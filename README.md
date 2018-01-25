# When to Run Distributed Tensorflow?
Michael Alan Chang, Lisa Jian, Pranay Kumar

Fabric file (`fabfile_awsgpu_distributed.py`) to help with the launching of EC2 instances and running of distributed Tensorflow experiments.

## Launching Cluster

Go into the file and set the number of workers (`NUM_WORKERS`) and number of parameter servers (`NUM_PARAM_SERVERS`) for your experiment. Then, set the types of each machine in the respective variables, `WORKER_TYPE` and `PS_TYPE`.

Run this command: 

`fab -f fabfile_awsgpu_distributed.py launch`

This command, upon completion, will launch the machines specified in the variables above, and perform the required status checks on them.

## Set Up Machines for the Experiment

After `launch` is completed, all the machines are ready to be set up. First, you must know what type of training you are running - CPU or GPU. In order to run GPU training, your workers must all be EC2 instances with GPUs (for example, `p2.xlarge` or `g3.4xlarge`). Additionally, you must know what model you will be running. The supported models are `inception`, `vgg`, `alexnet`, and `resnet`.

The parameter servers do not need a GPU, and thus will run the CPU setup. Run this command:

`fab -f fabfile_awsgpu_distributed.py -R <PS names, comma separated> cpu_setup:<model_name>`.

For example, if you had 2 parameter servers, and you were running Inception, the command would be:

`fab -f fabfile_awsgpu_distributed.py -R ps0,ps1 cpu_setup:inception`

For the workers, if you are doing CPU training, simply run the same command as you did for the parameter servers, except substitute the names of your workers, like this:

`fab -f fabfile_awsgpu_distributed.py -R <WORKER names, comma separated> cpu_setup:<model_name>`.

If doing GPU training, replace `cpu_setup` with `gpu_setup` in the command.

The workers also need to download the training data from the Amazon S3 bucket. To download from S3, create a file in the same directory as this script, titled `s3_config_file`. This will be uploaded to the remote machine as a config file.

The file should look like
```
access_key = YOUR ACCESS KEY
secret_key = YOUR SECRET KEY
bucket_location = YOUR BUCKET ZONE
```

While `cpu_setup` or `gpu_setup` is running for the workers, you will notice that after a minute or so, the machines reboot. After the reboot is over and more output starts showing up in the terminal, run this command in a new terminal:

`fab -f fabfile_awsgpu_distributed.py obtain_imagenet_data`

This will download the data from the S3 bucket for the workers.

## Running the Experiment

Time for the good stuff. Before running the experiment, you need to know 3 things.

- Model (`inception`, `vgg`, `alexnet`, or `resnet`) 
- Number of Parameter Servers
- Number of Workers

Once you have this info, simply run this command:

`fab -f fabfile_awsgpu_distributed.py start_experiment:<model_name>,<num_ps>,<num_workers>`

After the experiment terminates, there will be no more output in the terminal. The program won't stop running though, because parameter servers never technically terminate. To stop the experiment, close the terminal tab (after output has stopped!). Then, run the following command:

`fab -f fabfile_awsgpu_distributed.py -R <machines> shutdown_bazel:<model_name>`

`machines`, for example, could be `gpu0,gpu1,ps0,ps1'.

Simple, right? You might be asking, but how do I get the logs for each machine from the experiment I just run? You're in luck. Just run this command:

`fab -f fabfile_awsgpu_distributed.py obtain_logs:<model_name>,<dir_name>,<num_ps>,<num_workers>`

`<dir_name>` is the folder name of the place where you want your logs stored locally. You probably don't want to name it something dumb.

The organization of the logs will look like this (assume `dir_name` is **logs**, 2 PS, 3 Workers):

```
logs
--> ps0.txt
--> ps1.txt
--> wk0.txt
--> wk1.txt
--> wk2.txt
```

## Cleaning up

When you're done, terminate. This will terminate all machines and clean up the VPC that you set up.

`fab -f fabfile_awsgpu_distributed.py terminate`

# Now go do better things in your life than setting up AWS machines.
