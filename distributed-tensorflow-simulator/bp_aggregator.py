import os
import glob


def average(arr):
    if len(arr) == 0:
        print("ERROR: length of arr is zero")
        return 0.0
    return sum(arr) / len(arr)

trace_dir = "./csv"
(root, subdirs, file) = os.walk(trace_dir).next()
for subdir in sorted(subdirs):
    times = []
    sizes = []
    slowest = 0.0
    for (subroot, subsds, _) in os.walk(os.path.join(root,subdir)):
        for subsd in subsds:
            for csv in glob.glob(os.path.join(subroot, subsd, '*.csv')):
                trace = open(csv).readlines()
                total = 0.0
                if subdir == 'resnet-101' and float(trace[-1].strip().split(',')[0]) > 400:
                    continue
                if subdir == 'resnet-200' and float(trace[-1].strip().split(',')[0]) > 500:
                    continue
                if subdir == 'resnet-200_alternate' and float(trace[-1].strip().split(',')[0]) > 700:
                    continue
                if subdir == 'inception-v3' and float(trace[-1].strip().split(',')[0]) > 400:
                    continue
                if subdir == 'inception-v3_alternate' and float(trace[-1].strip().split(',')[0]) > 500:
                    continue
                if subdir.startswith('inception-v3_extend_'):
                    addition = subdir.find('count_') + 6
                    num = int(subdir[addition:])
                    if  float(trace[-1].strip().split(',')[0]) > 400 + num * 60:
                        continue
                if subdir == 'vgg16' and float(trace[-1].strip().split(',')[0]) > 40:
                    continue
                times.append(float(trace[-1].strip().split(',')[0]))
                if times[-1] > slowest:
                    slowest = times[-1]
                for row in trace:
                    if row.startswith("//") or row.startswith('"'):
                        continue
                    total += float(row.strip().split(',')[1])
                sizes.append(total)
    if len(times) == 0 or len(sizes) == 0:
        print("model {}: failed with times {} and sizes {}".format(subdir, len(times), len(sizes)))
        continue

    fw_pass_time_dict = {'inception-v3': 0.176,
                         'inception-v3_alternate': 0.194,
                         'dummy_model': 1.0,
                         'resnet-200': 0.357,
                         'resnet-200_alternate': 0.400,
                         'vgg16': 0.169,
                         'resnet-101': 0.176}

    if "_extend" not in subdir:
        fp_time = fw_pass_time_dict[subdir]
    else:
        fp_time = fw_pass_time_dict[subdir[:subdir.find("_extend")]]
        rest = subdir[subdir.find("count_") + 6:]
        fp_time += 0.008 * int(rest)
    average_time = average(times) / 1000.0
    average_size = average(sizes)
    average_agg = average_size / (10 * 10 ** 9)
    simple_divergence = average_time / average_agg / 5

    multiagg_time = average_agg + fp_time + max(average_agg, average_time)
    butterfly_time = fp_time + max(average_agg * 5, average_time)
    real_divergence = average_time / (average_agg * 4)
    print(("model {}:\n\taverage bp time {}" +
            "\n\tworst bp time {}"
            "\n\taverage send time {}" +
            "\n\tsimple divergence >= {}" +
            "\n\tfull multiagg time {}" +
            "\n\tfull butterfly time {}" +
            "\n\tbetter divergence >= {}").format(\
                subdir, \
                average_time, \
                slowest, \
                average_agg, \
                simple_divergence, \
                multiagg_time, \
                butterfly_time, \
                real_divergence))
