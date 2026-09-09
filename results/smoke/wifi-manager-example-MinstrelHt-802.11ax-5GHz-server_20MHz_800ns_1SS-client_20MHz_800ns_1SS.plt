set terminal postscript eps color enh "Times-BoldItalic"
set output "wifi-manager-example-MinstrelHt-802.11ax-5GHz-server_20MHz_800ns_1SS-client_20MHz_800ns_1SS.eps"
set title "Results for 802.11ax-5GHz with MinstrelHt\nserver: width=20MHz GI=800ns nss=1\nclient: width=20MHz GI=800ns nss=1"
set xlabel "SNR (dB)"
set ylabel "Rate (Mb/s)"
set xrange [0:60]
set yrange [0:160]
set key top left
plot "-"  title "802.11ax-5GHz-rate selected" with lines, "-"  title "802.11ax-5GHz-observed" with lines
55 143.382
53 143.382
51 143.382
49 143.382
47 143.382
45 143.382
43 143.382
41 143.382
39 143.382
37 143.382
35 143.382
33 129.044
31 109.688
29 73.125
27 81.25
25 86.0294
23 86.0294
21 86.0294
19 73.125
17 48.75
15 48.75
13 48.75
11 73.125
9 21.9375
7 21.9375
e
55 112.23
53 128.729
51 129.417
49 128.385
47 128.614
45 128.483
43 128.582
41 128.451
39 128.532
37 128.385
35 126.747
33 101.908
31 48.1362
29 43.0244
27 74.3834
25 78.1025
23 78.9873
21 78.8562
19 58.3598
17 15.7778
15 44.4334
13 43.1391
11 8.5033
9 13.6643
7 19.5625
e
