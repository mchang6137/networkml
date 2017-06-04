#Experiment settings
# All experiments should define all the parameters in model_params and infra_params
# This all assumes that you fix all values and toggle all the remaining values

#Available Network bandwidth of each machine (all in Gbps)
machine_bandwidth = {'p2.xlarge': 1,
                     'p2.8xlarge': 10,
                     'p2.16xlarge': 20,
                     'c4.8xlarge': 10}

#For experiments where you maintain the number of workers (so we can assume a given learning rate)
#Fix everything except for the number of workers/machine
#num_machines is a list of the number of machines
#worker_type describe the type of machine for each of these workers
def vary_workers_per_machine(args):
    assert len(num_machines_list) == len(machine_types_list)
    assert args['ps_type'][0] in machine_bandwidth
    
    model_params = {}
    #Number of training parameters 
    model_params['num_parameters'] = [11]
    model_params['parameter_size'] = [96000000.0 / model_params['num_parameters'][0]]
    #model_params['parameter_size'] = [5000000]

    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [32]

    infra_params = {}
    infra_params['num_machines'] = args['num_machines']
    infra_params['worker_net_bandwidth'] = [machine_bandwidth[args['machine_type'][0]] for machine_type in machine_types_list]
    infra_params['ps_net_bandwidth'] = [machine_bandwidth[args['ps_type'][0]]]
    infra_params['num_ps'] = args['num_ps']
    infra_params['Network_latency'] = [0.01]
    infra_params['num_workers'] = args['num_workers']

    num_trials = len(num_machines_list)
    return num_trials, model_params, infra_params

def vary_batch_size(args):
    model_params = {}
    #Average size of parameter in bytes (b)
    model_params['parameter_size'] = [5000000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [20]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = args['batch_size']

    infra_params = {}
    #Number of Workers
    infra_params['num_machines'] = args['num_machines']
    #Minimum bandwidth over all workers in Gbps
    infra_params['worker_net_bandwidth'] = [1]
    #Minimum bandwidth over all parameter servers in Gbps
    infra_params['ps_net_bandwidth'] = [10]
    #Bandwidth of the PCIe for single machine case in Gbps
    infra_params['pcie_bandwidth'] = [40]
    #Latency over the network in ms
    infra_params['Network_latency'] = [0.01]
    infra_params['num_ps'] = args['num_ps']
    infra_params['num_workers'] = args['num_workers']

    num_trials = len(model_params['batch_size'])
    return num_trials, model_params, infra_params

#Vary the number of workers and nothing else
def vary_worker_size():
    model_params = {}
    #Average size of parameter in bytes (b)
    model_params['parameter_size'] = [5000000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [20]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [32]

    infra_params = {}
    #Number of Workers
    infra_params['num_machines'] = [1,2,4,8]
    #Minimum bandwidth over all workers in Gbps
    infra_params['worker_net_bandwidth'] = [1]
    #Minimum bandwidth over all parameter servers in Gbps
    infra_params['ps_net_bandwidth'] = [10]
    #Bandwidth of the PCIe for single machine case in Gbps
    infra_params['pcie_bandwidth'] = [40]
    #Latency over the network in ms
    infra_params['Network_latency'] = [0.01]
    infra_params['num_workers'] = infra_params['num_machines']

    num_trials = len(infra_params['num_machines'])
    return num_trials, model_params, infra_params

#Fix everything except the number of parameter servers
def vary_ps_num(args):
    assert args['ps_type'][0] in machine_bandwidth
    assert args['machine_type'][0] in machine_bandwidth
    
    num_trials = 3
    model_params = {}
    #Average size of parameter in bytes (b)
    model_params['parameter_size'] = [5000000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [20]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [32]

    infra_params = {}
    #Number of physical machines
    infra_params['num_machines'] = args['num_machines']
    
    #Number of PS
    infra_params['num_ps'] = args['num_ps']
    #Minimum bandwidth over all workers in Gbps
    infra_params['worker_net_bandwidth'] = [machine_bandwidth[args['machine_type'][0]]]
    #Minimum bandwidth over all parameter servers in Gbps
    infra_params['ps_net_bandwidth'] = [machine_bandwidth[args['ps_type'][0]]]
    #Bandwidth of the PCIe for single machine case in Gbps
    infra_params['pcie_bandwidth'] = [40]
    #Latency over the network in ms
    infra_params['Network_latency'] = [0.01]
    #Number of GPU workers
    infra_params['num_workers'] = args['num_workers']

    num_trials = len(infra_params['num_ps'])
    return num_trials, model_params, infra_params
