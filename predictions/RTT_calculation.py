import csv
import argparse
import experiment_setting as exp
import actual_results as actual
import matplotlib.pylab as plt

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

    #Number of layers, not number of parameters?
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

def plot_results(experiment_str, setting_str, result, independent_var):
    assert len(result) == len(independent_var)
    prediction_result = {}
    for x in range(len(result)):
        prediction_result[independent_var[x]] = result[x]

    plt.title('Time/Iteration for {}, varying {}'.format(setting_str, experiment_str), fontname="Times New Roman", size=20)
    plt.ylabel('Time/Iteration in seconds', fontname="Times New Roman", size=16)
    plt.xlabel('{}'.format(experiment_str), fontname="Times New Roman", size=16)

    actual_mean = []
    actual_std = []
    if setting_str == 'single':
        actual_mean, actual_std = actual.get_single_results(experiment_str, independent_var)
    elif setting_str == 'distributed':
        actual_mean, actual_std = actual.get_distributed_results(experiment_str, independent_var)
                                                    
    font = {'family':'serif','serif':['Times']}
    actual_line_color = '#990000'
    prediction_line_color = 'black'    
    error_length = 1

    plt.plot(*zip(*sorted(prediction_result.items())), color=prediction_line_color)
    line, = plt.plot(independent_var, actual_mean, lw=3, color=actual_line_color)
    plt.errorbar(independent_var, actual_mean, actual_std, lw=error_length, color=actual_line_color)
    plt.grid()
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("setting", help="Options: distributed or single")
    parser.add_argument("exp", help="Options: batchsize, num_worker, num_ps")
    args = parser.parse_args()

    independent_var = []
    if args.exp == 'batchsize':
        num_trials, model_params, infra_params = exp.vary_batch_size()
        independent_var = model_params['batch_size']
    elif args.exp == 'worker':
        num_trials, model_params, infra_params = exp.vary_worker_size()
        independent_var = infra_params['num_workers']
    elif args.exp == 'num_ps':
        num_trials, model_params, infra_params = exp.vary_ps_size()
        independent_var = infra_params['num_ps']
    else:
        print 'Invalid experiment'
        exit()

    assert len(independent_var) == num_trials

    infra_params = prep_variables(num_trials, infra_params)
    model_params = prep_variables(num_trials, model_params)

    all_RTT = []
    if args.setting == 'distributed':
        all_RTT = model_distributed(num_trials, model_params, infra_params)
    else:
        all_RTT = model_single(num_trials, model_params, infra_params)

    plot_results(args.exp, args.setting, all_RTT, independent_var)

    
    
    
    
