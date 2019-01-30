import sys
import csv

results = []

def Main(args):
    models = ['vgg16', 'resnet-200',
              'resnet-101', 'inception-v3']
    models = models[:]
    # models = ['inception-v3_extend_17x17_count_' + str(x) for x in [1, 5, 25, 125]] + \
    #                    ['inception-v3_extend_35x35_count_' + str(x) for x in [1, 5, 25, 125]]
    bandwidths = [10.0,25.0,50.0,75.0,100.0, 125.0]
    bandwidths = bandwidths[0:3]
    max_param_sizes = [-1.0]
    #message_sizes = [2 ** y for y in range(4, 14)] #[-1.0]
    message_sizes = [-1.0,16.0]
    num_workerses = [32]
    speedups = [1.0] #, 1.5, 2.0, 2.5, 3.0]
    for model_name in models:
        results_file = './dom_results/' + model_name + '/globalbarrier.csv'
        f = open(results_file, 'r')
        #reader = csv.reader(f)
        # num_workers = 32
        # num_ps = 1
        for speedup in speedups:
            for bandwidth in bandwidths:
                for max_param_size in max_param_sizes:
                    if max_param_size != -1:
                        max_param_size = float(max_param_size * 1000000)
                    for num_workers in num_workerses:
                        for multi_step in [1,3]:#,1]:
                            for striping in [1]:#,1]:
                                for message_size in message_sizes:
                                    if message_size != -1:
                                        message_size = float(message_size * 1000000)
                                    horovod = 0
                                    butterfly = 0
                                    for num_ps in [1]:
                                        for multicast in [1]:
                                            for aggregation in [1]:
                                                for optimal_distr in [0]:
                                                    average_step(f, num_workers, num_ps, multicast, aggregation, 0, 0, \
                                                                 bandwidth, message_size, max_param_size, striping, optimal_distr, \
                                                                 multi_step, model_name, speedup=speedup)
                                    aggregation = 0
                                    horovod = 1
                                    for multicast in [0]:
                                        pass
                                        average_step(f, num_workers, 1, multicast, 0, horovod, butterfly, \
                                                     bandwidth, message_size, max_param_size, striping, 0, \
                                                     multi_step, model_name, speedup=speedup)
                                    multicast = 0
                                    aggregation = 0
                                    for butterfly in [1]:
                                        pass
                                        average_step(f, num_workers, 1, 0, 0, 1, 1, \
                                                     bandwidth, message_size, max_param_size, striping, 0, \
                                                     multi_step, model_name, speedup=speedup)
        f.close()
    f = open("dom_results/temp.csv", "wb")
    writer = csv.writer(f, delimiter=",")
    # for x in range(4):
    #     writer.writerow([models[x], results.pop(0), results.pop(0)])
    # writer.writerow(["inception 17x17"])
    # writer.writerow(["", "default", "agg", "multicast", "multiagg", "horovod", "horovod+multicast", "butterfly"])
    # writer.writerow([1] + [results.pop(0) for _ in range(7)])
    # writer.writerow([5] + [results.pop(0) for _ in range(7)])
    # writer.writerow([25] + [results.pop(0) for _ in range(7)])
    # writer.writerow([125] + [results.pop(0) for _ in range(7)])
    # writer.writerow([])
    # writer.writerow(["inception 35x35"])
    # writer.writerow(["", "default", "agg", "multicast", "multiagg", "horovod", "horovod+multicast", "butterfly"])
    # writer.writerow([1] + [results.pop(0) for _ in range(7)])
    # writer.writerow([5] + [results.pop(0) for _ in range(7)])
    # writer.writerow([25] + [results.pop(0) for _ in range(7)])
    # writer.writerow([125] + [results.pop(0) for _ in range(7)])
    for line in range(len(models)):
        writer.writerow(["32workers"])
        writer.writerow([models[line], "multiagg", "butterfly", "horovod", "multiagg no barrier"])
        for line2 in range(len(bandwidths)):
            writer.writerow([bandwidths[line2]] + ['{:.3f}'.format(results.pop(0)) for _ in range(4)])
        writer.writerow([])
        #[results.pop(0) for _ in range(77)]
        #writer.writerow([results.pop(0) for _ in range(77)])
    f.close()

def average_step(f, num_workers, num_ps, multicast, aggregation, horovod, butterfly, bandwidth, message_size,
                 max_param_size, striping, optimal_distr, multi_step, model_name, speedup=1.0):
    f.seek(0)
    reader = csv.DictReader(f)
    count = 0
    total = 0
    for row in reader:
        try:
            if int(row['inputs_as_bytes']) != '1':
                pass
        except:
            print '{}'.format(row)
            exit(-1)
        try:
            if int(row['num_workers']) == num_workers and (int(row['num_ps']) == num_ps or horovod) \
                and int(row['use_multicast']) == multicast and int(row['in_network_computation']) == aggregation \
                and int(row['horovod']) == horovod and float(row['worker_send_rate']) == bandwidth \
                and int(row['butterfly']) == butterfly and float(row['message_size']) == message_size \
                and int(row['striping']) == striping and int(row['multi_step']) == multi_step \
                and float(row['max_param_size']) == max_param_size and float(row['optimal_param_distribution']) == optimal_distr \
                and float(row['gpu_speedup']) == speedup and int(row['step_num']) == 0:
                if float(row['iteration_time']) <= 0.0:
                    print "error, iteration time was {:.3f}".format(float(row['iteration_time']))
                #print (float(row['iteration_time']))
                total += float(row['iteration_time'])
                count += 1
               # print row
        except:
            pass
        #print row
    if count == 0:
        return
    type = "num_ps {}, default".format(num_ps)
    if butterfly:
        type = "butterfly"
    elif horovod and multicast:
        type = "horocast"
    elif horovod:
        type = "horovod"
    elif multicast and aggregation:
        type = "num_ps {}, multiagg".format(num_ps)
    elif multicast:
        type = "num_ps {}, multicast".format(num_ps)
    elif aggregation:
        type = "num_ps {}, agg".format(num_ps)
    print '{}: num__workers {}, {:20s} bandwidth {} message size {} striping {} optimal_distr {} time {:.3f}, {}'.format( \
        model_name, num_workers, type, bandwidth, message_size, striping, optimal_distr, total / count if count != 0 else 0.0, count)
    if multi_step == 1:
        total *= 2
    if count != 0:
        results.append(total / count)
    else:
        results.append(0)

if __name__ == "__main__":
    Main(sys.argv[1:])