import numpy as np
import time
import os

def collect():
  s = []
  with open("/tmp/tf_run/worker0.log") as f:
    for l in f:
      #INFO:tensorflow:Worker 0: 2017-04-15 00:14:43.948375: step 19, loss = 12.85(17.0 examples/sec; 1.888  sec/batch)
      #2017-04-15 03:57:55.735478: step 0, loss = 13.09 (2.1 examples/sec; 15.070 sec/batch)
      try:
        if l.endswith("sec/batch)\n"):
          a = l.split(" ")
          #print l
          if a[4] == "step" and int(a[5].replace(",","")) > 40:
            s.append(float(a[10]))
        elif a[2] == "step" and int(a[3].replace(",","")) > 40:
            s.append(float(a[9]))
      except Exception as e:
          print "Err %s" % e, l
  return [np.mean(s), np.std(s)]

def run(cmd):
  print cmd
  os.system(cmd)

r = collect()
r_str = "%s %s %s" % (time.time(), r[0], r[1])
print r_str
run("echo \"%s\" >> result.txt" % r_str)
