#! /usr/bin/env python

# prw_pandas

# Import libraries for data analysis

import re
import os
import sys
import tqdm
import argparse
import textwrap
import numpy as np
import pandas as pd
import matplotlib as plt
from datetime import datetime
from pandas import Series, DataFrame
from matplotlib.backends.backend_pdf import PdfPages


# Regular Expressions and static (unchanging) variables 
SAMPLE_NAME_REGEXP = r'([\w \/]+) Turns Data'
FILE_NAME_REGEXP = r'(.+)\..+'
HEADER_STRING = 'Experiment Logfile:'


 # how to deal with NAs: fillna with zero, fill forward fill back
 # I think backfill is best option, with limit 1, or fill zeros for more
 # conservative take


def formatRawDf(rawDf):

    nullRows = rawDf.iloc[:,2::3].isnull().sum()
    print "Mouse", 'Num Missing Values'
    print nullRows
    print '\nWarning: The above null values were back filled'
    # print '\nWarning: The above null values were replaced with zeros'
    
    # back fill
    rawFill = rawDf.fillna(method='bfill', limit=1)
    #print rawFill.iloc[8183,:]

    #rawFill = rawDf.fillna(0) # fill with zeros

    # Create a column with date and time merged
    dtIndex = rawFill.iloc[:,0] + ' ' + rawFill.iloc[:,1]

    # Convert the date into datetime objects

    dtIndex2 = []

    for i in dtIndex:
        temp = datetime.strptime(i, '%m/%d/%y %H:%M:%S')
        dtIndex2.append(temp)

    # Set this new datetime list as the index
    df = rawFill  # copy the raw data frame with NAs filled
    df.index = dtIndex2

    # Filter out redundant date and time columns for each sample using slicing
    # iloc means go by index location (titles were too long to deal with)
    # slicing notation first ':' means we want all rows
    # '2' means start at column 3, ':' means go through all columns,
    # '3' means go in steps of 3 (jump over 2 columns so we can get just data)
    df1 = df.iloc[:, 2::3]

    # Add a column header
    df1.columns.name = 'condition'

    # multiply all turns data by 0.361 to convert turns to meters
    df2 = df1 * 0.361

    # Select the column names so we can rename them
    colNames = df2.columns

    # Create a regular expression formula
    REG_EXP = r'^([\w\/\s\-]+) Turns Data'

    sampleName = re.search(REG_EXP, colNames[0])

    # Loop through whole column list and rename everything
    newColNames = []

    for name in colNames:
        temp = re.search(REG_EXP, name)
        newName = temp.group(1)
        newColNames.append(newName)

    # Sub the old column names for the new ones
    df2.columns = newColNames
    df2.columns.name = 'condition'  # got erased, add back

    return df2, nullRows  # returns formatted dataframe and number of rows with null values


# Function used to create a sessions dataframe from formated dataframe
def calcSessions(df):
    colList = df.columns

    newDf = DataFrame()

    # iterate over list of column names and use to access data from each column
    for pos, col in enumerate(colList):

        # reset the dateTime index (place index back as a data column)
        resetCol = df.iloc[:,pos].reset_index()
        row_iter = resetCol.itertuples() # create iterator for accessing row data

        # make some variables
        phaseMins = 0
        phaseDist = 0
        phaseStartTime = ''
        phaseEndTime = ''
        sessionNum = 0
        phaseCount = 0
        prevTime = ''
        currTime = ''
        prevDist = 0
        currDist= 0

        subjectList = []
        phaseList = []

        # iterate over each row in the column of data
        for rowNum, row in enumerate(row_iter):     
            currDist = row[2]
            currTime = row[1]

            # If the mouse is running
            if rowNum == 0:
                phaseStartTime = currTime
            
            if currDist > 0: 
                # If the previous distance value is zero and the current is not
                # then it is end of rest phase. write the 'rest' phase data to list   
                if (prevDist == 0) & (rowNum > 0):
                    phaseList.append(sessionNum)
                    phaseList.append('rest')
                    phaseList.append(phaseStartTime)
                    phaseEndTime = currTime
                    phaseList.append(phaseEndTime)
                    phaseList.append(phaseMins)
                    phaseList.append(0)
                    phaseList.append(0)

                    # clear old results
                    phaseMins = 0
                    phaseDist = 0
                    phaseStartTime = currTime
                    prevTime = currTime
                    prevDist = currDist

                    # Add new phase values
                    phaseMins += 1
                    phaseDist += currDist

                    # Add new session only after a rest phase
                    sessionNum += 1

                    # add to session list and clear phase list
                    subjectList.append(phaseList)
                    phaseList = []


                else:
                    # just keep adding to the phase data
                    phaseMins += 1
                    phaseDist += currDist
                    prevTime = currTime
                    prevDist = currDist

            else:
                # if distance value is currently zero and the previous was 
                # higher than zero, that means it reach the end of a run phase
                # write run phase data to list
                if (prevDist > 0):
                    phaseList.append(sessionNum)
                    phaseList.append('run')
                    phaseList.append(phaseStartTime)
                    phaseEndTime = currTime
                    phaseList.append(phaseEndTime)
                    phaseList.append(phaseMins)
                    phaseList.append(phaseDist)
                    avgVelocity = phaseDist/phaseMins
                    phaseList.append(avgVelocity)

                    # clear old results
                    phaseMins = 0
                    phaseDist = 0
                    phaseStartTime = currTime
                    prevTime = currTime
                    prevDist = currDist

                    # add new phase information
                    phaseMins += 1
                    phaseDist += currDist

                    # add to session list and clear phase list
                    subjectList.append(phaseList)
                    phaseList = []

                else:
                    phaseMins += 1
                    phaseDist += currDist
                    prevTime = currTime
                    prevDist = currDist

        # create the hierarchical column names and create a new data frame to
        # house the data
        subjCols = [[col]*7, ['session', 'phase', 'start','end','mins','distance(m)','avg_velocity(m/min)']]
        newCols = pd.MultiIndex.from_arrays(subjCols, names=['subjects', 'values'])
        sub_df = DataFrame(subjectList, columns=newCols)
        #print sub_df
        newDf = pd.concat([newDf, sub_df], axis=1)
        subjectList = []

    return newDf

# for use in parse phase ('trimming')
def rmUnpairedPhase(animalDf):
    trimmedAnimalDf = ''
    # Each animal has different # of sessions, so pandas places NAs to even
    # out the rows in the large dataframe. Need to remove Nas to get real number
    # of phases
    drpNaDf = animalDf[animalDf.mins.notnull()]
    #print drpNaDf.head() 
    phases = drpNaDf.phase  # get phase column data
    numPhases = len(phases)
    lastPhase = phases[numPhases-1]

    if (drpNaDf.phase[0] == 'rest'):
        if (drpNaDf.phase[numPhases-1] == 'run'):
            trimmedAnimalDf = drpNaDf.iloc[1:(numPhases-1),:]
            #print 'one', numPhases, len(trimmedAnimalDf.phase), lastPhase, len(animalDf.phase)
            return trimmedAnimalDf
        else:
            trimmedAnimalDf = drpNaDf.iloc[1:,:]
            #print 'two', numPhases, len(trimmedAnimalDf.phase), lastPhase, len(animalDf.phase)
            return trimmedAnimalDf
    elif (drpNaDf.phase[0] == 'run'): 
        if (drpNaDf.phase[numPhases-1] == 'run'):
            trimmedAnimalDf = drpNaDf.iloc[:(numPhases-1),:]
            #print 'three', numPhases, len(trimmedAnimalDf.phase), lastPhase, len(animalDf.phase)
            return trimmedAnimalDf
        else:
            trimmedAnimalDf = drpNaDf.iloc[:,:]
            #print 'four', numPhases, len(trimmedAnimalDf.phase), lastPhase, len(animalDf.phase)
            return trimmedAnimalDf
    else:
        print "five"

# for use in parse phase ('pruning')
def rmStartingRestOnly(animalDf):
    prunedAnimalDf = ''
    drpNaDf = animalDf[animalDf.mins.notnull()] 
    phases = drpNaDf.phase  # get phase column data
    numPhases = len(phases)
    lastPhase = phases[numPhases-1]

    if (drpNaDf.phase[0] == 'rest'):
        prunedAnimalDf = drpNaDf.iloc[1:,:]
        #print 'one', numPhases, lastPhase, len(animalDf.phase)
        return prunedAnimalDf

    else:
        prunedAnimalDf = drpNaDf.iloc[:,:]
        #print 'four', numPhases, lastPhase, len(animalDf.phase)
        return prunedAnimalDf

# for use in parse phase
def formatSurvival(runs, rests):

    runsSel = runs.iloc[:,1:6] # select most colums
    restsSel = rests.iloc[:,1:4] # leave out a few

    # combine cols into single dataframe
    d = pd.concat([runsSel,restsSel], axis=2) 
    
    # rename headers
    d.columns = ['run_start', 'run_end', 'run_mins', 'run_dist', 'avg_v', 'rest_start','rest_end', 'rest_min']
    d.columns.name = 'values'

    # Reset index to make independent of session number. Session numbers were zero based but some were trimmed
    # because they started in a rest phase. Therefore, some animals had their first session number starting with 1.
    # If not reset, can cause problems when trying to use the length to get_item by an index number
    d2 = d.reset_index()

    # get the total number of rows in the dataframe and get the last resting minute value
    rowNum = len(d2)
    lastRestMin = d2.rest_min[rowNum-1]

    # Create two new series to be put into the dataframe
    # run_obs is whether or not the last run phase was observed to completion (1) or if it was censored (0)
    # rest_obs is whether or not the last resting phase was observed to completion (1) or if it was censored (0)
    # censored meaning the run or rest was still going while the data collection stopped / was cut off
    run_obs = Series([1]*rowNum, name='run_obs') # fill default series assuming all were observed
    rest_obs = Series([1]*rowNum, name='rest_obs')

    # Modify series of observations based on last resting minute
    # If lastRestMin is missing data, then there was no rest phase for the last session (None). That also means
    # the last run phase did not complete. Therefore, the last run was not observed to completion (0).
    if pd.isnull(lastRestMin):
        run_obs[rowNum-1] = 0
        rest_obs[rowNum-1] = None
    
    # lastRestMin does contain values.  This means the last session's running phase was seen to completion
    # so we leave the last run_obs as a (1). However, the resting phase continued to the end of data collection.
    # Therefore the rest phase was not observed to completion (0)
    else:
        rest_obs[rowNum-1] = 0

    # combine the new observation series as columns in the previous dataframe & set the index back to session
    temp = pd.concat([d2,run_obs, rest_obs], axis=2)
    d3 = temp.set_index('session')
    
    return d3

# Take original session dataframe and split into runs only and rest only dfs
# Also calls rmUnpairedPhase() to remove a rest phases at the beginning or an
# run phase at the end of the df. Important for scatter plots (need same
# number of x & y coordinates)

def parsePhase(sessionDf):
    
    animalDict = {}
    
    animals = sessionDf.columns.levels[0]
    for animal in animals:
        
        # Original Session Data for current animal
        animalDf = sessionDf[animal]
        
        
        # Parse sessions into different phases for output
        tempRuns = animalDf[animalDf.phase == 'run']
        runs = tempRuns.set_index('session') # set the index to session instead
        
        tempRests = animalDf[animalDf.phase == 'rest']
        rests = tempRests.set_index('session')

        
        ### Trimm any starting rests or unfinished runs at the end for scatter plots if exist
        # (x & y must be equal length)
        trimAnimalDf = rmUnpairedPhase(animalDf)
        
        tempRuns = trimAnimalDf[trimAnimalDf.phase == 'run']
        trimRuns = tempRuns.set_index('session')
        
        tempRests = trimAnimalDf[trimAnimalDf.phase == 'rest']
        trimRests = tempRests.set_index('session')
        
        
        ### Prune just the starting rests if exist, for survival curve
        prunedAnimalDf = rmStartingRestOnly(animalDf)
        
        tempRuns = prunedAnimalDf[prunedAnimalDf.phase == 'run']
        prunedRuns = tempRuns.set_index('session')
        
        tempRests =  prunedAnimalDf[prunedAnimalDf.phase == 'rest']
        prunedRests = tempRests.set_index('session')
        
        
        ### Create dataframe for survival curves using pruned rests and runs
        survivalDf = formatSurvival(prunedRuns, prunedRests)
        
        cleanName = re.sub(r'[\/\+\s]', r'_', animal)
        
        
        animalDict.update({cleanName: [animalDf, runs, rests, trimAnimalDf, trimRuns, trimRests, 
                                       prunedAnimalDf, prunedRuns, prunedRests, survivalDf]})

    return animalDict

def outputAllToFile(rawDf, formattedDf, nullRows, animalDict, cohortName):
    currWorkingDir = os.getcwd()
    newDirPath = os.path.join(currWorkingDir, cohortName)

    if not os.path.exists(newDirPath):
        os.makedirs(newDirPath)

    # output main formatted data frame
    rawDf.to_csv(os.path.join(newDirPath, cohortName +'_raw_data.csv'))
    nullRows.to_csv(os.path.join(newDirPath, cohortName +'_num_null.csv'))
    formattedDf.to_csv(os.path.join(newDirPath, cohortName +'_formatted.csv'))

    # see if you can output null rows along with raw data in future

    # Output session data frames
    for key in animalDict:
        # make a new folder for each animal
        animalDirPath = os.path.join(newDirPath, key)
        if not os.path.exists(animalDirPath):
            os.makedirs(animalDirPath)

        print "Outputting Tables for: ", key
        allDf = animalDict[key][0]
        runsDf = animalDict[key][1]
        restsDf = animalDict[key][2]

        # Orginal data
        allDf.to_csv(os.path.join(animalDirPath, key + '_sessions.csv'))
        runsDf.to_csv(os.path.join(animalDirPath, key + '_run_phases.csv'))
        restsDf.to_csv(os.path.join(animalDirPath, key + '_rest_phases.csv'))
        
        # Trimmed data - removes any starting rests or unfinished runs at the end
        # if exist.  Useful for for scatter plots (x & y must be equal length)
        allTrimDf = animalDict[key][3]
        trimRunsDf = animalDict[key][4]
        trimRestsDf = animalDict[key][5]

        allTrimDf.to_csv(os.path.join(animalDirPath, key + '_trim_sessions.csv'))
        trimRunsDf.to_csv(os.path.join(animalDirPath, key + '_trim_run_phases.csv'))
        trimRestsDf.to_csv(os.path.join(animalDirPath, key + '_trim_rest_phases.csv'))

        # Pruned data - removes just the starting rests if exist
        allPrunedDf = animalDict[key][6]
        prunedRunsDf = animalDict[key][7]
        prunedRestsDf = animalDict[key][8]

        allPrunedDf.to_csv(os.path.join(animalDirPath, key + '_pruned_sessions.csv'))
        prunedRunsDf.to_csv(os.path.join(animalDirPath, key + '_pruned_run_phases.csv'))
        prunedRestsDf.to_csv(os.path.join(animalDirPath, key + '_pruned_rest_phases.csv'))

        # Survival dataframe - created originally for making survival curves
        # but a useful format
        survivalDf = animalDict[key][9]

        survivalDf.to_csv(os.path.join(animalDirPath, key + '_survival_dataframe.csv'))
        # Output a readme explaination maybe?

def checkInputFile(inputFileArg):
    """Make sure the file exists"""
    if not os.path.exists(inputFileArg):
        print "Input fasta file not found. Check path."
        sys.exit(1)

def checkFileHeader(readerObj, HEADER_STRING):
    """Function to check the file's header."""
    #Move to the next (first) row of data and assign it to a variable
    firstHeader = readerObj.next()

    # Try a search and find on the header row to match HEADER_STRING. If return
    # error, print feedback and quit program.
    try:
        searchHeader = re.search(HEADER_STRING, firstHeader[0])
        searchResult = searchHeader.group(0) # group(0) returns whole string
        return firstHeader 
    except AttributeError:
        print "ERROR: This file is in the wrong format or is the wrong file type."
        sys.exit(0) # quit the program


def checkSampleHeader(SAMPLE_NAME_REGEXP, rowOfData):
    """Function to check the second header and formats header for distance csv
    Returns raw header and reformatted header"""
    rowLength = len(rowOfData)

    # Use the modulo (%) operator which yeilds remainder after dividing by a
    # number. Sample data should be in triplicate columns. If it's not, quit.
    # Else, reformat the header and return formated one
    if rowLength % 3 != 0:
        print "ERROR: Sample data are not in triplicate columns."
        sys.exit(0) # quit the program
    else:
        # For distance file, reformat header
        distHeaderRow = ["Date", "Time"]

        # Loop through the columns of data starting at col 3, until end. Step 3
        # at a time to get col containing Turn Data for each sample only.
        # Remember python lists start at 0, 1, 2, ...
        # I reformat the column order here to remove duplicate time and dates
        # and add a meters per minute one.
        for i in xrange(2, rowLength, 3):
            sampleHeader = rowOfData[i]

            # Add the Turns Data sample header as is to the row
            #distHeaderRow.append(sampleHeader)

            # Capture the sample name (without 'Turn Data')
            searchObj = re.search(SAMPLE_NAME_REGEXP, sampleHeader)
            searchResult = searchObj.group(1)

            # Append meters/min to end of name
            sampleDistHeader = searchResult + ' meters/min'

            # Add this new meters/min sample header as a new column
            distHeaderRow.append(sampleDistHeader)
        # Return True for header checked, and the newly created header
        return distHeaderRow

def getFilenameInfo(FILE_NAME_REGEXP, user_args_input):
    """Function to get dirpath, the whole filename and the filename without the .asc"""
    
    # get filename from first command line argument
    # fileDir, wholeFileName = os.path.split(user_args_input)
    wholeFileName = os.path.basename(user_args_input)

    # Use a regular expression to match the filename
    nameSearchObj = re.search(FILE_NAME_REGEXP, wholeFileName)

    # Capture part without extension. Notice FILE_NAME_REGEXP in parentheses
    # is inside group(1). If there was another pair of () it would be group(2)
    fileNameNoExtension = nameSearchObj.group(1)

    # return information file name without extension (e.g. '.csv', '.asc')
    return  fileNameNoExtension #, wholeFileName, fileDir  # Don't need

def parseInput():
    """Use argparse to handle user input for program"""
    
    # Create a parser object
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        
        description="""%(prog)s parses mouse running wheel data that has been 
        output into a ASCII file directly obtained from the Vitalview Software. 
        The input file should have two headers. The first will be the the over 
        all file header that says 'Experiment Logfile:' followed by the date. 
        Second, the data header below in comma delimited format (csv)""",

        epilog=textwrap.dedent("""\
        The script will output a csv file for each of the following:
            1) Mice data - summary statistics
            2) Raw data - unmanipulated
            3) Distance calculated - converted turns to meters
            4) Time Filtered - includes data > 18:01:00 of day 1 to 06:00:00 of day 3
            5) Sum Hourly - minute data is summed into hours per row
            6) Cumulative - data from each hour is compounded onto the previous"""))
    
    parser.add_argument("input",
        help="File name and/or path to experiment_file.asc")
    
    parser.add_argument("-v", "--version", action="version",
                        version=textwrap.dedent("""\
        %(prog)s
        -----------------------   
        Version:    0.2 
        Updated:    01/26/2015
        By:         Prech Uapinyoying   
        Website:    https://github.com/puapinyoying"""))

    args = parser.parse_args()
    
    return args


user_args = parseInput()

if user_args.input:
    cohortName = getFilenameInfo(FILE_NAME_REGEXP, user_args.input)
    # Read in running wheel data

    rawDf = pd.read_csv(user_args.input)

    ftDf, nullRows = formatRawDf(rawDf)

    sDf = calcSessions(ftDf)

    dataDict = parsePhase(sDf)

    outputAllToFile(rawDf, ftDf, nullRows, dataDict, cohortName)
