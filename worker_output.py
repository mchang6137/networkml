import sys

output = [x.strip() for x in sys.stdin.readlines()]

step_98_index = -1
for i, line in enumerate(output):
  if '98, loss = ' in line:
    step_98_index = i
    break

assert(step_98_index > 0)

real_output = output[step_98_index:]

timestamp = -1
for line in real_output:
  if 'Send data with estimated' in line:
    timestamp = int(line.split(' ')[0])
    break

assert(timestamp > 0)

with open('vgg_output.txt', 'w') as f:
  f.write('Worker Output:\n')
  for line in real_output:
    f.write(line + '\n')
  f.write('Parameter Server Timestamp:', timestamp, '\n')



