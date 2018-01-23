''' 
Sanity check the measurement data
'''

from find_async_variance import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_file')
    parser.add_argument('--num_ps')
    parser.add_argument('--max_wk')
    parser.add_argument('--model_name')
    parser.add_argument('--max_step')
    args = parser.parse_args()

    last_edge = aggregation_end_dict[args.model_name][0]
    small_time = []
    large_time = []

    cluster_times = {}
    debug = []
    for cluster_size in range(int(args.max_wk)+1):
        tracename_basedir = args.base_file + '{}/'.format(cluster_size)
        print tracename_basedir
        if os.path.exists(tracename_basedir) is False:
            continue

        cluster_times[cluster_size] = []

        for worker_id in range(cluster_size):
            for step_num in range(int(args.max_step)):
                worker_name = 'worker{}'.format(worker_id)
                wk_path = tracename_basedir + 'wk{}_{}.csv'.format(worker_id, step_num)
                
                if os.path.exists(wk_path) is False:
                    print 'There is no trace data for {} cluster, wkid {}, step_num {}'.format(cluster_size, worker_id, step_num)
                    continue
            
                trace = open(wk_path).readlines()
                for ev in trace:
                    if ev.startswith("//") or ev.startswith('"'):
                        continue
                    parts = ev.strip().split(',')
                    time = float(parts[0])
                    size = float(parts[1])
                    edgename = str(parts[2])
                    if cluster_size == 12 and worker_id == 11 and step_num == 49:
                        small_time.append(edgename)
                    elif cluster_size == 12 and worker_id == 2 and step_num == 23:
                        large_time.append(edgename)
                    if edgename == last_edge:
                        cluster_times[cluster_size].append(time)
                            
    for cluster_size in cluster_times:
        print 'Cluster size {}, {}'.format(cluster_size, sorted(cluster_times[cluster_size]))
        print 'mean: {}'.format(np.percentile(cluster_times[cluster_size],50))
        print 'std: {}'.format(np.std(cluster_times[cluster_size]))
