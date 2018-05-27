import sys
import csv

results = []

def Main(args):
    for model_name in ['vgg16', 'resnet-200', 'resnet-101', 'inception-v3']:
        results_file = './dom_results/' + model_name + '/horovodexp_uneven_striping.csv'
        f = open(results_file, 'r')
        reader = csv.reader(f)
        for num_workers in [32, 16, 8]:
            for bandwidth in [10, 25, 50, 100]:
                horovod = 0
                for num_ps in [1, 8]:
                    multicast = 0
                    aggregation = 0
                    average_step(f, num_workers, num_ps, multicast, aggregation, horovod, bandwidth, model_name)
                for num_ps in [1, 8]:
                    multicast = 1
                    for aggregation in [0, 1]:
                        average_step(f, num_workers, num_ps, multicast, aggregation, horovod, bandwidth, model_name)
                aggregation = 0
                horovod = 1
                for multicast in [0, 1]:
                    average_step(f, num_workers, num_ps, multicast, aggregation, horovod, bandwidth, model_name)
        f.close()
    f = open("dom_results/horovod.csv", "wb")
    writer = csv.writer(f, delimiter=";")
    for line in range(48):
        writer.writerow([results.pop(0) for _ in range(8)])
    f.close()

def average_step(f, num_workers, num_ps, multicast, aggregation, horovod, bandwidth, model_name):
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
                and int(row['horovod']) == horovod and int(row['worker_send_rate']) == bandwidth:
                total += float(row['iteration_time'])
                count += 1
        except:
            pass
        #print row
    print '{}: num__workers {}, num_ps {}, multicast {} aggregation {} horovod {} bandwidth {} time {:.3f}, {}'.format(model_name, num_workers, num_ps, \
        multicast, aggregation, horovod, bandwidth, total / count, count)
    if count != 0:
        results.append(total / count)
    else:
        results.append(0)

if __name__ == "__main__":
    Main(sys.argv[1:])