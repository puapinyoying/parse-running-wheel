# parse-running-wheel

### sessions.py - version 0.4.1
Script to parse VitalView mouse volunary running wheel data and calculate running sessions (run phase followed by a rest phase) for each animal.

---

### Requires: 
- python 2.7
- argparse
- numpy
- pandas* v0.17.1
- matplotlib

*Currently program breaks with version 0.18. Please use pandas version v0.17.1 for now*


---

**usage:** sessions.py [-h] [-v] input

`sessions.py` parses mouse running wheel data that has been output into a ASCII file directly obtained from the Vitalview Software. The input file should have two headers. The first will be the the over all file header that says 'Experiment Logfile:' followed by the date. Second, the data header below in comma delimited format (csv)

Option to use with csv files that have the mouse summary data removed. However, the data must still be in triplicate columns.

**positional arguments**:
  input          File name and/or path to experiment_file.asc or .csv

**optional arguments**:
  -h, --help     show this help message and exit
  -v, --version  show program's version number and exit

**The script will output a csv file for each of the following**:

1. Animal data              <cohort_name>_asc_summary.csv
2. Raw data                 <cohort_name>_asc_rawdata.csv
3. Formatted                <cohort_name>_formatted.csv
4. Bin by hour              <cohort_name>_bin_by_hour.csv
5. Cumulative sum by hr     <cohort_name>_cumsum_by_hour.csv
6. Sum distance by day      <cohort_name>_sum_dist_by_day.csv
7. Sessions                 <animal>_sessions.csv
8. Percent Run & rest       <cohort_name>_percentRunRest.csv
9. Graphs                   <cohort_name>_graphs.pdf

The pdf of graphs contains
- Total Running Distance By Day
- Percent Run and Percent Rest Per Animal
- Cumilative Sum Plot Binned By Hour
- Distance Histogram Binned By Hour

---

### Future additions
- Filter by time
- Fix bugs with pandas v0.18

---

### parseRunningWheelAsc.py 
Depreciated version.
