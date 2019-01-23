import sys
import os
import csv
import json

results = []

def Main(args):
    models = ['inception-v3']
    step_nums = { 'inception-v3' :  [41,42,43,44,45,46,47],
        'resnet-200' : [41,42,43,44,45,46,47]}
    fc_layer = {'resnet-200' : 'resnet_v2_200/logits/weights/read',
                'inception-v3' : 'sync_token_q_Dequeue'}
    agg_workers = [2,4,8,12]
    dist_ps = [1]
    repeat_counts = [1,5,25,125]
    for repeat_count in repeat_counts:
        for model_name in models:
            addNs = {}
            json_file = "./json/%s_param_ps_assignment.json" % (model_name)
            for pses in dist_ps:
                for ps in range(pses):
                    dist_file = './distribution_csv/%s/%d/ps%d.csv' % (model_name, pses, ps)
                    #print(dist_file)
                    f = open(dist_file, 'r')
                    #reader = csv.DictReader(f)
                    lines = []
                    newblock = []
                    for row in f:
                        if row.startswith("//") or row.startswith('"'):
                            continue
                        line = row.strip().split(",")
                        lines.append(line)
                        if model_name == "inception-v3" and "mixed_17x17x768e" in line[2]:
                            line = line[:]
                            line[2] = line[2].replace("mixed_17x17x768e", "mixed_17x17x768f")
                            newblock.append(line)
                            if "weights/read" in line[2]:
                                idx = line[2].find("branch")
                                endidx = line[2].find("weights")
                                branchname = line[2][idx:endidx]
                                addNs[branchname] = line
                        elif model_name == "resnet-200" and "block2" in line[2]:
                            line = line[:]
                            line[2] = line[2].replace("block2", "block5")
                            newblock.append(line)
                            if "weights/read" in line[2]:
                                idx = line[2].find("unit_")
                                unitname = line[2][idx:idx+7]
                                idx = line[2].find("conv")
                                convname = line[2][idx:idx+5]
                                if "shortcut" in line[2]:
                                    convname = "shortcut"
                                if unitname not in addNs:
                                    addNs[unitname] = {}
                                addNs[unitname][convname] = line
                            #print(line)
                    #print("")
                    #print(len(newblock))
                    if repeat_count > 1:
                        count = len(newblock)
                        for x in range(1, repeat_count):
                            for y in range(count):
                                item = newblock[y][:]
                                item[2] = item[2] + '_' + str(x)
                                newblock.append(item)
                    for idx in range(len(lines)):
                        if lines[idx][2] == fc_layer[model_name]:
                            #print(idx)
                            lines[idx:idx] = newblock
                            break
                    #print("")
                    for idx in range(len(lines)):
                        lines[idx][0] = idx
                        #print(lines[idx])

                    dist_file_alt = dist_file.replace(model_name, model_name + "_alternate_" + str(repeat_count))
                    try:
                        os.makedirs(os.path.dirname(dist_file_alt))
                    except OSError as e:
                        pass
                    g = open(dist_file_alt, "wb")
                    writer = csv.writer(g, delimiter=",")
                    for item in lines:
                        writer.writerow(item)
                    g.close()
                    f.close()
                    for addN in addNs:
                        print addN
                        for item in addNs[addN]:
                            print "\t" + str(item)

            for workers in agg_workers:
                for worker in range(workers):
                    for step_num in step_nums[model_name]:
                        agg_file  = './csv/%s/%d/wk%d_%d.csv' % (model_name, workers, worker, step_num)
                        try:
                            f = open(agg_file, 'r')
                        except IOError as ioe:
                            continue
                        lines = []
                        newblock = []
                        blockstart = -1.0
                        for row in f:
                            if row.startswith("//") or row.startswith('"'):
                                continue
                            line = row.strip().split(",")
                            #print(line)
                            if model_name == "inception-v3":
                                if "mixed_17x17x768e" in line[2] and blockstart == -1.0:
                                    blockstart = float(line[0])
                                if "mixed_17x17x768e" in line[2]:
                                    line[2] = line[2].replace("mixed_17x17x768e", "mixed_17x17x768f")
                                    newblock.append(line)
                            elif model_name == "resnet-200":
                                if "block4" in line[2] and blockstart == -1.0:
                                    blockstart = float(line[0])
                                if "block2" in line[2]:
                                    line[2] = line[2].replace("block2", "block5")
                                    newblock.append(line)

                        basis = float(newblock[0][0])
                        addNBlock = []
                        control_dependencies = {}
                        # print(addNs)
                        # for addN in addNs:
                        #     print(addN)
                        #     for part in addNs[addN]:
                        #         print("\t" + part)
                        #         for part2 in addNs[addN][part]:
                        #             print("\t\t" + str(part2))
                        if model_name == "inception-v3":
                            for line in newblock:
                                line[0] = float(line[0]) - basis
                                branchname = ''
                                if "branch" in line[2]:
                                    idx = line[2].find("branch")
                                    endidx = line[2].find("Batch")
                                    branchname = line[2][idx:endidx]
                                if branchname == '':
                                    continue
                                else:
                                    addNBlock.append([line[0] + 6.0, addNs[branchname][1],
                                                      "gradients/addN" + branchname])

                        elif model_name == "resnet-200":
                            for line in newblock:
                                line[0] = float(line[0]) - basis
                                convname = ""
                                unitname = ""
                                if "unit_" in line[2]:
                                    idx = line[2].find("unit_")
                                    unitname = line[2][idx:idx+7]
                                if "conv" in line[2]:
                                    idx = line[2].find("conv")
                                    convname = line[2][idx:idx+5]
                                if "shortcut" in line[2]:
                                    convname = "shortcut"
                                    addNBlock.append(
                                        [line[0] + 1.0, addNs[unitname][convname][1], "gradients/addN" + unitname + convname])
                                elif convname == '':
                                    continue
                                elif convname == "conv3":
                                    addNBlock.append([line[0] + 1.0, addNs[unitname][convname][1], "gradients/addN" + unitname + convname])
                                else:
                                    if unitname not in control_dependencies:
                                        control_dependencies[unitname] = {}
                                    if convname not in control_dependencies[unitname]:
                                        control_dependencies[unitname][convname] = 1
                                    else:
                                        addNBlock.append([line[0] + 1.0, addNs[unitname][convname][1], "gradients/addN" + unitname + convname])
                        # for item in addNBlock:
                        #     print(item)
                        newblock.extend(addNBlock)
                        upperbound = max(float(item[0]) for item in newblock)
                        count = len(newblock)
                        if repeat_count > 1:
                            for x in range(1, repeat_count):
                                for y in range(count):
                                    item = newblock[y][:]
                                    item[0] = float(item[0]) + upperbound * x
                                    item[2] = item[2] + "_"  + str(x)
                                    newblock.append(item)
                        for item in newblock:
                            item[0] = float(item[0]) + blockstart

                        f.seek(0)
                        output = []

                        for row in f:
                            if row.startswith("//") or row.startswith('"'):
                                continue
                            line = row.strip().split(',')
                            if float(line[0]) >= blockstart:
                                line[0] = float(line[0]) + upperbound * repeat_count
                            output.append(line)
                            #print(line)
                        output.extend(newblock)
                        output.sort(key=lambda a: float(a[0]))
                        agg_file_alt = agg_file.replace(model_name, model_name + "_alternate_" + str(repeat_count))
                        try:
                            os.makedirs(os.path.dirname(agg_file_alt))
                        except OSError as e:
                            pass
                        g = open(agg_file_alt, "wb")
                        writer = csv.writer(g, delimiter=",")
                        for item in output:
                            writer.writerow(item)
                        g.close()
                        f.close()
                        if step_num == step_nums[model_name][0] and worker == 0 and workers == agg_workers[0]:
                            json_file_alt = json_file.replace(model_name, model_name + "_alternate_" + str(repeat_count))
                            jsf = open(json_file_alt, "wb")
                            jstuff = {}
                            jstuff["1"] = {}
                            jstuff["1"]["/job:ps/replica:0/task:0/device:CPU:0"] = []
                            for item in output:
                                newitem = [0, float(item[1]) / 8, {},
                                           "/job:worker/replica:0/task:1/device:GPU:0",
                                            "/job:ps/replica:0/task:0/device:CPU:0",
                                            item[2]]
                                jstuff["1"]["/job:ps/replica:0/task:0/device:CPU:0"].append(newitem)
                            jsf.write(json.dumps(jstuff))
                            jsf.close()


    # f = open("dom_results/maxparamsize.csv", "wb")
    # writer = csv.writer(f, delimiter=",")
    # for line in range(4):
    #     writer.writerow([])
    # f.close()

if __name__ == "__main__":
    Main(sys.argv[1:])
