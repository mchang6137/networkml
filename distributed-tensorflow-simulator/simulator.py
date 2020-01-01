import sys
import argparse
import csv
import os
import glob

from .sim import Simulation
from .dom_simulations import *

def check_csv(args):
    results_file = './dom_results/' + args.model_name + '/maxparamsize.csv'
    file_exists = os.path.isfile(results_file)
    if not file_exists:
        return False
    f = open(results_file, 'r')
    f.seek(0)
    reader = csv.DictReader(f)
    for row in reader:
        if int(row['num_workers']) == args.num_workers and (int(row['num_ps']) == args.num_ps or args.horovod) \
                and int(row['use_multicast']) == args.use_multicast \
                and int(row['in_network_computation']) == args.in_network_computation \
                and int(row['horovod']) == args.horovod and float(row['worker_send_rate']) == args.worker_send_rate \
                and int(row['butterfly']) == args.butterfly and float(row['message_size']) == args.message_size \
                and int(row['step_num']) == args.step_num and int(row['striping']) == args.striping \
                and int(row['multi_step']) == args.multi_step and float(row['max_param_size']) == args.max_param_size \
                and int(row['optimal_param_distribution']) == args.optimal_param_distribution \
                and float(row['gpu_speedup']) == args.gpu_speedup and float(row['iteration_time']) > 0.0:
            f.close()
            return True
    f.close()
    return False

def write_to_csv(args, finish_time, worker_receive_times):
    args_dict = vars(args)
    results_file = './dom_results/' + args.model_name + '/maxparamsize'
    # if args_dict['optimal_param_distribution'] == 1:
    #     results_file = results_file + '_even'
    # elif args_dict['optimal_param_distribution'] == 0:
    #     results_file = results_file + '_uneven'
    # if args_dict['striping'] == 1:
    #     results_file = results_file + '_striping'
    # elif args_dict['striping'] == 0:
    #     results_file = results_file + '_nostriping'
    results_file = results_file + '.csv'
    #results_file = './dom_results/{}/results.csv'.format(args.model_name)
    file_exists = os.path.isfile(results_file)
    try:
        os.makedirs(os.path.dirname(results_file))
    except OSError as e:
        pass
    
    #args_dict = vars(args)
    args_dict['iteration_time'] = finish_time
    args_dict['worker_receive_time'] = worker_receive_times
    headers = list(args_dict.keys())
    headers.sort()
    #print args_dict
    with open(results_file, 'a') as out:
        writer = csv.DictWriter(out, delimiter=',', lineterminator='\n',fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        #print 'For {}, an iteration time of {} was calculated'.format(args.model_name, finish_time)
        print('For {}, an iteration time of {} was recorded'.format(args.model_name, args_dict['iteration_time']))
        writer.writerow(args_dict)

def update_csvs(args):
    # this one needs a comment....
    # for x in os.walk(orig_tracename_basedir):
    #   for y in glob.glob(os.path.join(x[0], '*_{step_num}.csv'):
    #       yield y
    # os.walk yields a 3-tuple of [root, subdirectories, files]
    # glob is regex for filenames
    csvs = [z for (root, subdirectories, files) in os.walk("dom_results")
            for y in subdirectories
            for z in glob.glob(os.path.join(root, y, '*.csv'))]
    for csv in csvs:
        print(csv)
        try:
            update_csv(args, csv)
        except ValueError as ve:
            continue

def update_csv(args, csv_file):
    args_dict = vars(args)
    tempfilename = os.path.splitext(csv_file)[0] + '.bak'
    try:
        os.remove(tempfilename)  # delete any existing temp file
    except OSError:
        pass
    os.rename(csv_file, tempfilename)

    # create a temporary dictionary from the input file
    with open(tempfilename, mode='rb') as infile:
        reader = csv.DictReader(infile)
        infile.seek(0)
        temp_dict = [row for row in reader]

    if len(temp_dict) == 0:
        print("no items found???")
        return

    args_dict['iteration_time'] = 0.0
    args_dict['worker_receive_time'] = 0.0
    headers = list(args_dict.keys())
    headers.sort()

    # create updated version of file
    with open(csv_file, mode='wb') as outfile:
        writer = csv.DictWriter(outfile, delimiter=',', lineterminator='\n', fieldnames=headers)
        writer.writeheader()
        for item in temp_dict:
            if float(item['iteration_time']) <= 0.0:
                continue
            for key in headers:
                if key not in item:
                    item[key] = args_dict[key]
            writer.writerow(item)

    os.remove(tempfilename)  # delete backed-up original

def vary_worker_step_time(args):
    num_workers = [2,4,8,12]
    num_ps = [1,2,4,8]
    step_range = [x for x in range(10,50)]
    for step_num in step_range:
        args.step_num = step_num
        vary_workers_exp(args, num_workers=num_workers, num_ps=num_ps)

def Main (args):
    parser = argparse.ArgumentParser(description="Simulator Arguments", fromfile_prefix_chars='@')
    parser.add_argument(
        "trace_base_dir",
        type=str,
        action="store",
        default="csv/",
        help="base directory for filename")
    parser.add_argument(
        "distribution_trace_base_dir",
        type=str,
        action="store",
        default="distribution_csv/",
        help="base directory for ps distribution csv filename")
    parser.add_argument(
        "json",
        type=str,
        action="store",
        default="json/",
        help=".json filename for parameter mappings")
    parser.add_argument(
        "--fwd_pass_time",
        dest="fwd_pass_time",
        type=float,
        action="store",
        default=0)
    parser.add_argument(
        "--step_num",
        dest="step_num",
        type=int,
        action="store",
        default=10)
    parser.add_argument(
        "--gpu_speedup",
        dest="gpu_speedup",
        type=float,
        action="store",
        default=1.0)
    # latency takes the form of --latency 2 --latency-distribution standard --latency-std 1
    # or --latency 2 --latency-distribution uniform --latency-std 1
    # or --latency 2
    # depending on the desired latency distribution
    parser.add_argument(
        "--latency",
        dest="latency",
        type=float,
        action="store",
        default=0)
    parser.add_argument(
        "--latency-distribution",
        dest="latency_distribution",
        type=str,
        action="store",
        default="none",
        help="distribution curve for latency. acceptable values are uniform, standard, and none")
    parser.add_argument(
        "--latency-std",
        dest="latency_std",
        type=float,
        action="store",
        default=0,
        help="standard deviation for latency. in the case of uniform distribution, the difference between the middle and top values")
    """parser.add_argument(
        "--bandwidth",
        dest="bandwidth",
        type=float,
        action="store",
        default=-1)"""
    parser.add_argument(
        "--optimal_param_distribution",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--ps-send-rate",
        dest="ps_send_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--worker-send-rate",
        dest="worker_send_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--tor-send-rate",
        dest="tor_send_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--global-switch-send-rate",
        dest="gswitch_send_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--ps-recv-rate",
        dest="ps_recv_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--worker-recv-rate",
        dest="worker_recv_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--tor-recv-rate",
        dest="tor_recv_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--global-switch-recv-rate",
        dest="gswitch_recv_rate",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--ps-inbuffer-size",
        dest="ps_inbuffer_size",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--worker-inbuffer-size",
        dest="worker_inbuffer_size",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--tor-inbuffer-size",
        dest="tor_inbuffer_size",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--global-switch-inbuffer-size",
        dest="gswitch_inbuffer_size",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--num-global-switches",
        dest="num_gswitches",
        type=int,
        action="store",
        default=1)
    parser.add_argument(
        "--timeout",
        dest="timeout",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--MTU",
        dest="MTU",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--message-size",
        dest="message_size",
        type=float,
        action="store",
        default=-1)
    parser.add_argument(
        "--input-as-bytes",
        dest="inputs_as_bytes",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--gradient-size",
        dest="gradient_size",
        type=float,
        action="store",
        default=0,
        help="size of the gradient to be distributed by the ps; only used in json mode")
    parser.add_argument(
        "--multicast",
        dest="use_multicast",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--in-network-computation",
        dest="in_network_computation",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--num_workers",
        dest='num_workers',
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--num_ps",
        dest='num_ps',
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--on_same_rack",
        dest='on_same_rack',
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--fat_tree",
        dest='fat_tree',
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--striping",
        dest='striping',
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--topology",
        dest="topology",
        type=str,
        action="store",
        default="")
    parser.add_argument(
        "--model_name",
        dest="model_name",
        type=str,
        action="store",
        default="")
    parser.add_argument(
        "--horovod",
        dest="horovod",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--scattercast",
        dest="scattercast",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--butterfly",
        dest="butterfly",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--real_distribution",
        dest="real_distribution",
        type=int,
        action="store",
        default=0)
    parser.add_argument(
        "--first-pass-as-bytes",
        dest="forward_pass_as_bytes",
        type=int,
        action="store",
        default=1)
    parser.add_argument(
        "--max-param-size",
        dest="max_param_size",
        type=float,
        action="store",
        default=-1.0)
    parser.add_argument(
        "--multi-step",
        dest="multi_step",
        type=int,
        action="store",
        default=1)
    parser.add_argument(
        "--verbosity",
        dest="verbosity",
        type=int,
        action="store",
        default=1)
    
    args = parser.parse_args()
    #if not args.trace_base_dir.endswith(".csv") or not args.json.endswith(".json"):
        #print "The trace is supposed to be a file ending with .csv and a parameter mapping ending with .json"
    if args.latency_distribution != "none" and args.latency_distribution != "uniform" and args.latency_distribution != "standard":
        print("Unknown distribution {}, defaulting to none".format(args.latency_distribution))
        args.latency_distribution = "none"
    if args.latency == 0 and args.latency_distribution != "none" :
        print("Cannot have a latency distribution with zero latency")
    if args.latency_distribution != "none" and not args.latency_std :
        print("Cannot have a latency distribution without variance")
    if args.topology == 'none':
        print('Defaulting to in-rack or across racks based on args.in_rack')

    # Set the arguments based on the model name
    if args.trace_base_dir == 'csv/':
        args.trace_base_dir += args.model_name  + '/'
    if args.distribution_trace_base_dir == 'distribution_csv/':
        args.distribution_trace_base_dir += args.model_name  + '/'
    if args.json == 'json/':
        args.json += '{}_param_ps_assignment.json'.format(args.model_name)
    #update_csvs(args)
    #args.striping = 0
    #vary_model_and_steps(args)
    #args.striping = 1
    vary_model_and_steps(args)
    #vary_bandwidths(args)
    #for i in range(100):
    #sim = Simulation()
    #sim.Setup(args)
    #a,b = sim.Run()
    # if a > 0.6 or a < 0.550:
    #     print(a)
    #vary_model_and_steps(args)
    
if __name__ == "__main__":
    Main(sys.argv[1:])
