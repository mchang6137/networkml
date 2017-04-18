import csv
import argparse

def model_distributed(num_trials, model_param, infra_param):
    trial_RTT = []
    for trial_num in range(num_trials):
        distribution_steps = []
        #Start the distribution step
        distribution_steps.append(serialization_time(model_param, infra_param, trial_num))
        distribution_steps.append(network_overhead(model_param, infra_param, trial_num))
        distribution_steps.append(deserialization_time(model_param, infra_param, trial_num))
        RTT_distribution = calculate_pipeline_time(distribution_steps, model_param, trial_num)

        aggregation_steps = []
        aggregation_steps.append(gpu_compute_time(model_param, infra_param, trial_num))
        aggregation_steps.append(serialization_time(model_param, infra_param, trial_num))
        aggregation_steps.append(network_overhead(model_param, infra_param, trial_num))
        aggregation_steps.append(deserialization_time(model_param, infra_param, trial_num))
        RTT_aggregation = calculate_pipeline_time(aggregation_steps, model_param, trial_num)

        overall_RTT = RTT_aggregation + RTT_distribution
        pretty_print_results(overall_RTT, RTT_distribution, RTT_aggregation, model_param, infra_param, trial_num)
        trial_RTT.append(overall_RTT)
        
    return trial_RTT

def model_single(num_trials, model_param, infra_param):
    trial_RTT = []
    
    #Start the distribution step
    for trial_num in range(num_trials):
        distribution_steps = []
        distribution_steps.append(pcie_overhead(model_param, infra_param, trial_num))
        RTT_distribution = calculate_pipeline_time(distribution_steps, model_param, trial_num)

        aggregation_steps = []
        aggregation_steps.append(gpu_compute_time(model_param, infra_param, trial_num))
        aggregation_steps.append(pcie_overhead(model_param, infra_param, trial_num))
        RTT_aggregation = calculate_pipeline_time(aggregation_steps, model_param, trial_num)

        overall_RTT = RTT_distribution + RTT_aggregation
        pretty_print_results(overall_RTT, RTT_distribution, RTT_aggregation, model_param, infra_param, trial_num)
        trial_RTT.append(overall_RTT)
        
    return trial_RTT

def pretty_print_results(RTT, RTT_distribution, RTT_aggregation, model_params, infra_params, trial_index):
    print 'For Trial Index {}'.format(trial_index)
    for param in model_params:
        print '{}: {}'.format(param, model_params[param][trial_index])

    for param in infra_params:
        print '{}: {}'.format(param, infra_params[param][trial_index])

    print 'Distribution step: {} seconds'.format(RTT_distribution)
    print 'Aggregation step: {} seconds'.format(RTT_aggregation)
    print 'The calculated RTT was {} seconds\n\n'.format(RTT)

def calculate_pipeline_time(phase_steps, model_param, trial_index):
    num_params = model_param['num_parameters'][trial_index]
    total_time = 0 
    max_step_duration = 0
    for step_num in range(len(phase_steps)):
        total_time += phase_steps[step_num]
        if phase_steps[step_num] > max_step_duration:
            max_step_duration = phase_steps[step_num]
    total_time += max_step_duration * (num_params - 1)
    return total_time
    
def serialization_time(model_params, infra_params, trial_index):
    return 0

def deserialization_time(model_params, infra_params, trial_index):
    return 0

def network_overhead(model_params, infra_params, trial_index):
    worker_bandwidth = infra_params['worker_net_bandwidth'][trial_index]
    ps_bandwidth = infra_params['ps_net_bandwidth'][trial_index]
    num_workers = infra_params['num_workers'][trial_index]
    
    min_bandwidth = ps_bandwidth
    if worker_bandwidth < (ps_bandwidth / float(num_workers)):
        min_bandwidth = worker_bandwidth
    else:
        min_bandwidth = float(ps_bandwidth) / num_workers

    bits_min_bandwidth = float(min_bandwidth * (10 ** 9))
    bits_parameter_size = model_params['parameter_size'][trial_index] * 8

    network_time = bits_parameter_size / bits_min_bandwidth
    return network_time

def pcie_overhead(model_params, infra_params, trial_index):
    bandwidth = infra_params['pcie_bandwidth'][trial_index]

    bits_min_bandwidth = bandwidth * (10 ** 9)
    bits_parameter_size = model_params['parameter_size'][trial_index] * 8

    network_time = bits_parameter_size / float(bits_min_bandwidth)
    return network_time
            
#Time it takes for the training to occur on the individual GPU
#i.e., Forward Pass and Back-propagation
def gpu_compute_time(model_params, infra_params, trial_index):
    #Number of parameters as a proxy for number of layers
    num_params = model_params['num_parameters'][trial_index]
    batch_size = model_params['batch_size'][trial_index]

    runtime = 0.017 * batch_size / num_params
    return runtime

#Time it takes for the parameter server to average all the PS updates
def ps_agg_time(model_params, trial_index):
    #Assumed to be negligle for now
    return 0

#Ensures that all of the parameters have the same number of trials
def prep_variables(num_trials, params):
    for key in params:
        if len(params[key]) != num_trials:
            first_key = params[key][0]
            while len(params[key]) != num_trials:
                params[key].append(first_key)

    return params

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("setting", help="Options: distributed or single")
    args = parser.parse_args()

    #Each param dict maps to a list of elements. The 0th element in the list corresponds to the 0th trial, while the 1st element corresponds to the 1st trial, etc.

    num_trials = 3
    
    model_params = {}
    #Average size of parameter in bytes (b) 
    model_params['parameter_size'] = [528000]
    #Number of training parameters (k)
    model_params['num_parameters'] = [196]
    #Number of training examples handled by each worker (i)
    model_params['batch_size'] = [32, 48, 64]

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
    

    infra_params = prep_variables(num_trials, infra_params)
    model_params = prep_variables(num_trials, model_params)

    if args.setting == 'distributed':
        model_distributed(num_trials, model_params, infra_params)
    else:
        model_single(num_trials, model_params, infra_params)
    
    
    
