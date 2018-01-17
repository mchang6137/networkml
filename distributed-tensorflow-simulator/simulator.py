import sys
import argparse
from sim import Simulation

def vary_workers_exp(args):
    num_workers = [2,4,8,12]
    num_ps = [2,4,8]

    for workers in num_workers:
	for ps in num_ps:
            args.num_workers = workers
            args.num_ps = ps
            
            print '{} ps, {} wk, with multicast'.format(ps, workers)
            args.use_multicast = 1
            sim = Simulation()
            sim.Setup(args)
            sim.Run()

            
            print '{} ps, {} wk, with no multicast'.format(ps, workers)
            args.use_multicast = 0
            sim = Simulation()
            sim.Setup(args)
            sim.Run()
            
            
def Main (args):
    parser = argparse.ArgumentParser(description="Simulator Arguments", fromfile_prefix_chars='@')
    parser.add_argument(
        "trace_base_dir",
        type=str,
        action="store",
        help="base directory for filename")
    parser.add_argument(
        "json",
        type=str,
        action="store",
        help=".json filename for parameter mappings")
    parser.add_argument(
        "--step_num",
        dest="step_num",
        type=int,
        action="store",
        default=10)
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
        "--topology",
        dest="topology",
        type=str,
        action="store",
        default="")
    args = parser.parse_args()
    if not args.trace_base_dir.endswith(".csv") or not args.json.endswith(".json"):
        print "The trace is supposed to be a file ending with .csv and a parameter mapping ending with .json"
    if args.latency_distribution != "none" and args.latency_distribution != "uniform" and args.latency_distribution != "standard":
        print "Unknown distribution {}, defaulting to none".format(args.latency_distribution)
        args.latency_distribution = "none"
    if args.latency == 0 and args.latency_distribution != "none" :
        print "Cannot have a latency distribution with zero latency"
    if args.latency_distribution != "none" and not args.latency_std :
        print "Cannot have a latency distribution without variance"
    if args.topology == 'none':
        print 'Defaulting to in-rack or across racks based on args.in_rack'

    vary_workers_exp(args)
    
    #sim = Simulation()
    #sim.Setup(args)
    #sim.Run()

if __name__ == "__main__":
    Main(sys.argv[1:])
