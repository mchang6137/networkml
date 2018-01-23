import csv
import argparse
import os.path
import re

import matplotlib.pylab as plt

'''
Keys in csv
inputs_as_bytes,gswitch_recv_rate,tor_inbuffer_size,tor_send_rate,latency,gswitch_inbuffer_size,num_gswitches,use_multicast,json,worker_send_rate,worker_inbuffer_size,step_num,num_ps,worker_recv_rate,num_workers,iteration_time,MTU,latency_std,ps_send_rate,on_same_rack,topology,gswitch_send_rate,tor_recv_rate,ps_inbuffer_size,gradient_size,trace_base_dir,timeout,ps_recv_rate,latency_distribution
'''

# Compares the importance of distribution and aggregation
# Optimization 1: Distribution + Aggregation
# Assuming even split of parameters 
# Optimization 2: (Distribution + Aggregation) vs. Just Distribution
# Optimization 3: (Distribution + Aggregation) vs Just Aggregation 
def plot_compare_agg_distr(result_csv_dict, model_name, filter_bandwidth=10, use_even_split=1):
    baseline = {}
    just_multicast = {}
    just_agg = {}
    multicast_and_agg = {}
    
    for result in result_csv_dict:
        bandwidth = float(result['ps_send_rate'])
        num_workers = int(result['num_workers'])
        num_ps = int(result['num_ps'])
        use_multicast = int(result['use_multicast'])
        iteration_time = float(result['iteration_time'])
        is_optimal = int(result['optimal_param_distribution'])
        use_agg = int(result['in_network_computation'])
        result_model_name = result['model_name']

        # Apply filters
        if result_model_name != model_name:
            continue
        if is_optimal != use_even_split:
            continue
        if bandwidth != filter_bandwidth:
            continue

        # Gather data based on the optimizations
        if use_agg == 0 and use_multicast == 0:
            update_dict(baseline, num_ps, num_workers, iteration_time)

        if use_agg == 1 and use_multicast == 0:
            update_dict(just_agg, num_ps, num_workers, iteration_time)

        if use_agg == 0 and use_multicast == 1:
            update_dict(just_multicast, num_ps, num_workers, iteration_time)

        if use_agg == 1 and use_multicast == 1:
            update_dict(multicast_and_agg, num_ps, num_workers, iteration_time)

    print multicast_and_agg[8][12]
    print just_agg[8][12]
    exit()

    both_over_baseline = {}
    multicast_over_baseline = {}
    distribution_over_baseline = {}

    multicast_over_baseline  = dict_ratio(baseline, just_multicast)
    agg_over_baseline = dict_ratio(baseline, just_agg)
    multicast_agg_over_baseline = dict_ratio(baseline, multicast_and_agg)
    multicast_agg_over_agg = dict_ratio(just_agg, multicast_and_agg)
    multicast_agg_over_multicast = dict_ratio(just_multicast, multicast_and_agg)
    multicast_over_agg = dict_ratio(just_agg, just_multicast)

    plot_dict(multicast_over_baseline, model_name, 'Multicast over baseline')
    plot_dict(agg_over_baseline, model_name, 'Aggregation over baseline')
    plot_dict(multicast_over_agg, model_name, 'Multicast over aggregation')
    plot_dict(multicast_agg_over_baseline, model_name, 'Mutlicast + Agg over baseline')
    plot_dict(multicast_agg_over_agg, model_name, 'Multicast + Agg over Just Agg')
    plot_dict(multicast_agg_over_multicast, model_name, 'Multicast + aggregation over just Multicast')

def update_dict(dict1, num_ps, num_workers, iteration_time):
    if num_ps not in dict1:
        dict1[num_ps] = {}
    if num_workers in dict1[num_ps]:
        print 'extra csv points'
        print dict1[num_ps][num_workers]
        print iteration_time
    dict1[num_ps][num_workers] = iteration_time
    
# Assumes num_ps -> num_workers
# Dict 1 should be the baseline, dict2 the result with te improvement
def dict_ratio(dict_1, dict_2):
    result = {}
    for num_ps in dict_2:
        result[num_ps] = {}
        for num_workers in dict_2[num_ps]:
            time1 = dict_1[num_ps][num_workers]
            time2 = dict_2[num_ps][num_workers]

            result[num_ps][num_workers] = 100.0 * (time1 - time2) / float(time1)

    return result

def plot_dict(dict1, model_name, title):
    all_lines = []
    for num_ps in dict1:
        results = dict1[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('{}:{}'.format(model_name, title))
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement Percentage')
    plt.show()

# Used to plot experiment 1: varying number of workers and parameter servers
def plot_vary_wk_vary_ps(result_csv_dict, model_name):
    ps_worker_time = {}
    multicast_ps_worker_time = {}
    in_network_ps_worker_time = {}
    both_ps_worker_time = {}
    for result in result_csv_dict:
        num_workers = int(result['num_workers'])
        num_ps = int(result['num_ps'])
        is_multicast = int(result['use_multicast'])
        in_network = int(result['in_network_computation'])
        if is_multicast == 0 and in_network == 0:
            iteration_time = float(result['iteration_time'])
            
            if num_ps not in ps_worker_time:
                ps_worker_time[num_ps] = {}
            ps_worker_time[num_ps][num_workers] = iteration_time
        elif is_multicast == 1 and in_network == 0:
            iteration_time = float(result['iteration_time'])
            
            if num_ps not in multicast_ps_worker_time:
                multicast_ps_worker_time[num_ps] = {}
            multicast_ps_worker_time[num_ps][num_workers] = iteration_time
        elif is_multicast == 0 and in_network == 1:
            iteration_time = float(result['iteration_time'])
            
            if num_ps not in in_network_ps_worker_time:
                in_network_ps_worker_time[num_ps] = {}
            in_network_ps_worker_time[num_ps][num_workers] = iteration_time
        elif is_multicast == 1 and in_network == 1:
            iteration_time = float(result['iteration_time'])
            
            if num_ps not in both_ps_worker_time:
                both_ps_worker_time[num_ps] = {}
            both_ps_worker_time[num_ps][num_workers] = iteration_time

    percent_improvement = {}
    for num_ps in in_network_ps_worker_time:
        percent_improvement[num_ps] = {}
        for num_workers in in_network_ps_worker_time[num_ps]:
            in_network_multicast_time = in_network_ps_worker_time[num_ps][num_workers]
            no_multicast_time = ps_worker_time[num_ps][num_workers]
            percent_improvement[num_ps][num_workers] = 100.0 * (no_multicast_time - in_network_multicast_time)/float(no_multicast_time) 

    alt_percent_improvement = {}
    for num_ps in both_ps_worker_time:
        alt_percent_improvement[num_ps] = {}
        for num_workers in both_ps_worker_time[num_ps]:
            both_time = both_ps_worker_time[num_ps][num_workers]
            multicast_time = multicast_ps_worker_time[num_ps][num_workers]
            alt_percent_improvement[num_ps][num_workers] = 100.0 * (multicast_time - both_time)/float(multicast_time)

    all_lines = []
    for num_ps in both_ps_worker_time:
        results = both_ps_worker_time[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, '-.', label='{} ps, Both'.format(num_ps))
        all_lines.append(distr_line)

    for num_ps in in_network_ps_worker_time:
        results = in_network_ps_worker_time[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, '--', label='{} ps, In-Network'.format(num_ps))
        all_lines.append(distr_line)

    for num_ps in multicast_ps_worker_time:
        results = multicast_ps_worker_time[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps, Multicast'.format(num_ps))
        all_lines.append(distr_line)

    for	num_ps in ps_worker_time:
	results = ps_worker_time[num_ps]
	distr_lists = sorted(results.items())
	x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y,label='{} ps, Unicast'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Performance subject to different workers and parameter servers')
    plt.xlabel('Number of Workers')
    plt.ylabel('Iteration time')
    plt.show()

    all_lines_alt = []
    for num_ps in percent_improvement:
        results = percent_improvement[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps, Unicast'.format(num_ps))
        all_lines_alt.append(distr_line)

    for num_ps in alt_percent_improvement:
        results = alt_percent_improvement[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, '-', label='{} ps, Multicast'.format(num_ps))
        all_lines_alt.append(distr_line)

    plt.legend(handles=all_lines_alt)
    plt.title('Percent improvement of using Multicast')
    plt.xlabel('Number of workers')
    plt.ylabel('Percent Improvement in Performance with Multicast')
    plt.show()

def plot_step_variance(result_csv_dict, model_name, use_multicast):
    step_worker_ps_time = {}
    config_average = {}
    
    for result in result_csv_dict:
        num_workers = int(result['num_workers'])
        num_ps = int(result['num_ps'])
        config = (num_ps, num_workers)
        step_num = int(result['step_num'])
        iteration_time = float(result['iteration_time'])
        multicast_used = int(result['use_multicast'])

        if multicast_used != use_multicast:
            continue

        if step_num not in step_worker_ps_time:
            step_worker_ps_time[step_num] = {}

        if config not in config_average:
            config_average[config] = []

        step_worker_ps_time[step_num][config] = iteration_time
        config_average[config].append(iteration_time)

    import numpy as np
    config_cv = {}
    for config in config_average:
        print '{}, median = {}, 90th = {}, 10th = {}'.format(config,
                                                             np.percentile(config_average[config], 50),
                                                             np.percentile(config_average[config], 80),
                                                             np.percentile(config_average[config], 20)

        )

        config_cv[config] = np.std(config_average[config]) / np.mean(config_average[config])

    return config_cv

def compare_results(result1_dict, result2_dict, title, result1_legend, result2_legend):
    revised_result1 = {}
    revised_result2 = {}
    # Break down into the right form
    for config in result1_dict:
        num_ps = config[0]
        num_workers = config[1]
        if num_ps not in revised_result1:
            revised_result1[num_ps] = {}
        revised_result1[num_ps][num_workers] = result1_dict[config]

    for	config in result2_dict:
	num_ps = config[0]
	num_workers = config[1]
        if num_ps not in revised_result2:
	    revised_result2[num_ps] = {}
	revised_result2[num_ps][num_workers] = result2_dict[config]

    all_lines = []
    for num_ps in revised_result1:
        results = revised_result1[num_ps]
	distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, '.', label='{} ps {}'.format(num_ps, result1_legend))
        all_lines.append(distr_line)

    for num_ps in revised_result2:
        results = revised_result2[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, 'x', label='{} ps {}'.format(num_ps, result2_legend))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('{}'.format(title))
    plt.xlabel('Number of workers')
    plt.ylabel('Coefficient of variance')
    plt.show()
    
def plot_vary_parameter_aggregation(result_csv_dict, model_name, filter_bandwidth=10):
    # Baseline is performance with one parameter server
    # num_workers -> performance
    baseline_performance = {}

    # Optimization 1: Only use multiple parameter servers, NO multicast
    # num_ps -> num_worker -> iteration time
    multips_time = {}

    # Optimization 2: Only use multiple parameter servers, NO multicast
    # with correct parameter distributions
    # num_ps -> num_workers -> iteration_time
    multips_even_split_time = {}

    # Optimization 3: Multiple parameter servers, MULTICAST
    agg_uneven_split_time = {}

    # Optimization 4: Multiple parameter servers, MULTICAST, optimal
    agg_even_split_time = {}

    # Baseline is performance with one parameter server
    # num_workers -> performance
    for result in result_csv_dict:
        # Assume symmetric bandwidth
        bandwidth = float(result['ps_send_rate'])
        if bandwidth != filter_bandwidth:
            continue
        
        num_workers = int(result['num_workers'])
        num_ps = int(result['num_ps'])

        use_multicast = int(result['use_multicast'])
        if use_multicast == 1:
            continue
        iteration_time = float(result['iteration_time'])
        is_optimal = int(result['optimal_param_distribution'])
        use_agg = int(result['in_network_computation'])

        if num_ps == 1 and use_agg == 0 and is_optimal == 0:
            baseline_performance[num_workers] = iteration_time

        # Optimization 1
        if use_agg == 0 and is_optimal == 0:
            if num_ps not in multips_time:
                multips_time[num_ps] = {}
            if num_workers in multips_time[num_ps]:
                print 'extra csv points'
                #if iteration_time != multips_time[num_ps][num_workers]:
                #    exit()
            multips_time[num_ps][num_workers] = iteration_time

        # Optimization 2
        if use_agg == 0 and is_optimal == 1:
            if num_ps not in multips_even_split_time:
                multips_even_split_time[num_ps] = {}
            if num_workers in multips_even_split_time[num_ps]:
                print 'Extra csv points'
                #if iteration_time != multips_even_split_time[num_ps][num_workers]:
                #    exit()
            multips_even_split_time[num_ps][num_workers] = iteration_time

        # Optimization 3
        if use_agg == 1 and is_optimal == 0:
            if num_ps not in agg_uneven_split_time:
                agg_uneven_split_time[num_ps] = {}
            if num_workers in agg_uneven_split_time[num_ps]:
                print 'Extra csv points'
                #if agg_uneven_split_time[num_ps][num_workers] != iteration_time:
                #    exit()
            agg_uneven_split_time[num_ps][num_workers] = iteration_time

        # Optimization 4
        if use_agg == 1 and is_optimal == 1:
            if num_ps not in agg_even_split_time:
                agg_even_split_time[num_ps] = {}
            if num_workers in agg_even_split_time[num_ps]:
                print 'Extra csv points'
                #if agg_even_split_time[num_ps][num_workers] != iteration_time:
                #    exit()
            agg_even_split_time[num_ps][num_workers] = iteration_time

    percent_improvement_over_baseline = {}
    percent_improvement_over_even = {}
    unicast_even_vs_unicast_uneven = {}
    agg_even_vs_agg_uneven = {}

    for num_ps in agg_even_split_time:
        percent_improvement_over_baseline[num_ps] = {}
        percent_improvement_over_even[num_ps] = {}
        unicast_even_vs_unicast_uneven[num_ps] = {}
        agg_even_vs_agg_uneven[num_ps] = {}
        for num_workers in agg_even_split_time[num_ps]:
            baseline_time = baseline_performance[num_workers]
            agg_even = agg_even_split_time[num_ps][num_workers]
            unicast_even = multips_even_split_time[num_ps][num_workers]
            unicast_uneven = multips_time[num_ps][num_workers]
            agg_uneven = agg_uneven_split_time[num_ps][num_workers]

            unicast_even_vs_unicast_uneven[num_ps][num_workers] = 100.0 * (unicast_uneven - unicast_even) / float(unicast_uneven)
            percent_improvement_over_even[num_ps][num_workers] = 100.0 * (unicast_even - agg_even) / float(unicast_even)
            percent_improvement_over_baseline[num_ps][num_workers] = 100.0 * (baseline_time - agg_even) / float(baseline_time)
            agg_even_vs_agg_uneven[num_ps][num_workers] = 100.0 * (agg_uneven - agg_even) / float(agg_uneven)

    all_lines = []
    for num_ps in agg_even_vs_agg_uneven:
        results = agg_even_vs_agg_uneven[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Aggregation Unevenly split (baseline) vs Aggregation Evenly split')
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement in performance')
    plt.show()

    all_lines = []
    for num_ps in unicast_even_vs_unicast_uneven:
        results = unicast_even_vs_unicast_uneven[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Unicast Evenly split vs unicast unevenly split (baseline)')
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement in performance')
    plt.show()

    all_lines = []
    for num_ps in percent_improvement_over_even:
        results = percent_improvement_over_even[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Aggregatopm evenly split vs unicast evenly split (baseline)')
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement in performance')
    plt.show()

    for num_ps in percent_improvement_over_baseline:
        results = percent_improvement_over_baseline[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, '--', label='{} parameter servers'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Benefit of using Aggregation + evenly split parameters')
    plt.xlabel('Number of workers')
    plt.ylabel('Percent Improvement')
    plt.show()
    

def plot_vary_parameter_distribution(result_csv_dict, model_name, filter_bandwidth=10):
    # Baseline is performance with one parameter server
    # num_workers -> performance
    baseline_performance = {}

    # Optimization 1: Only use multiple parameter servers, NO multicast
    # num_ps -> num_worker -> iteration time
    multips_time = {}

    # Optimization 2: Only use multiple parameter servers, NO multicast
    # with correct parameter distributions
    # num_ps -> num_workers -> iteration_time
    multips_even_split_time = {}

    # Optimization 3: Multiple parameter servers, MULTICAST
    multicast_uneven_split_time = {}

    # Optimization 4: Multiple parameter servers, MULTICAST, optimal
    multicast_even_split_time = {}

    # Baseline is performance with one parameter server
    # num_workers -> performance
    for result in result_csv_dict:
        bandwidth = float(result['ps_send_rate'])
        if filter_bandwidth != bandwidth:
            continue
        use_agg = int(result['in_network_computation'])
        if use_agg == 1:
            continue

        num_workers = int(result['num_workers'])
        num_ps = int(result['num_ps'])
        use_multicast = int(result['use_multicast'])
        iteration_time = float(result['iteration_time'])
        is_optimal = int(result['optimal_param_distribution'])

        if num_ps == 1 and use_multicast == 0 and is_optimal == 0:
            baseline_performance[num_workers] = iteration_time

        # Optimization 1
        if use_multicast == 0 and is_optimal == 0:
            if num_ps not in multips_time:
                multips_time[num_ps] = {}
            if num_workers in multips_time[num_ps]:
                print 'extra csv points'
                #if iteration_time != multips_time[num_ps][num_workers]:
                #    exit()
            multips_time[num_ps][num_workers] = iteration_time

        # Optimization 2
        if use_multicast == 0 and is_optimal == 1:
            if num_ps not in multips_even_split_time:
                multips_even_split_time[num_ps] = {}
            if num_workers in multips_even_split_time[num_ps]:
                print 'Extra csv points'
                #if iteration_time != multips_even_split_time[num_ps][num_workers]:
                #    exit()
            multips_even_split_time[num_ps][num_workers] = iteration_time

        # Optimization 3
        if use_multicast == 1 and is_optimal == 0:
            if num_ps not in multicast_uneven_split_time:
                multicast_uneven_split_time[num_ps] = {}
            if num_workers in multicast_uneven_split_time[num_ps]:
                print 'Extra csv points'
                #if multicast_uneven_split_time[num_ps][num_workers] != iteration_time:
                #    exit()
            multicast_uneven_split_time[num_ps][num_workers] = iteration_time

        # Optimization 4
        if use_multicast == 1 and is_optimal == 1:
            if num_ps not in multicast_even_split_time:
                multicast_even_split_time[num_ps] = {}
            if num_workers in multicast_even_split_time[num_ps]:
                print 'Extra csv points'
                #if multicast_even_split_time[num_ps][num_workers] != iteration_time:
                #    exit()
            multicast_even_split_time[num_ps][num_workers] = iteration_time

    percent_improvement_over_baseline = {}
    percent_improvement_over_even = {}
    unicast_even_vs_unicast_uneven = {}
    multicast_even_vs_multicast_uneven = {}
    
    for num_ps in multicast_even_split_time:
        percent_improvement_over_baseline[num_ps] = {}
        percent_improvement_over_even[num_ps] = {}
        unicast_even_vs_unicast_uneven[num_ps] = {}
        multicast_even_vs_multicast_uneven[num_ps] = {}
        for num_workers in multicast_even_split_time[num_ps]:
            baseline_time = baseline_performance[num_workers]
            multicast_even = multicast_even_split_time[num_ps][num_workers]
            unicast_even = multips_even_split_time[num_ps][num_workers]
            unicast_uneven = multips_time[num_ps][num_workers]
            multicast_uneven = multicast_uneven_split_time[num_ps][num_workers]

            unicast_even_vs_unicast_uneven[num_ps][num_workers] = 100.0 * (unicast_uneven - unicast_even) / float(unicast_uneven)
            percent_improvement_over_even[num_ps][num_workers] = 100.0 * (unicast_even - multicast_even) / float(unicast_even)
            percent_improvement_over_baseline[num_ps][num_workers] = 100.0 * (baseline_time - multicast_even) / float(baseline_time)
            multicast_even_vs_multicast_uneven[num_ps][num_workers] = 100.0 * (multicast_uneven - multicast_even) / float(multicast_uneven)

    all_lines = []
    for num_ps in multicast_even_vs_multicast_uneven:
        results = multicast_even_vs_multicast_uneven[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Multicast Unevenly split (baseline) vs Multicast Evenly split')
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement in performance')
    plt.show()

    
    all_lines = []
    for num_ps in unicast_even_vs_unicast_uneven:
        results = unicast_even_vs_unicast_uneven[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Unicast Evenly split vs unicast unevenly split (baseline)')
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement in performance')
    plt.show()

    all_lines = []
    for num_ps in percent_improvement_over_even:
        results = percent_improvement_over_even[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, ':', label='{} ps'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Multicast evenly split vs unicast evenly split (baseline)')
    plt.xlabel('Number of workers')
    plt.ylabel('Improvement in performance')
    plt.show()

    for num_ps in percent_improvement_over_baseline:
        results = percent_improvement_over_baseline[num_ps]
        distr_lists = sorted(results.items())
        x,y = zip(*distr_lists)
        distr_line, = plt.plot(x,y, '--', label='{} parameter servers'.format(num_ps))
        all_lines.append(distr_line)

    plt.legend(handles=all_lines)
    plt.title('Benefit of using multicast + evenly split parameters')
    plt.xlabel('Number of workers')
    plt.ylabel('Percent Improvement')
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--result_csv')
    parser.add_argument('--model_name')
    parser.add_argument('--filter_bandwidth')
    parser.add_argument('--experiment_name')
    args = parser.parse_args()
    
    file_exists = os.path.isfile(args.result_csv)
    if not file_exists:
        print 'This data file does not exist'
        exit()

    result_csv_dict = list(csv.DictReader(open(args.result_csv)))
    if args.experiment_name == 'ps_wk_vary':
        plot_vary_wk_vary_ps(result_csv_dict, args.model_name)
    if args.experiment_name == 'distr_wk_ps':
        plot_vary_parameter_distribution(result_csv_dict, args.model_name, float(args.filter_bandwidth))
    if args.experiment_name == 'agg_wk_ps':
        plot_vary_parameter_aggregation(result_csv_dict, args.model_name, float(args.filter_bandwidth))
    if args.experiment_name == 'multicast_agg_compare':
        plot_compare_agg_distr(result_csv_dict, args.model_name, float(args.filter_bandwidth), use_even_split=1)
    if args.experiment_name == 'step_variance':
        print 'Without multicast'
        unicast_cv = plot_step_variance(result_csv_dict, args.model_name, use_multicast=0)
        print 'With Multicast'
        multicast_cv = plot_step_variance(result_csv_dict, args.model_name, use_multicast=1)
        compare_results(unicast_cv, multicast_cv,
                        'Performance variation with and without multicast', 'Unicast', 'Multicast')
        
