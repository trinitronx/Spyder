#!/usr/bin/python

AB="/usr/sbin/ab"
REPEAT=200

import sys, os

def do_benchmark (target_url, requests=1):
	"Run ab, return percentile results"
	os.system (AB+" -e ab.data.tmp -n "+str(requests)
	               +" "+target_url+">/dev/null 2>&1")
	f = file ("ab.data.tmp")
	l = [float(s.split(",")[1]) for s in f.readlines()[1:]]
	f.close()
	return l
	# os.system ("rm -f ab.data.tmp")

urls = sys.stdin.readlines()
s = 0
for u in urls:
	u = u.strip()
	results = do_benchmark (u, requests=REPEAT)
	print u,":", results[95]
	s += results[95]
print "Total: ", s

