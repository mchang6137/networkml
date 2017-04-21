#Experiment settings
#All experiments should define all the parameters in model_params and infra_params

def vary_batch_size():
    model_params = {}
    #Average size of parameter in bytes (b)
    model_params['parameter_size'] = [528000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [196]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [8, 16, 32, 48, 64]

    infra_params = {}
    #Number of Workers
    infra_params['num_workers'] = [8]
    #Minimum bandwidth over all workers in Gbps
    infra_params['worker_net_bandwidth'] = [1]
    #Minimum bandwidth over all parameter servers in Gbps
    infra_params['ps_net_bandwidth'] = [10]
    #Bandwidth of the PCIe for single machine case in Gbps
    infra_params['pcie_bandwidth'] = [40]
    #Latency over the network in ms
    infra_params['Network_latency'] = [0.01]

    num_trials = len(model_params['batch_size'])
    return num_trials, model_params, infra_params

def vary_worker_size():
    model_params = {}
    #Average size of parameter in bytes (b)
    model_params['parameter_size'] = [528000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [196]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [32]

    infra_params = {}
    #Number of Workers
    infra_params['num_workers'] = [1,2,4,8]
    #Minimum bandwidth over all workers in Gbps
    infra_params['worker_net_bandwidth'] = [1]
    #Minimum bandwidth over all parameter servers in Gbps
    infra_params['ps_net_bandwidth'] = [10]
    #Bandwidth of the PCIe for single machine case in Gbps
    infra_params['pcie_bandwidth'] = [40]
    #Latency over the network in ms
    infra_params['Network_latency'] = [0.01]

    num_trials = len(model_params['num_workers'])
    return num_trials, model_params, infra_params
    
def vary_ps_size():
    num_trials = 3
    model_params = {}
    #Average size of parameter in bytes (b)
    model_params['parameter_size'] = [528000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [196]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [32]

    infra_params = {}
    #Number of Workers
    infra_params['num_workers'] = [8]
    #Number of PS
    infra_params['num_ps'] = [1,2,4]
    #Minimum bandwidth over all workers in Gbps
    infra_params['worker_net_bandwidth'] = [1]
    #Minimum bandwidth over all parameter servers in Gbps
    infra_params['ps_net_bandwidth'] = [10]
    #Bandwidth of the PCIe for single machine case in Gbps
    infra_params['pcie_bandwidth'] = [40]
    #Latency over the network in ms
    infra_params['Network_latency'] = [0.01]

    num_trials = len(model_params['num_ps'])
    return num_trials, model_params, infra_params
