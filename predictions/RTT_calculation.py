import csv
import argparse
import experiment_setting as exp
import actual_results as actual
import matplotlib.pylab as plt
import plot_results as plot
import numpy as np

def model_distributed(num_trials, model_param, infra_param):
    trial_overall_RTT = []
    trial_agg_RTT = []
    trial_dist_RTT = []
    trial_dequeue = []
    trial_fp = []
    
    for trial_num in range(num_trials):
        additional_time = 0
        distribution_steps = []
        #Start the distribution step
        distribution_steps.append(serialization_time(model_param, infra_param, trial_num))
        distribution_steps.append(network_overhead(model_param, infra_param, trial_num))
        distribution_steps.append(deserialization_time(model_param, infra_param, trial_num))
        RTT_distribution = calculate_pipeline_time(distribution_steps, model_param, trial_num)
        additional_time += calculate_dequeue_time(model_param, infra_param, trial_num)
        trial_dequeue.append(additional_time)
        trial_dist_RTT.append(RTT_distribution)
        
        aggregation_steps = []
        additional_time += calculate_forwardpass_time(model_param, infra_param, trial_num)
        trial_fp.append(calculate_forwardpass_time(model_param, infra_param, trial_num))
        aggregation_steps.append(gpu_compute_time(model_param, infra_param, trial_num))
        aggregation_steps.append(serialization_time(model_param, infra_param, trial_num))
        aggregation_steps.append(network_overhead(model_param, infra_param, trial_num))
        aggregation_steps.append(deserialization_time(model_param, infra_param, trial_num))
        RTT_aggregation = calculate_pipeline_time(aggregation_steps, model_param, trial_num)
        trial_agg_RTT.append(RTT_distribution)

        overall_RTT = RTT_aggregation + RTT_distribution + additional_time
        pretty_print_results(overall_RTT, RTT_distribution, RTT_aggregation, model_param, infra_param, trial_num)
        
        trial_overall_RTT.append(overall_RTT)
        
    return trial_overall_RTT, trial_agg_RTT, trial_dist_RTT, trial_dequeue, trial_fp

def model_single(num_trials, model_param, infra_param):
    trial_overall_RTT = []
    trial_dist_RTT = []
    trial_agg_RTT = []
    trial_dequeue = []
    trial_fp = []
    
    #Start the distribution step
    for trial_num in range(num_trials):
        additional_time = 0
        distribution_steps = []
        distribution_steps.append(pcie_overhead(model_param, infra_param, trial_num))
        RTT_distribution = calculate_pipeline_time(distribution_steps, model_param, trial_num)
        trial_dist_RTT.append(RTT_distribution)
        additional_time += calculate_dequeue_time(model_param, infra_param, trial_num)
        trial_dequeue.append(additional_time)
        
        aggregation_steps = []
        additional_time += calculate_forwardpass_time(model_param, infra_param, trial_num)
        trial_fp.append(calculate_forwardpass_time(model_param, infra_param, trial_num))
        aggregation_steps.append(gpu_compute_time(model_param, infra_param, trial_num))
        aggregation_steps.append(pcie_overhead(model_param, infra_param, trial_num))
        RTT_aggregation = calculate_pipeline_time(aggregation_steps, model_param, trial_num)
        trial_agg_RTT.append(RTT_aggregation)

        overall_RTT = RTT_distribution + RTT_aggregation + additional_time
        pretty_print_results(overall_RTT, RTT_distribution, RTT_aggregation, model_param, infra_param, trial_num)
        trial_overall_RTT.append(overall_RTT)
        
    return trial_overall_RTT, trial_agg_RTT, trial_dist_RTT, trial_dequeue, trial_fp

def pretty_print_results(RTT, RTT_distribution, RTT_aggregation, model_params, infra_params, trial_index):
    print 'For Trial Index {}'.format(trial_index)
    for param in model_params:
        print '{}: {}'.format(param, model_params[param][trial_index])

    for param in infra_params:
        print '{}: {}'.format(param, infra_params[param][trial_index])

    print 'Distribution step: {} seconds'.format(RTT_distribution)
    print 'Aggregation step: {} seconds'.format(RTT_aggregation)
    print 'The calculated RTT was {} seconds\n\n'.format(RTT)

#Non-pipelined time of the forward pass
def calculate_forwardpass_time(model_param, infra_param, trial_index):
    batch_size = model_params['batch_size'][trial_index]
    fp = 0.0117 * batch_size + 0.06
    print 'For batch size {} fp time was {}'.format(batch_size, fp)
    return fp

#Non-pipelined time of the dequeue time
def calculate_dequeue_time(model_param, infra_param, trial_index):
    batch_size = model_params['batch_size'][trial_index]
    worker_per_machine = float(infra_params['num_workers'][trial_index]) /  infra_params['num_machines'][trial_index]
    dequeue_time = 3.0/50 * worker_per_machine + 19.0/4800 * batch_size - 7.0/30
    print 'For batch size {}, workers {} dequeue time was {}'.format(batch_size, worker_per_machine, dequeue_time)
    return dequeue_time

def calculate_pipeline_time(phase_steps, model_param, trial_index):
    num_params = model_param['num_parameters'][trial_index]
    total_time = 0 
    max_step_duration = 0
    max_step_num = 0
    for step_num in range(len(phase_steps)):
        total_time += phase_steps[step_num]
        if phase_steps[step_num] > max_step_duration:
            max_step_duration = phase_steps[step_num]
            max_step_num = step_num
    total_time += max_step_duration * (num_params - 1)
    print 'Bottlenecked step is {}'.format(max_step_num)
    return total_time
    
def serialization_time(model_params, infra_params, trial_index):
    num_params = model_params['num_parameters'][trial_index]
    return 0.09 / num_params

def deserialization_time(model_params, infra_params, trial_index):
    num_params = model_params['num_parameters'][trial_index]
    return 0.09 / num_params

def network_overhead(model_params, infra_params, trial_index):
    worker_bandwidth = infra_params['worker_net_bandwidth'][trial_index]
    ps_bandwidth = infra_params['ps_net_bandwidth'][trial_index]
    num_machines = infra_params['num_machines'][trial_index]
    num_ps = infra_params['num_ps'][trial_index]
    num_workers = infra_params['num_workers'][trial_index]

    worker_per_machine = float(num_workers) / num_machines
    
    min_bandwidth = ps_bandwidth
    bits_min_bandwidth = 0
    bits_parameter_size = 0
    if worker_bandwidth/worker_per_machine < (num_ps * ps_bandwidth / float(num_workers)):
        min_bandwidth = worker_bandwidth / worker_per_machine
        bits_min_bandwidth = float(min_bandwidth * (10 ** 9))
        bits_parameter_size = model_params['parameter_size'][trial_index] * 8 
    else:
        min_bandwidth = float(ps_bandwidth) / num_workers
        bits_min_bandwidth = float(min_bandwidth * (10 ** 9))
        bits_parameter_size = model_params['parameter_size'][trial_index] * 8 / float(num_ps)

    network_time = bits_parameter_size / bits_min_bandwidth
    print 'The Network time is {}'.format(network_time)
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

def plot_stackbar(agg_RTT, dist_RTT, dequeue_time, fp_pass, independent_var):
    assert len(agg_RTT) == len(independent_var)
    
    width = 5
    #ind = np.arange(len(agg_RTT))

    p1 = plt.bar(independent_var, agg_RTT, width, color='blue')
    p2 = plt.bar(independent_var, dist_RTT, width, bottom=agg_RTT, color='red')
    p3 = plt.bar(independent_var, dequeue_time, width, bottom=np.array(dist_RTT) + np.array(agg_RTT), color='green')
    p4 = plt.bar(independent_var, fp_pass, width, bottom=np.array(dist_RTT) + np.array(agg_RTT) + np.array(dequeue_time), color='yellow')

    plt.legend((p1[0], p2[0], p3[0], p4[0]), ('Aggregation', 'Distribution', 'Dequeue time', 'Forward pass'), loc="upper left")
    plt.ylim((0, 4))

    plt.show()

def plot_results(experiment_str, setting_str, result, independent_var):
    assert len(result) == len(independent_var)
    prediction_result = {}
    for x in range(len(result)):
        prediction_result[independent_var[x]] = result[x]

    plt.title('Predicting RTT for {}, varying {}'.format(setting_str, experiment_str), fontname="Times New Roman", size=20)
    plt.ylabel('Time/Iteration in seconds', fontname="Times New Roman", size=16)
    plt.xlabel('{} size'.format(experiment_str), fontname="Times New Roman", size=16)

    actual_mean = []
    actual_std = []
    #if setting_str == 'single':
    #    actual_mean, actual_std = actual.get_single_results(experiment_str, independent_var)
    #elif setting_str == 'distributed':
    #    actual_mean, actual_std = actual.get_distributed_results(experiment_str, independent_var)
                                                    
    font = {'family':'serif','serif':['Times']}
    actual_line_color = '#990000'
    prediction_line_color = 'black'    
    error_length = 1

    line1, = plt.plot(*zip(*sorted(prediction_result.items())), color=prediction_line_color, label='Predicted RTT')
    #line2, = plt.plot(independent_var, actual_mean, lw=3, color=actual_line_color, label='Actual RTT')
    #plt.legend(handles=[line1, line2])
    #plt.errorbar(independent_var, actual_mean, actual_std, lw=error_length, color=actual_line_color)
    plt.grid()

def get_exp_params(exp_type, num_machines=[1], num_workers=[8], num_ps=[1], batch_size=[32], ps_type=['c4.8xlarge'], machine_type=['p2.8xlarge']):
    independent_var = []
    args = {}
    args['num_machines'] = num_machines
    args['num_workers'] = num_workers
    args['num_ps'] = num_ps
    args['batch_size'] = batch_size
    args['ps_type'] = ps_type
    args['machine_type'] = machine_type
    
    if exp_type == 'batchsize':
        num_trials, model_params, infra_params = exp.vary_batch_size(args)
        independent_var = model_params['batch_size']
    elif exp_type == 'worker':
        num_trials, model_params, infra_params = exp.vary_worker_size(args)
        independent_var = infra_params['num_machines']
    elif exp_type == 'num_ps':
        num_trials, model_params, infra_params = exp.vary_ps_num(args)
        independent_var = infra_params['num_ps']
    elif exp_type == 'physical_machines':
        num_trials, model_params, infra_params = exp.vary_workers_per_machine(args)
        independent_var = infra_params['num_machines']
    else:
        print 'Invalid experiment'
        exit()

    #Format the experiments separately
    infra_params = prep_variables(num_trials, infra_params)
    model_params = prep_variables(num_trials, model_params)
    
    return num_trials, model_params, infra_params, independent_var

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("setting", help="Options: distributed, single, both")
    parser.add_argument("exp", help="Options: batchsize, num_worker, num_ps, num_machines")
    args = parser.parse_args()

    num_workers_list = [16]
    num_machines_list = [1,2,4,8,16]
    num_ps_list = [1,2,3,4]
    machine_type = ['p2.8xlarge']

    all_lines = []
    #Should always be set to number of experiments + 1 colors
    plt.gca().set_color_cycle(['red', 'green', 'blue', 'yellow','black', 'purple', 'orange'])

    #Plot the distributed cases
    for num_machines in num_machines_list:
        exp_type = 'num_ps'
        num_trials, model_params, infra_params, independent_var = get_exp_params(exp_type, num_machines=[num_machines], num_ps=num_ps_list, num_workers=num_workers_list)
        assert len(independent_var) == num_trials

        all_RTT = model_distributed(num_trials, model_params, infra_params)[0]
        line = plot.plot_single(all_RTT, independent_var, plot_label='{} machines'.format(num_machines))
        all_lines.append(line)

    #Plot the single machine case
    exp_type = 'num_ps'
    num_trials, model_params, infra_params, independent_var = get_exp_params(exp_type,num_machines=[1], num_ps=num_ps_list, num_workers=num_workers_list)
    all_RTT = model_single(num_trials, model_params, infra_params)[0]
    line = plot.plot_single(all_RTT, independent_var, plot_label='Single Machine')
    all_lines.append(line)

    font = {'family':'serif','serif':['Times']}
    plt.title('Iteration Time', fontname="Times New Roman", size=20)
    plt.ylabel('Time/Iteration in seconds', fontname="Times New Roman", size=16)
    plt.xlabel('Number of PS', fontname="Times New Roman", size=16)
    plt.legend(handles=all_lines)
    plt.grid()
    plt.show()


    
    
    
    
