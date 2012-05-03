#!/bin/bash

i=0

for f in $(cat $1); do
    let i++
#    ab -n 1000 -c 50 -g /tmp/$i.gnuplot "$f" | tee -a /tmp/ab.log;
    cat >/tmp/gnuplot.p<<EOM
# output as png image
set terminal png

# save file to "out.png"
set output "$i.png"

# graph title
set title "ab -n 1000 -c 50 \n $f"

# nicer aspect ratio for image size
set size 1,0.7

# y-axis grid
set grid y

# x-axis label
set xlabel "request"

# y-axis label
set ylabel "response time (ms)"

# plot data from "out.dat" using column 9 with smooth sbezier lines
# and title of "nodejs" for the given data
plot "$i.gnuplot" using 9 smooth sbezier with lines title "${f%%\/.*}"
EOM

( cd /tmp/ && gnuplot /tmp/gnuplot.p )

done
