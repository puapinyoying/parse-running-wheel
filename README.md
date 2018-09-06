# parse-running-wheel
Updated 9/5/2018

### sessions.py - version 0.5.0
Script to parse VitalView mouse volunary running wheel data and calculate running sessions (run phase followed by a rest phase) for each animal.

Input data obtained using: 

- VitalView Activity & Data Viewer
- STARR Life Sciences Corp
- Version 1.3 

---

### Installation

1. Requirements **UPDATED** - Now requires Python 3
	- python==3.6.5
	- pandas==0.23.0
		+ Should automatically install numpy==1.14.3
	- argparse==1.1
	- matplotlib==2.2.2

2. [How to install Python 3](https://realpython.com/installing-python/)

3. [Install dependencies using pip](https://packaging.python.org/tutorials/installing-packages/#use-pip-for-installing)
```
pip install pandas==0.23.0
pip install argparse==1.1
pip install matplotlib==2.2.2
```

4. Or use [Anaconda by Continuum](https://www.anaconda.com/download/)
```
conda install pandas=0.23.0
conda install argparse=1.1
conda install matplotlib=2.2.2
```
	- More about [Conda package manager](https://conda.io/docs/user-guide/tasks/manage-pkgs.html)

---

### Usage

sessions.py [-h] [-v] input

`sessions.py` parses mouse running wheel data and calculates run and rest sessions.  

The program takes '.csv' data output from the Vitalview Software. The input file should have three levels of headers. From top to bottom. The header needs to be 'Channel Name:','Channel Group:' and 'Sensor Type:' 

**positional arguments**:
```bash
input          		File name and/or path to experiment_file.asc or .csv
```
**optional arguments**:
```bash
-S, --customStart	start at 'month/day/yeah hour:min' (e.g. 9/5/2018 15:35)
-E, --customEnd		end at 'month/day/yeah hour:min' (e.g. 9/7/2018 13:35)
-H, --customGrpByHr	group data by specified number of hours, can specify argument multiple times
-h, --help     		show this help message and exit
-v, --version  		show program's version number and exit
```

**The script will output a csv file for each of the following**:

| Data | Details | Output Filename |
| ---- | ------- | --------------- |
| Raw data | A copy of the raw data table | cohort_name_rawdata.csv |
| Formatted turns | Dataframe with formated headers and indexes, displays wheel turns data| cohort_name_formatted_turns.csv |
| Formatted distance | Same as above, but data converted to meters (turns * 0.361) | cohort_name_formatted_distance.csv |
| Selected distance | User selected time window of data defined by '-S' and '-E' arguments (subsequently used for the rest of the calculations), if custom start and end times were given | cohort_name_selected_distance.csv |
| Bin by hr | Distance data grouped by hour | cohort_name_bin_by_hour.csv |
| Bin by days | Distance data grouped by day| cohort_name_bin_by_day.csv |
| Bin by <X> hrs | Custom groupings by X hours, defined by -H argument | cohort_name_bin_by_<user_defined_hours>H.csv |
| Sessions | Run and rest sessions for each individual animal put into the animal_sessions folder | animalName_group_sessions.csv |
| Percent Run & rest | Calculate the percentages of each run vs rest for sessions | cohort_name_percentRunRest.csv |
| Graphs | See below | cohort_name_graphs.pdf |
  
The pdf of graphs contains:

- Total Running Distance By Day
- Percent Run and Percent Rest Per Animal
- Cumilative Sum Plot Binned By Hour
- Distance Histogram Binned By Hour

---

### Example command:

```bash
python sessions.py test-input.csv -S '8/21/2017 11:01' -E '8/23/2017 9:01' -H 4 -H 6 -H 12
```

- `-S '8/21/2017 11:01'` & `-E '8/23/2017 9:01'` 
	+ This defines when we should the start and end the calculations (skips first hour; maybe it was part of aclimation time). Basically, trucates the dataframe to fit this window. If a start or end time is not defined it will default to including all data from each end respenctively. (seen in "_selected_distance")

- `-H 4 -H 6 -H 12` 
	+ This tells the program to calculate and output three extra dataframes in 4, 6 and 12 hour groupings.
