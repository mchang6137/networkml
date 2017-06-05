import csv
import argparse
import experiment_setting as exp
import actual_results as actual
import matplotlib.pylab as plt
import numpy as np
import RTT_calculation as rtt

#Fully Isolated Graphs go in here
def plot_ps_to_workerpermachine(num_workers_list, num_machines_list, num_ps_list, machine_type):
    all_lines = []
    #Plot the distributed cases
    for num_machines in num_machines_list:
        exp_type = 'num_ps'
        num_trials, model_params, infra_params, independent_var = rtt.get_exp_params(exp_type, num_machines=[num_machines], num_ps=num_ps_list, num_workers=num_workers_list)
        assert len(independent_var) == num_trials

        all_RTT = rtt.model_distributed(num_trials, model_params, infra_params)[0]
	line = plot_single(all_RTT, independent_var, plot_label='{} machines'.format(num_machines))
	all_lines.append(line)

    #Plot the single machine case
    exp_type = 'num_ps'
    num_trials, model_params, infra_params, independent_var = rtt.get_exp_params(exp_type,num_machines=[1], num_ps=num_ps_list, num_workers=num_workers_list)
    all_RTT = rtt.model_single(num_trials, model_params, infra_params)[0]
    line = plot_single(all_RTT, independent_var, plot_label='Single Machine')
    all_lines.append(line)

    font = {'family':'serif','serif':['Times']}
    plt.title('Iteration Time', fontname="Times New Roman", size=20)
    plt.ylabel('Time/Iteration in seconds', fontname="Times New Roman", size=16)
    plt.xlabel('Number of PS', fontname="Times New Roman", size=16)
    plt.legend(handles=all_lines)
    plt.grid()
    plt.show()

#Plot the parameter servers 
def plot_ps_to_workerpermachine_stackbar(num_workers_list, num_machines_list, num_ps_list, machine_type):
    fig = plt.figure()
    num_subplots = len(num_machines_list) + 2

    axis = 0
    while axis ** 2 < num_subplots:
        axis += 1
    
    plot_index = 1
    #Plot the distributed cases
    for num_machines in num_machines_list:
        subplotnum = axis*100 + axis*10 + plot_index
        plot_index += 1

        subplot = fig.add_subplot(subplotnum)
        exp_type = 'num_ps'
        num_trials, model_params, infra_params, independent_var = rtt.get_exp_params(exp_type, num_machines=[num_machines], num_ps=num_ps_list, num_workers=num_workers_list)
        assert len(independent_var) == num_trials

        all_RTT,trial_agg,trial_dist,trial_dequeue,trial_fp = rtt.model_distributed(num_trials, model_params, infra_params)
        plot_stackbar(trial_agg,trial_dist,trial_dequeue,trial_fp,independent_var,subplot, subplot_title='Distributed - {} Machines'.format(num_machines))

    #Plot the single machine case
    exp_type = 'num_ps'
    num_trials, model_params, infra_params, independent_var = rtt.get_exp_params(exp_type,num_machines=[1], num_ps=num_ps_list, num_workers=num_workers_list)
    all_RTT,trial_agg,trial_dist,trial_dequeue,trial_fp = rtt.model_single(num_trials, model_params, infra_params)
    subplotnum = axis*100 + axis*10 + plot_index
    subplot = fig.add_subplot(subplotnum)
    plot_stackbar(trial_agg,trial_dist,trial_dequeue,trial_fp,independent_var,subplot, plot_legend=True,subplot_title='Single Machine')

    plt.xlabel('Number of PS', fontname="Times New Roman", size=16)
    plt.grid()
    plt.show()
    
def plot_stackbar(agg_RTT, dist_RTT, dequeue_time, fp_pass, independent_var, subplot=None, subplot_title='gimme title', plot_legend=False):
    assert len(agg_RTT) == len(independent_var)

    width = 0.5

    p1 = subplot.bar(independent_var, agg_RTT, width, color='blue')
    p2 = subplot.bar(independent_var, dist_RTT, width, bottom=agg_RTT, color='red')
    p3 = subplot.bar(independent_var, dequeue_time, width, bottom=np.array(dist_RTT) + np.array(agg_RTT), color='green')
    p4 = subplot.bar(independent_var, fp_pass, width, bottom=np.array(dist_RTT) + np.array(agg_RTT) + np.array(dequeue_time), color='purple')
    subplot.set_title(subplot_title)

    if plot_legend:
        plt.legend((p1[0], p2[0], p3[0], p4[0]), ('Aggregation', 'Distribution', 'Dequeue time', 'Forward pass'), loc="upper left")

    return p1[0], p2[0], p3[0], p4[0]

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
    if setting_str == 'single':
        actual_mean, actual_std = actual.get_single_results(experiment_str, independent_var)
    elif setting_str == 'distributed':
        actual_mean, actual_std = actual.get_distributed_results(experiment_str, independent_var)

    font = {'family':'serif','serif':['Times']}
    actual_line_color = '#990000'
    prediction_line_color = 'black'
    error_length = 1

    line1, = plt.plot(*zip(*sorted(prediction_result.items())), color=prediction_line_color, label='Predicted RTT')
    line2, = plt.plot(independent_var, actual_mean, lw=3, color=actual_line_color, label='Actual RTT')
    plt.legend(handles=[line1, line2])
    plt.errorbar(independent_var, actual_mean, actual_std, lw=error_length, color=actual_line_color)
    plt.grid()

#Plots the result for a single experiment
#single_result: independent_var -> iteration time prediction
#Does not show() so this needs to be called at a later time
def plot_single(single_result, independent_var_list, line_color='black', plot_label='Single Machine'):
    prediction_result = {}
    for x in range(len(single_result)):
        prediction_result[independent_var_list[x]] = single_result[x]

    print single_result
    print prediction_result

    font = {'family':'serif','serif':['Times']}

    line, = plt.plot(*zip(*sorted(prediction_result.items())), label=plot_label)
    return line

