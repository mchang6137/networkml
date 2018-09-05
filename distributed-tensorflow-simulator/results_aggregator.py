import sys
import csv

results = []

def Main(args):
    for model_name in ['vgg16', 'resnet-200', 'resnet-101', 'inception-v3']:
        results_file = './dom_results/' + model_name + '/messaging.csv'
        f = open(results_file, 'r')
        reader = csv.reader(f)
        for num_workers in [32]:
            for bandwidth in [10.0, 25.0, 50.0, 100.0]:
                for message_size in [1,2,4,8,16,32,64,128,256,512,1024]:
                    message_size = float(message_size * 1000000)
                    horovod = 0
                    butterfly = 0
                    for num_ps in [1, 8]:
                        for multicast in [0, 1]:
                            for aggregation in [0, 1]:
                                average_step(f, num_workers, num_ps, multicast, aggregation, horovod, butterfly, bandwidth, message_size, model_name)
                    aggregation = 0
                    horovod = 1
                    for multicast in [0, 1]:
                        average_step(f, num_workers, num_ps, multicast, aggregation, horovod, butterfly, bandwidth, message_size, model_name)
                    multicast = 0
                    for butterfly in [1]:
                        average_step(f, num_workers, num_ps, multicast, aggregation, horovod, butterfly, bandwidth, message_size, model_name)
        f.close()
    f = open("dom_results/messaging.csv", "wb")
    writer = csv.writer(f, delimiter=",")
    for line in range(16):
        writer.writerow([results.pop(0) for _ in range(77)])
    f.close()

def average_step(f, num_workers, num_ps, multicast, aggregation, horovod, butterfly, bandwidth, message_size, model_name):
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
                and int(row['butterfly']) == butterfly and float(row['message_size']) == message_size:
                total += float(row['iteration_time'])
                count += 1
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
    elif multicast and aggregation:
        type = "num_ps {}, agg".format(num_ps)
    print '{}: num__workers {}, {:20s} bandwidth {} message size {} time {:.3f}, {}'.format( \
        model_name, num_workers, type, bandwidth, message_size, total / count if count != 0 else 0.0, count)
    if count != 0:
        results.append(total / count)
    else:
        results.append(0)

if __name__ == "__main__":
    Main(sys.argv[1:])