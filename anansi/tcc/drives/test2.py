import subprocess
from time import sleep

for ii in range(100):
    print "LAUNCHING PROCESS",ii
    p = subprocess.Popen(["python","test.py"])
    sleep(5)
    print "KILLING PROCESS"
    p.terminate()
    p.wait()
    print 
    print
    print
