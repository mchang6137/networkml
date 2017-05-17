#File to store the actual result from our experiments for the purposes of comparison
#Each function should return the results and error bars

def get_distributed_results(experiment_type, independent_var):
    mean_time = {}
    std_time = {}
    if experiment_type == 'batchsize':
        #Batch size results
        mean_time = {8: 2.355, 16: 2.627, 32: 2.647, 48: 3.288, 64: 3.66}
        std_time = {8: 0.1204, 16: 0.141, 32: 0.563, 48: 3.288, 64: 0.088}
    elif experiment_type == 'worker':
        #Worker Number results
        mean_time =  {1: 2.046, 2: 2.1624, 8: 2.65}
        std_time =   {1: 0, 2:0.1148, 8: 2.6488}
    else:
        print 'invalid experiment type'
        exit()

    actual_mean = []
    actual_std = []
    for variable in independent_var:
        try:
            actual_mean.append(mean_time[variable])
            actual_std.append(std_time[variable])
        except KeyError:
            actual_mean.append(0)
            actual_std.append(0)

    return actual_mean, actual_std
            


def get_single_results(experiment_type, independent_var):
    mean_time = {}
    std_time = {}

    if experiment_type == 'batchsize':
        #Batch size results
        mean_time = {8: 0.692, 16: 1.054, 32: 1.9291, 48: 2.5505, 64: 3.368}
        std_time = {8: 0.042, 16: 0.0458, 32: 0.0694, 48: 0.053, 64: 0.0548}
    elif experiment_type == 'worker':
        #Worker results
        mean_time = {1: 1.426, 2: 1.6384, 4: 1.721, 8: 1.9291}
        std_time = {1: 0, 2: 0, 4:0, 8: 1.9291}
    else:
        print 'invalid experiment type!'
        exit()

    actual_mean = []
    actual_std = []
    
    for	variable in independent_var:
	try:
            actual_mean.append(mean_time[variable])
            actual_std.append(std_time[variable])
	except KeyError:
            actual_mean.append(0)
            actual_std.append(0)

    return actual_mean,	actual_std


