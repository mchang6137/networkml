import csv
import argparse
import experiment_setting as exp
import actual_results as actual
import matplotlib.pylab as plt
import numpy as np

#Fully Isolated Graphs go in here

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

