# p4_parameter_server
distributed tensorflow simulator commandline arguments/usage

python simulator.py @args/*model*.args

Where args is a file containing arguments
Not all arguments are necessarily required, but it is recommended to keep all arguments to stay aware of internal values
The csv and json files are necessary at this time

**csv/*model*.csv**
csv file in the form of delta-time, size, edge name for the edges sent from a worker after Global Barrier 2
**json/*model*.json**
json file containing mappings from parameter server to contained parameters
**--latency=0.00001**
latency across an individual link. for reasons, cannot be zero or below
**--latency-distribution=none**
distribution curve for latency, can be none, uniform, or standard
**--latency-std=1**
standard deviation for a standard distribution of latency. in the case of uniform distribution, the difference between the middle and top values
**--ps-send-rate=8**
**--ps-recv-rate=8**
**--worker-send-rate=2.5**
**--worker-recv-rate=2.5**
**--tor-send-rate=25**
**--tor-recv-rate=25**
**--global-switch-send-rate=4**
**--global-switch-recv-rate=5**
bandwidths for various entities **in gigabits**
**--num-global-switches=4**
number of global switches when using multiple racks. uses random switches on precomputed paths on a src-dest basis. multicast forces switch zero
**--gradient-size=0**
size of global gradient to be distributied by each parameter server. if zero, each ps counts up the parameters assigned to it from the json
**--MTU=12000**
MTU in bits for packet size. lower MTUs better approximate behaviour in the network do to an error regarding queueing
**--input-as-bytes=0**
0 or 1 flag for converting input values from bytes to bits. the json assumes the inputs are bytes for now
**--multicast=0**
0 or 1 flag for using multicast in the distribution step
**--topology=[[worker0, worker1], [/job:ps/replica:0/task:0/device:CPU:0, /job:ps/replica:0/task:1/device:CPU:0]]**
topology in the form of inner brackets indicating a rack, ie. this topology has a rack with two workers and a rack with two parameter servers