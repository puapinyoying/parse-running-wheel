#! /usr/bin/env python

# Import libraries for data analysis
from __future__ import division
import re
import os
import csv
import sys
#import tqdm
import argparse
#import openpyxl
import textwrap
import numpy as np
import pandas as pd
from datetime import datetime
from pandas import Series, DataFrame
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# Regular Expressions and static (unchanging) variables 
SAMPLE_NAME_REGEXP = r'([\w \/\)\(\-\.\|]+) Turns Data'
FILE_NAME_REGEXP = r'(.+)\.(.+)'
HEADER_STRING = 'Experiment Logfile:'

#########################################################
### Section below contains functions for calculations ###
#########################################################

def formatRawDf(rawDf):

    nullRows = rawDf.iloc[:,2::3].isnull().sum()
    print '\nWarning: Null values below will be back filled'
    nullRows.index.name = 'column_name'
    nullRows.name = 'null_value_count'
    nullRows = nullRows.reset_index()
    print nullRows # Output to stdout

    # print '\nWarning: The above null values were replaced with zeros'
    
    # how to deal with NAs: fillna with zero, fill forward fill back
    # I think backfill is best option, with limit 1, or fill zeros for more
    # conservative take (use 'ffill' for forward fill)
    rawFill = rawDf.fillna(method='bfill', limit=1)
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

    # Add a name for all column headers
    df1.columns.name = 'condition'

    df2 = df1 * 0.361 # mult all turns data by 0.361 to convert turns to meters

    # Select the column names so we can rename them
    colNames = df2.columns

    # Create a regular expression formula
    REG_EXP = r'^([\w\/\s\-\+]+) Turns Data'

    sampleName = re.search(REG_EXP, colNames[0])

    # Loop through list of column headers. We want to:
    # 1. Remove 'Turns Data' to obtain just the sample name
    # 2. Remove any spaces, periods, slashes and plus signs
    # 3. Replace with underscores '_'
    newColNames = []

    for name in colNames:
        temp = re.search(REG_EXP, name)
        origName = temp.group(1)
        noSpaceName = re.sub(r'[\/\s\.]', r'_', origName)
        rmPlusSign = re.sub(r'[\+]', r'_plus_', noSpaceName)
        newColNames.append(rmPlusSign)

    df2.columns = newColNames # Sub the old column names for the new ones
    df2.columns.name = 'condition'  # got erased, add back
    df2.index.name = 'date_time'

    return df2, nullRows  # returns formatted df and num of rows with null vals

def formatHourlyCumSum(df):
    hourlyDf = df.resample('H')
    hourlyCumSumDf = hourlyDf.cumsum()

    return hourlyDf, hourlyCumSumDf

def calcSumDistPerDay(df):
    t = formattedDf.index # Get timeseries index
    t2 = Series(t) # convert to series
    uniqueDates = t2.map(pd.Timestamp.date).unique() # get unique dates only

    uniqueList = []

    # For each datetime object in unique dates, convert to strings so we can
    # use them as dataframe indexes
    for date in uniqueDates:
        uniqueList.append(date.strftime('%Y-%m-%d'))

    dateDict = {} # New dictionary for dataframe

    for date in uniqueList:
        # Grab matching data, take sum and place in new dictionary
        dateDict[date] = formattedDf[date].sum()

    daySumDf = DataFrame(dateDict) # Turn into dataframe

    return daySumDf

def calcSessions(df):
    """Calculates running session data. Each session consists of a run phase
    followed by a rest phase. Function outputs a dictionary containing a
    session dataframe for each animal in the formatted dataframe. Each session
    dataframe contains columns for session number, run start time,
    run stop time, number of minutes run, distance run, velocity of run,
    rest start time, rest end time, number of minutes rested, run observed and
    rest observed."""

    colList = df.columns

    sessionDict = {} # Dictionary to house all animal's session dataframes

    # iterate over list of column names and use to access data from each column
    for pos, col in enumerate(colList):

        # reset the dateTime index (place index back as a data column)
        resetCol = df.iloc[:,pos].reset_index()
        row_iter = resetCol.itertuples() # create iterator for accessing row data
        colLen = len(resetCol[col])  # keep track of number of rows in column 

        # Create some variables
        runMins = 0        # current sum of minutes in run phase
        runDist = 0        # current sum of distance in run phase
        runMinsList = []   # list of minutes per run phase
        runDistList = []   # list of distances per run phase
        runStartList = []  # list of run start times
        runEndList = []    # list of run end times

        restMins = 0       # curren sum of minutes in rest phase
        restMinsList = []  # current list of minutes for each rest phase
        restStartList = [] # list of rest start times
        restEndList = []   # list of rest end times

        # Keep track of previous and current times and distance
        #prevTime = None
        currTime = None
        prevDist = None
        currDist= 0
        
        # Create new dictionary to house current animal's session data
        sessionDf = DataFrame()

        # iterate over each row in the column of data
        for rowNum, row in enumerate(row_iter):     
            currDist = row[2]
            currTime = row[1]

            # If this is the first session
            if prevDist == None:
                if currDist > 0: # run phase
                    runStartList.append(currTime)
                    runMins += 1
                    runDist += currDist

                else: # if currDist == 0; or rest phase
                    restStartList.append(currTime)
                    restMins += 1

                    # If the animal started with a rest phase, then append empty
                    # values for the run phase. We want every session to start 
                    # with a run phase then followed by a rest phase.
                    runStartList.append(None)
                    runEndList.append(None)
                    runMinsList.append(None)
                    runDistList.append(None)

                prevDist = currDist
                prevTime = currTime

            elif prevDist == 0: # if animal was resting last minute
                if currDist == 0: # and currently resting this minute
                    restMins += 1
                    prevDist = currDist

                else:  # currDist > 0; End of rest phase, close out
                    restEndList.append(currTime)
                    restMinsList.append(restMins)
                    restMin = 0 # reset accumilated rest minute total

                    # Beginnin new run phase
                    runStartList.append(currTime)
                    runMins = 0 # Make sure to reset first
                    runMins += 1
                    runDist += currDist
                    prevDist = currDist

            elif prevDist > 0: # If animal was running last minute
                if currDist > 0: # and currently running this minute
                    runMins += 1
                    runDist += currDist
                    prevDist = currDist

                else: # currDist == 0; End of running phase, close out
                    runMinsList.append(runMins)
                    runDistList.append(runDist)
                    runEndList.append(currTime)
                    runMins = 0 # reset accumilated run phase minutes
                    runDist = 0 # reset accumilated run phase distance


                    # Also start of new rest phase
                    restStartList.append(currTime)
                    restMins = 0 # reset resting minutes first
                    restMins += 1
                    prevDist = currDist

            if rowNum == colLen - 1:  # If its the last row
                if currDist > 0: # Animal is still running; end here
                    runMinsList.append(runMins)
                    runDistList.append(runDist)
                    runEndList.append(currTime)
                    
                    # This final run time incomplete due to end of experiment
                    # so this session does not have a resting phase
                    restStartList.append(None)
                    restEndList.append(None)
                    restMinsList.append(None)

                else: # currDist == 0: Animal is still resting
                    restMinsList.append(restMins) # close out rest minutes
                    restEndList.append(currTime)
                        
                # Create a dictionary of all the lists to form a new data frame
                resultsDict = {'run_start':runStartList, 'run_end':runEndList, 
                           'run_mins':runMinsList,'run_dist(m)':runDistList, 
                           'rest_start':restStartList, 'rest_end':restEndList, 
                           'rest_mins':restMinsList}
             
                # use the results dictionary to make dataframe
                sessionDf = DataFrame(resultsDict) 

        # Place each animal's session df into a session dict for all animals. 
        # Each animal's session dataframe can now be accessed by providing the 
        # animal name as the dictionary's key.
        sessionDict[col] = sessionDf 

    return sessionDict

def observed(x):
    """Used in calcObsCols(). Simple test to see if data is present. 
    If None, then return False"""
    if x == None:
        return False
    else:
        return True

def calcObsCols(sessionDf):
    """Used in reformatSessions(). Check to see if a run or rest was observed 
    for each session, return both columns."""
    runObsCol = sessionDf.run_start.apply(observed)
    restObsCol = sessionDf.rest_start.apply(observed)
    runObsCol.name = 'run_obs'
    restObsCol.name = 'rest_obs'
    return runObsCol, restObsCol

def calcVelocityCol(sessionDf):
    """Used in reformatSessions(). Calculate the velocity of each run session 
    and return column of data"""
    velocityCol = sessionDf['run_dist(m)'] / sessionDf['run_mins']
    velocityCol.name = 'velocity(m/min)'
    return velocityCol

def reformatSessions(sessionDict):
    """Reformats the SessionDict from calcSessions(). Calculates and adds
    new columns to each sessionDf including:
        1. Session column
        2. Run velocity column
        3. Run observed column
        4. Rest observed column
    Finally, it creates a new dataframe and reorganizes the columns."""
    reformatedDict = {} # new session dictionary for added and reformated cols
    
    for animalName, df in sessionDict.iteritems():
        
        # Do calculations and get columns
        runObsCol, restObsCol = calcObsCols(df)
        velocityCol = calcVelocityCol(df)
        #sessionCol = calcSessionCol(df)
        
        # Join all columns into a single dataframe
        joinedDf = pd.concat([df,velocityCol,runObsCol, restObsCol],
                                axis=1)

        resetDf = joinedDf.reset_index()  # reset the index
        
        # Make a list of column names in the order we want
        colOrder = ['run_start', 'run_end', 'run_mins', 
                    'run_dist(m)', 'velocity(m/min)', 'rest_start',
                    'rest_end', 'rest_mins', 'run_obs', 'rest_obs']
        
        arrangedDf = resetDf[colOrder]
        arrangedDf.index = arrangedDf.index + 1
        arrangedDf.index.name = 'session'

        reformatedDict[animalName] = arrangedDf
        
    return reformatedDict


def calcPercentRunRest(sessionDict):
    '''Calculate the percentage the animal ran and rested of the total time the
    data was collected. If data was collected one row per minute, the number of
    rows in the raw data file should correspond to the sum total of minutes.'''
    # Create an empy dictionary list for creating a dataframe in the end
    dictList = []

    for animalName, df in sessionDict.iteritems():
        sumMinsRun = df.run_mins.sum()
        sumDistRun = df['run_dist(m)'].sum()
        sumMinsRest = df.rest_mins.sum()
        sumTotal = sumMinsRun + sumMinsRest

        # Create a dictionary for each row to be in the dataframe
        rowDict = {'animal':animalName, 'sum_mins_run':sumMinsRun, 
                    'sum_mins_rest':sumMinsRest, 'sum_dist_run(m)':sumDistRun,
                    'total_mins':sumTotal}

        dictList.append(rowDict) # Add to the dictionary list

    # Create dataframe
    df2 = DataFrame(dictList)

    # Calculate percent data columns
    percentRun =  (df2.sum_mins_run / df2.total_mins) * 100
    percentRest = (df2.sum_mins_rest / df2.total_mins) * 100

    rPercentRun = percentRun.round(2)
    rPercentRest = percentRest.round(2)

    df2.index.name = 'index' # Add header names to the columns
    rPercentRun.name = 'percent_mins_run'
    rPercentRest.name = 'percent_mins_rest'

    joinedDf = pd.concat([df2, rPercentRun, rPercentRest], axis=1) # join cols

    colOrder = ['animal','sum_mins_run', 'sum_dist_run(m)', 'sum_mins_rest',
                'total_mins', 'percent_mins_run', 'percent_mins_rest']

    percentRunRestDf = joinedDf[colOrder] # Final order of columns

    return percentRunRestDf



###########################################################################
### Section below contains functions for input/output, graphing and     ###
### parsing files                                                       ###
###########################################################################

def chunkLists(userList, chunkSize):
    """Use to split lists of columns into chunks of sublists for graphing"""
    chunkList = []

    # x goes from start of list to end in groups of chunkSize
    for x in xrange(0, len(userList), chunkSize):
        # Eg. If chunkSize = 6:
        # first loop: start = 0 and end = 6
        # second loop: start = 6 and end = 12
        # third loop: start = 12 end = 18 etc.
        chunk=userList[x:x+chunkSize]
        chunkList.append(chunk)
    return chunkList

def plotGraphs(formattedDf, percentRunRestDf, newDirPath, cohortName):
    """Make some plots"""
    hourlyDf, hourlyCumSumDf = formatHourlyCumSum(formattedDf)
    daySumDf = calcSumDistPerDay(formattedDf)

    with PdfPages(os.path.join(newDirPath, cohortName + '_graphs.pdf')) as pdf:
        # Barplot of daily distance sums
        b = daySumDf.plot(kind='bar',figsize=(10,5), width=0.75, alpha=.75) #color=['#FFAAAA','#D46A6A','#801515','#550000'])
        b.set_title('{0}: Total Running Distance By Day'.format(cohortName), y=1.08)
        b.set_ylabel('Distance in meters')
        b.set_xlabel('Animal & Condition')
        b.legend(bbox_to_anchor=(1.12, 0.6),prop={'size':6})
        pdf.savefig(bbox_inches='tight')
        plt.clf()

        # Stacked Barplot of % rest and run
        pnames = percentRunRestDf.animal
        pruns = percentRunRestDf.percent_mins_run
        prests = percentRunRestDf.percent_mins_rest
        px = range(len(pnames)) # xaxis must be numbers, we can change to names with xticks
        width =0.50 # of bars, must be a fraction
        b1 = plt.bar(px, pruns, width, color='black')
        b2 = plt.bar(px, prests, width, color='lightgrey',bottom=pruns)
        # xticks takes original xaxis (px), and replacement (pnames)
        plt.xticks(px, pnames, size='small', rotation=90, horizontalalignment='left')
        plt.title('Percent Run and Percent Rest Per Animal', y=1.08)
        plt.legend((b1[0], b2[0]), ('Run', 'Rest'), bbox_to_anchor=(1.15, 1.01),prop={'size':10})
        plt.ylabel('Percent %')
        plt.xlabel('Animal & Condition')
        pdf.savefig(bbox_inches='tight')
        plt.clf()

        # Cumsum Line plot
        chunks = chunkLists(hourlyDf.columns, 6)
        for i, c in enumerate(chunks):
            l = hourlyDf[chunks[i]].cumsum().plot(figsize=(7, 7), linewidth=3, alpha=0.70)
            l.set_title('{0}: Cumilative Sum Plot Binned By Hour (plot {1} of {2})'.format(
                cohortName, i+1, len(chunks)), y=1.08)
            l.set_ylabel('Distance in meters)')
            l.set_xlabel('Date & Time')
            l.legend(bbox_to_anchor=(1.38, 1.01),prop={'size':8})
            pdf.savefig(bbox_inches='tight')
            plt.clf()

        # Distance Histogram - Line plot
        chunks2 = chunkLists(hourlyDf.columns, 3)
        for i, c in enumerate(chunks2):   
            h = hourlyDf[chunks2[i]].plot(figsize=(15, 3), linewidth=3, alpha=0.65)
            h.set_title('{0}: Distance Histogram Binned By Hour (plot {1} of {2})'.format(
                cohortName, i+1, len(chunks2)), y=1.08)
            h.set_ylabel('Distance in meters')
            h.set_xlabel('Date & Time')
            h.legend(bbox_to_anchor=(1.18, 1.01), prop={'size':8})
            pdf.savefig(bbox_inches='tight')
            plt.clf()

def outputAllToFile(rawDf, formattedDf, percentRunRestDf, nullRows, sessionDict,
                        cohortName):
    """Creates a cohort folder in current directory and output's all the 
    data frames for each sample."""

    currWorkingDir = os.getcwd()
    newDirPath = os.path.join(currWorkingDir, cohortName)

    if not os.path.exists(newDirPath):
        os.makedirs(newDirPath)

    # output main formatted data frame
    print '\nExporting results to CSV...'
    print "Outputting raw dataframe"
    rawDf.to_csv(os.path.join(newDirPath, cohortName +'_rawdata.csv'))
    print "Outputting number of null rows."
    nullRows.to_csv(os.path.join(newDirPath, cohortName +'_num_null.csv'))
    print "Outputting formatted dataframe."
    formattedDf.to_csv(os.path.join(newDirPath, cohortName +'_formatted.csv'))
    print "Outputting calculated percent run and rest."
    percentRunRestDf.to_csv(os.path.join(newDirPath, cohortName + '_percentRunRest.csv'))

    hourlyDf, hourlyCumSumDf = formatHourlyCumSum(formattedDf)
    daySumDf = calcSumDistPerDay(formattedDf)

    print "Outputting data binned by the hour."
    hourlyDf.to_csv(os.path.join(newDirPath, cohortName +'_bin_by_hour.csv'))
    print "Outputting cumilative sum data by the hour."
    hourlyCumSumDf.to_csv(os.path.join(newDirPath, cohortName +'_cumsum_by_hour.csv'))
    print "Outputting data for total distance per day"
    daySumDf.to_csv(os.path.join(newDirPath, cohortName +'_sum_dist_by_day.csv'))
    # Output the plots
    # Output session data frames
    print '\nExporting results to CSV...'
    for animalName, sessionDf in sessionDict.iteritems():
        print "Outputting session data for: ", animalName
        sessionDf.to_csv(os.path.join(newDirPath, animalName + '_sessions.csv'))
        # Output a readme explaination maybe?

    print '\nMaking plots...'
    plotGraphs(formattedDf, percentRunRestDf, newDirPath, cohortName)
    print '**Done**.'

def checkInputFile(inputFileArg):
    """Make sure the file exists"""
    if not os.path.exists(inputFileArg):
        print "{0} not found. Check path.".format(inputFileArg)
        sys.exit(1)

def checkAscFileHeader(readerObj, HEADER_STRING):
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
        sys.exit(1) # quit the program


def checkSampleHeader(SAMPLE_NAME_REGEXP, rowOfData):
    """Function to check the second header"""
    rowLength = len(rowOfData)

    # Use the modulo (%) operator which yeilds remainder after dividing by a
    # number. Sample data should be in triplicate columns. If it's not, quit.
    # Else, reformat the header and return formated one
    if rowLength % 3 != 0:
        print "ERROR: Sample data are not in triplicate columns."
        sys.exit(1) # quit the program

def checkCsvHeader(user_input):
    with open(user_input, 'rb') as csvFile:
    # Turns the open file into an object we can use to pull data from
        fileReader = csv.reader(csvFile, delimiter=",", quotechar='"')
        header = fileReader.next()
        if len(header) % 3 != 0:
            print "ERROR: Data are not in triplicate columns. Check file."
            sys.exit(1) # quit the program
        
def getFilenameInfo(FILE_NAME_REGEXP, user_args_input):
    """Function to split the filename and extension and return both."""
    
    # get filename from first command line argument
    # fileDir, wholeFileName = os.path.split(user_args_input)
    wholeFileName = os.path.basename(user_args_input)

    # Use a regular expression to match the filename
    nameSearchObj = re.search(FILE_NAME_REGEXP, wholeFileName)

    # Capture name without extension. 
    fileNameNoExtension = nameSearchObj.group(1)

    # Grab file extension to determine if .asc or .csv
    fileExtension = nameSearchObj.group(2)

    # return information file name without extension (e.g. '.csv', '.asc')
    return  fileNameNoExtension, fileExtension #, wholeFileName, fileDir

def parse_asc(user_input):
    """Function to take asc file and split the animal summary and actual data
    into two files. Returns the raw csv name."""

    with open(user_input, 'rb') as csvFile:
    # Turns the open file into an object we can use to pull data from
        fileReader = csv.reader(csvFile, delimiter=",", quotechar='"')
        
        # Check first file header and assign to variable
        fileHeader = checkAscFileHeader(fileReader, HEADER_STRING)

        miceCsvName = cohortName + '_asc_summary.csv'
        rawCsvName = cohortName + '_asc_rawdata.csv'

        # Create a mice data csv file
        with open(miceCsvName, 'wb') as miceOutFile:
            miceFileWriter = csv.writer(miceOutFile)

            # Create a raw data csv file
            with open(rawCsvName, 'wb') as rawOutFile:
                rawFileWriter = csv.writer(rawOutFile)

                # First time around?
                firstRowOfFile = True

                # Make sure to check the data header too
                checkedSampleHeader = False

                # Iterate through every line (row) of the original file
                for row in fileReader:
                    # Put all mouse summary data into the mice sheet, data
                    # should be in less than 3 columns
                    if len(row) < 3:
                        # If very first row, place the checked header
                        if firstRowOfFile:
                            miceFileWriter.writerow(fileHeader)
                            # Next round, set to false to skip this part
                            firstRowOfFile = False
                        # For the rest of the rows, just dump
                        miceFileWriter.writerow(row)
                
                    # Real data should have at least 3 columns
                    else:
                        # Check second header, is it a multiple of 3?
                        if not checkedSampleHeader:
                            checkSampleHeader(SAMPLE_NAME_REGEXP, row)
                            checkedSampleHeader = True           
                            
                            # Raw data file takes header row as is
                            rawFileWriter.writerow(row)

                            print "\n**The file is in the correct format.**"

                        # Once the header is good
                        else:
                            rawFileWriter.writerow(row)
    return rawCsvName

def parseUserInput():
    """Use argparse to handle user input for program"""
    
    # Create a parser object
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        
        description="""%(prog)s parses mouse running wheel data that has been 
        output into a ASCII file directly obtained from the Vitalview Software. 
        The input file should have two headers. The first will be the the over 
        all file header that says 'Experiment Logfile:' followed by the date. 
        Second, the data header below in comma delimited format (csv)

        Option to use with csv files that have the mouse summary data removed.
        However, the data must still be in triplicate columns.""",

        epilog=textwrap.dedent("""\
        The script will output a csv file for each of the following:
            1) Animal data            <cohort_name>_asc_summary.csv
            2) Raw data               <cohort_name>_asc_rawdata.csv
            3) Formatted              <cohort_name>_formatted.csv
            4) Bin by hr              <cohort_name>_bin_by_hour.csv
            5) Cumilative sum by hr   <cohort_name>_cumsum_by_hour.csv
            6) Sum distance by day    <cohort_name>_sum_dist_by_day.csv
            7) Sessions               <animal>_sessions.csv
            8) Percent Run & rest     <cohort_name>_percentRunRest.csv
            9) Graphs                 <cohort_name>_graphs.pdf
          
        The pdf of graphs contain plots for:
            - Total Running Distance By Day
            - Percent Run and Percent Rest Per Animal
            - Cumulative Sum Plot Binned By Hour
            - Distance Histogram Binned By Hour"""))

    parser.add_argument("input",
        help="File name and/or path to experiment_file.asc or .csv")
    
    parser.add_argument("-v", "--version", action="version",
                        version=textwrap.dedent("""\
        %(prog)s
        -----------------------   
        Version:    0.4
        Updated:    05/03/2016
        By:         Prech Uapinyoying   
        Website:    https://github.com/puapinyoying"""))

    args = parser.parse_args()
    
    return args

# Grab parsed user input.
user_args = parseUserInput()

if user_args.input:

    # Start with sanity checks
    checkInputFile(user_args.input) # Does file exist? If no, exit and warn.

    # Next grab the file name to use as cohort and file extension
    cohortName, fileExtension = getFilenameInfo(FILE_NAME_REGEXP, user_args.input)
    
    if fileExtension == 'asc':
        rawCsvName = parse_asc(user_args.input)
        rawDf = pd.read_csv(rawCsvName)

    elif fileExtension == 'csv':
        checkCsvHeader(user_args.input)
        rawDf = pd.read_csv(user_args.input)

    else:
        print "This program only excepts the raw '.asc' file or '.csv' files."
        sys.exit(1)

    # Start doing some calculations and creating dataframes
    formattedDf, nullRows = formatRawDf(rawDf)
    sessionsDict = calcSessions(formattedDf)
    reformattedDict = reformatSessions(sessionsDict)
    percentRunRestDf = calcPercentRunRest(reformattedDict)

    # Dump csvs into folders
    outputAllToFile(rawDf, formattedDf, percentRunRestDf, nullRows, 
        reformattedDict, cohortName)