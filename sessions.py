#! /usr/bin/env python3

# Import libraries for data analysis
import re
import os
import csv
import sys
import argparse
import textwrap
import pandas as pd
from datetime import datetime
from pandas import Series, DataFrame
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# Regular Expressions and static (unchanging) variables 
FILE_NAME_REGEXP = r'(.+)\.(.+)'

##############################################################################
### Section below contains functions for reformatting and calculating data ###
##############################################################################
  

def reformatString(stringList):
    '''Reformat the list of strings to make it more consistant by:
        1. Convert to lower case
        2. Substitute spaces for underscores _
        3. Convert the + sign into _plus_
        4. Covert the ^ carrot sign into _pwr_
        5. Strip any trailing underscores (former spaces)
        6. Strip any leading underscores (former spaces)'''
    reformatedList = []
    for string in stringList:
        lowercased = string.lower()
        noSpace = re.sub(r'[\/\s\.]', r'_', lowercased)
        rmPlusSign = re.sub(r'[\+]', r'_plus_', noSpace)
        rmCarrot = re.sub(r'[\^]', r'_pwr_', rmPlusSign)
        rmMultiUnder = re.sub(r'_+', r'_', rmCarrot)
        rightStripUnder = rmMultiUnder.rstrip('_')
        leftStripUnder = rightStripUnder.lstrip('_')
        reformatedList.append(leftStripUnder)
    
    return reformatedList


def convertDatetime(df):
    '''Function to convert the row indexes (dates and times) into a proper datetime object we can use downstream'''
    originalIndex = df.index
    
    dtIndex = []
    for i in originalIndex:
        temp = datetime.strptime(str(i), '%m/%d/%y %H:%M') # specify the month, date, year, hour, minutes
        dtIndex.append(temp)
    
    df.index = dtIndex # replace original index with new datetime index
    
    return df


def fillNa(df):
    nullRows = df.isnull().sum()
    
    # Lets put some labels down
    nullRows.index.name = 'column_name'
    nullRows.name = 'null_value_count'
    nullRows = nullRows.reset_index()
    print('\nWarning: There are {} null values that will be back filled'.format(nullRows.null_value_count.sum()))

    # df_fill = df.fillna(0)
    # df_fill = df.fillna(method='ffill', limit=1)
    dfFilled = df.fillna(method='bfill', limit=1) # Do the backfill and limit it to only 1 consecutive row
    
    return dfFilled, nullRows


def formatRawDf(rawDf):
    '''Formats the raw data file by cleaning up the headers, assigning them properly and converting the row
    names into proper datetime objects. Outputs two dataframes, one with original turns data and the other 
    converted into meters (turns * 0.361)'''
    header1 = reformatString(rawDf.iloc[0]) # grab row 0 and reformat to remove spaces and special chars
    header2 = reformatString(rawDf.iloc[1])
    header3 = reformatString(rawDf.iloc[2])
    
    rawDf.iloc[0] = header1 # replace the original row with the reformated row
    rawDf.iloc[1] = header2
    rawDf.iloc[2] = header3
    
    # Use the first three rows as a multiindex header (3 stacked headers)
    rawDf.columns = [rawDf.iloc[0],rawDf.iloc[1],rawDf.iloc[2]]
    rawDf = rawDf.drop(rawDf.index[[0,1,2]]) # Remove the original 3 rows from the df
    rawDf.columns.names = ['sample', 'group', 'sensor'] # rename the three headers
    
    df = convertDatetime(rawDf) # Convert the row indexs (names) into proper datetime objects
    formattedTurnsDf, nullRows = fillNa(df) # Back fill any single NA's that may show up in the formatted df
    formattedDistanceDf = formattedTurnsDf.astype(float) * 0.361 # Convert turns to meters

    return formattedTurnsDf, formattedDistanceDf, nullRows


def customStartDateTime(formattedDistanceDf, customStart, customEnd):
    """Use user defined start and end date times if specified. None will be specifed
    for both customStart and customEnd if not specified (e.g. use all data)"""

    if customStart != None:
        try:
            customStartDt = datetime.strptime(customStart, '%m/%d/%Y %H:%M')
        except ValueError:
            print("Check customStart time. Custom start date times should be formated as 'month/day/year hour:minute'")
            print("(e.g. 9/5/2018). No leading zeros, years in four number format")
            sys.exit(1) # quit the program
    else:
        customStartDt = customStart

    if customEnd != None:
        try:
            customEndDt = datetime.strptime(customEnd, '%m/%d/%Y %H:%M')
        except ValueError:
            print("Check customEnd time. Custom end date times should be formated as 'month/day/year hour:minute'")
            print("(e.g. 9/5/2018). No leading zeros, years in four number format")
            sys.exit(1) # quit the program
    else:
        customEndDt = customEnd

    selectedDistanceDf = formattedDistanceDf[customStartDt:customEndDt]

    return selectedDistanceDf


def getStartingTime(selectedDistanceDf):
    """Determine the initial time point in the input data"""
    startDt = selectedDistanceDf.index[0] # grab datetime index from very first row of data
    startHr = startDt.hour
    startMin = startDt.minute
    
    return startHr, startMin


def calcBaseParam(startHr, startMin):
    baseFraction = startMin / 60
    baseParam = startHr + baseFraction
    
    return baseParam


def resampleByHr(selectedDistanceDf, customGrpByHr, baseParam):
    """Outputs a list of dictionaries with the rule as key, and resampledDf as value"""
    customDfList = []
    
    if customGrpByHr == None:
        customDfList = None
    else:
        for i in customGrpByHr:
            ruleStr = i + 'H'
            resampledDf = selectedDistanceDf.resample(rule=ruleStr, base=baseParam).sum()
            customDfDict = {ruleStr:resampledDf}
            customDfList.append(customDfDict)
    
    return customDfList


def formatHourly(selectedDistanceDf, baseParam):
    hourlyDf = selectedDistanceDf.resample(rule='H', base=baseParam).sum()

    return hourlyDf


def formatDaily(selectedDistanceDf, baseParam):
    dailyDf = selectedDistanceDf.resample(rule="1d", base=baseParam).sum()

    return dailyDf


def calcSessions(df):
    """Calculates running session data. Each session consists of a run phase
    followed by a rest phase. Function outputs a dictionary containing a
    session dataframe for each animal in the formatted dataframe. Each session
    dataframe contains columns for session number, run start time,
    run stop time, number of minutes run, distance run, velocity of run,
    rest start time, rest end time, number of minutes rested, run observed and
    rest observed."""

    colList = df.columns

    sessionsDict = {} # Dictionary to house all animal's session dataframes

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
        sessionsDict[col] = sessionDf 

    return sessionsDict

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

def reformatSessions(sessionsDict):
    """Reformats the sessionsDict from calcSessions(). Calculates and adds
    new columns to each sessionDf including:
        1. Session column
        2. Run velocity column
        3. Run observed column
        4. Rest observed column
    Finally, it creates a new dataframe and reorganizes the columns."""
    reformatedDict = {} # new session dictionary for added and reformated cols
    
    for animalName, df in sessionsDict.items():
        
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


def calcPercentRunRest(sessionsDict):
    '''Calculate the percentage the animal ran and rested of the total time the
    data was collected. If data was collected one row per minute, the number of
    rows in the raw data file should correspond to the sum total of minutes.'''
    # Create an empy dictionary list for creating a dataframe in the end
    dictList = []

    for animalName, df in sessionsDict.items():
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


###########################################################
### Section below contains functions for plotting data  ###
###########################################################

def chunkLists(userList, chunkSize):
    """Use to split lists of columns into chunks of sublists for graphing"""
    chunkList = []

    # x goes from start of list to end in groups of chunkSize
    for x in range(0, len(userList), chunkSize):
        # Eg. If chunkSize = 6:
        # first loop: start = 0 and end = 6
        # second loop: start = 6 and end = 12
        # third loop: start = 12 end = 18 etc.
        chunk=userList[x:x+chunkSize]
        chunkList.append(chunk)
    return chunkList

def plotGraphs(selectedDistanceDf, percentRunRestDf, hourlyDf, dailyDf, newDirPath, cohortName):
    """Make some plots"""
    with PdfPages(os.path.join(newDirPath, cohortName + '_graphs.pdf')) as pdf:
        # Barplot of daily distance sums
        b = dailyDf.plot(kind='bar',figsize=(10,5), width=0.75, alpha=.75) #color=['#FFAAAA','#D46A6A','#801515','#550000'])
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


####################################################################################
### Section below contains functions for file input/output data & sanity checks  ###
####################################################################################

def checkInputFile(inputFileArg):
    """Make sure the file exists"""
    if not os.path.exists(inputFileArg):
        print("{0} not found. Check path.".format(inputFileArg))
        sys.exit(1)

def checkHeader(rawDf):
    HEADER0_NAME = 'Channel Name:'
    HEADER1_NAME = 'Channel Group:'
    HEADER2_NAME = 'Sensor Type:'

    """Function to check the file's header."""
    #Move to the next (first) row of data and assign it to a variable

    # Try a search and find on the header row to match HEADER_STRING. If return
    # error, print feedback and quit program.
    if (rawDf.index[0] != HEADER0_NAME) or (rawDf.index[1] != HEADER1_NAME) or (rawDf.index[2] != HEADER2_NAME):
        print("ERROR: This file is in the wrong format. ")
        print("It's missing the proper headers (i.e. Channel Name, Channel Group, Sensor Type)")
        sys.exit(1) # quit the program
    else:
        print('File header checks out.') 


def outputAllToFile(formattedTurnsDf, formattedDistanceDf, selectedDistanceDf, 
    baseParam, hourlyDf, dailyDf, customDfList, sessionsDict, reformattedDict, percentRunRestDf, 
    nullRows, cohortName):
    """Creates a cohort folder in current directory and output's all the 
    data frames for each sample."""

    currWorkingDir = os.getcwd()
    newDirPath = os.path.join(currWorkingDir, cohortName)

    if not os.path.exists(newDirPath):
        os.makedirs(newDirPath)

    # output main formatted data frame
    print('\nExporting results to CSV...')
    print("Outputting raw dataframe")
    rawDf.to_csv(os.path.join(newDirPath, cohortName +'_rawdata.csv'))
    print("Outputting number of null rows.")
    nullRows.to_csv(os.path.join(newDirPath, cohortName +'_num_null.csv'))
    print("Outputting turns formatted dataframe.")
    formattedTurnsDf.to_csv(os.path.join(newDirPath, cohortName +'_formatted_turns.csv'))
    print("Outputting formatted distance dataframe.")
    formattedDistanceDf.to_csv(os.path.join(newDirPath, cohortName +'_formatted_distance.csv'))
    print("Outputting df with selected hours, if not specified will output all data")
    selectedDistanceDf.to_csv(os.path.join(newDirPath, cohortName +'_selected_distance.csv'))
    
    print("Outputting custom data bins.")
    if customDfList != None:
        for dfDict in customDfList:
            for rule, customDf in dfDict.items():
                customDf.to_csv(os.path.join(newDirPath, cohortName +'_bin_by_' + rule + '_' + '.csv'))

    print("Outputting data binned by the hour.")
    hourlyDf.to_csv(os.path.join(newDirPath, cohortName +'_bin_by_hour.csv'))
    print("Outputting data binned by day")
    dailyDf.to_csv(os.path.join(newDirPath, cohortName +'_bin_by_day.csv'))
    # Output the plots
    # Output session data frames
    print("Outputting calculated percent run and rest.")
    percentRunRestDf.to_csv(os.path.join(newDirPath, cohortName + '_percentRunRest.csv'))
    print('\nExporting results to CSV...')

    animalSessionsDir = os.path.join(newDirPath, 'animal_sessions')
    if not os.path.exists(animalSessionsDir):
        os.makedirs(animalSessionsDir)

    for animalName, sessionDf in sessionsDict.items():
        print("Outputting session data for: ", animalName)
        sessionDf.to_csv(os.path.join(animalSessionsDir, animalName[0] +'_' + animalName[1] + '_sessions.csv'))

    print('\nMaking plots...')
    plotGraphs(selectedDistanceDf, percentRunRestDf, hourlyDf, dailyDf, newDirPath, cohortName)
    print('**Done**.')

        
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


def parseUserInput():
    """Use argparse to handle user input for program"""
    
    # Create a parser object
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        
        description="""%(prog)s parses mouse running wheel data and calculates 
        run and rest sessions.  

        The program takes '.csv' data output from the 
        Vitalview Software. The input file should have three levels of headers. 
        From top to bottom. The header needs to be 'Channel Name:','Channel Group:' 
        and 'Sensor Type:'""",

        epilog=textwrap.dedent("""\
        The script will output a csv file for each of the following:
            1) Raw data               <cohort_name>_rawdata.csv
            2) Formatted turns        <cohort_name>_formatted_turns.csv
            3) Formatted distance     <cohort_name>_formatted_distance.csv
            4) Selected distance      <cohort_name>_selected_distance.csv (based on customStart/End inputs)
            4) Bin by hr              <cohort_name>_bin_by_hour.csv
            5) Bin by days            <cohort_name>_bin_by_day.csv
            6) Bin by <X> Hours       <cohort_name>_bin_by_<user_defined_hours>H.csv
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
    
    parser.add_argument("-S", '--customStart', default=None, 
        help=textwrap.dedent("""Specify custom start time in 'month/day/year hour:min' format. (e.g. '9/5/2018 11:30').
        Make sure to place in quotes and leave a space between year and hour.  Add no leading zeros. The
        hour should be in military time (24 hour) format. Defaults to None"""))

    parser.add_argument("-E",'--customEnd', default=None, 
        help=textwrap.dedent("""Specify custom end time in 'month/day/year hour:min' format. (e.g. '9/5/2018 11:30').
        Make sure to place in quotes and leave a space between year and hour.  Add no leading zeros. The
        hour should be in military time (24 hour) format. Defaults to None"""))

    parser.add_argument("-H",'--customGrpByHr', default=None, action='append',
        help=textwrap.dedent("""Optional: specify number of hours to group data by"""))
    
    parser.add_argument("-V", "--version", action="version",
                        version=textwrap.dedent("""\
        %(prog)s
        -----------------------   
        Version:    0.5.0
        Updated:    09/5/2018
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

    if fileExtension == 'csv':
        rawDf = pd.read_csv(user_args.input, index_col=[0], header=None)

    else:
        print("This program only excepts the raw '.csv' files.")
        sys.exit(1)

    # Start doing some calculations and creating dataframes
    formattedTurnsDf, formattedDistanceDf, nullRows = formatRawDf(rawDf)

    # Produce the formated dataframe with the user selected time windows
    customStart = user_args.customStart
    customEnd = user_args.customEnd
    selectedDistanceDf = customStartDateTime(formattedDistanceDf, customStart, customEnd)

    # Reformat the df to group the data by days, hours and custom amount of hours
    startHr, startMin = getStartingTime(selectedDistanceDf)
    baseParam = calcBaseParam(startHr, startMin)
    hourlyDf = formatHourly(selectedDistanceDf, baseParam)
    dailyDf = formatDaily(selectedDistanceDf, baseParam)

    if user_args.customGrpByHr != None:
        customDfList = resampleByHr(selectedDistanceDf, user_args.customGrpByHr, baseParam)
    else:
        customDfList = None

    # Calculate the sessions and other stats
    sessionsDict = calcSessions(selectedDistanceDf)
    reformattedDict = reformatSessions(sessionsDict)
    percentRunRestDf = calcPercentRunRest(reformattedDict)

    # Dump csvs into folders
    outputAllToFile(formattedTurnsDf, formattedDistanceDf, selectedDistanceDf, 
        baseParam, hourlyDf, dailyDf, customDfList, sessionsDict, reformattedDict, 
        percentRunRestDf, nullRows, cohortName)