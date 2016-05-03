# parse-running-wheel

### sessions.py - version 0.3
Script to parse VitalView mouse volunary running wheel data and calculate running sessions (run phase followed by a rest phase) for each animal.

---

### Requires: 
- python 2.7
- tqdm
- argparse
- numpy
- pandas

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

1. Animal data   <cohort_name>_asc_summary.csv
2. Raw data      <cohort_name>_asc_rawdata.csv
3. Formatted     <cohort_name>_formatted.csv
4. Sessions      <animal>_sessions.csv

---

### Future additions
- Time Filtered - includes data > 18:01:00 of day 1 to 06:00:00 of day 3
- Sum Hourly - minute data is summed into hours per row
- Cumulative - data from each hour is compounded onto the previous"""))

---

### parseRunningWheelAsc.py 
Depreciated version. Can output hourly sum and cumilative sum but no session data.  Also does not use pandas. 