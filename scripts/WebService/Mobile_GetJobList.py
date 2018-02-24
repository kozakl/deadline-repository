from System import String
from System import DateTime
from System.IO import *
from System.Security import *
from System.Text import *

from Deadline.Scripting import *

import traceback

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__( dlArgs, qsArgs ):
    returnVal = ""
    
    sb = StringBuilder()
    
    # Get the args
    egosort = qsArgs["ego"] if "ego" in qsArgs else None
    primarysort = qsArgs["psort"] if "psort" in qsArgs else None
    primarysortorder = qsArgs["psord"] if "psord" in qsArgs else None
    secondarysort = qsArgs["ssort"] if "ssort" in qsArgs else None
    secondarysortorder = qsArgs["ssord"] if "ssord" in qsArgs else None
    pulseaddress = qsArgs["pulse"] if "pulse" in qsArgs else None
    lastupdate = qsArgs["update"] if "update" in qsArgs else None
    nonplist = qsArgs["plist"] if "plist" in qsArgs else None

    # parse the last update
    if ( lastupdate != None ):
        lastupdate = fromPlatformIndDateTime( lastupdate )#BUG possibility when starting the app for the first time - unable to reproduce
    
    # check if plist is wanted or not
    if( nonplist != None ):
        usePlist = False
    else:
        usePlist = True
        
    plugins = {}
    users = {}
    statuses = {}
    groups = {}
    pools = {}
    
    thisAddress = ClientUtils.GetMacAddress()
    jobs = WebServiceUtils.GetJobs()
    
    # do the sorts
    if ( secondarysort != None ):
        jobs = SortDictArrayByKey( jobs, secondarysort, secondarysortorder )
    if ( primarysort != None ):
        jobs = SortDictArrayByKey( jobs, primarysort, primarysortorder )
    if ( egosort != None ):
        jobs = EgoSortDictArray( jobs, egosort )
    if ( usePlist == False ):
        sb.AppendLine( "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" )
        sb.AppendLine( "<jobList>" )
        
        # add each job
        for job in jobs:
            if ( job != None and job["Status"] != "Deleted"):
                try:
                    lastJobUpdate = DateTime.Parse( job["LastWriteTime"] )
                except:
                    lastJobUpdate = None
                
                # if there was no update time given, or the update time is before this jobs last update
                if ( lastupdate == None or pulseaddress != thisAddress or DateTime.Compare( lastupdate, lastJobUpdate ) < 0 ):
                    sb.AppendLine( "\t<job>" )
                    sb.AppendLine( "\t\t<name>" + SecurityElement.Escape( job["Name"] ) + "</name>" )
                    sb.AppendLine( "\t\t<comment>" + SecurityElement.Escape( job["Comment"] ) + "</comment>" )
                    sb.AppendLine( "\t\t<plugin>" + job["PluginName"] + "</plugin>" )
                    sb.AppendLine( "\t\t<uname>" + job["UserName"] + "</uname>" )
                    sb.AppendLine( "\t\t<status>" + job["Status"] + "</status>" )
                    sb.AppendLine( "\t\t<jobid>" + job["JobId"] + "</jobid>" )
                    sb.AppendLine( "\t\t<taskcount>" + job["TaskCount"] + "</taskcount>" )
                    sb.AppendLine( "\t\t<completed>" + job["CompletedChunks"] + "</completed>" )
                    sb.AppendLine( "\t\t<errors>" + job["ErrorReports"] + "</errors>" )
                    sb.AppendLine( "\t\t<group>" + job["Group"] + "</group>" )
                    sb.AppendLine( "\t\t<pool>" + job["Pool"] + "</pool>" )
                    sb.AppendLine( "\t</job>" )
                # if the job is up to date, just print it's id to retrieve its data
                else:
                    sb.AppendLine( "\t<string>" + job["JobId"] + "</string>" )
                
                plugins[job["PluginName"]] = True
                users[job["UserName"]] = True
                statuses[job["Status"]] = True
                groups[job["Group"]] = True
                pools[job["Pool"]] = True
        
        # meta dictionary
        sb.AppendLine( "\t<meta>" )
        
        # add each section
        listKeys( "plugin", plugins, sb, False )
        listKeys( "uname", users, sb, False )
        listKeys( "status", statuses, sb, False )
        listKeys( "group", groups, sb, False )
        listKeys( "pool", pools, sb, False )
        
        # add the new update time
        sb.AppendLine( "\t\t<update>" + toPlatformIndDateTime( DateTime.Now ) + "</update>" )
        
        # add Pulse's mac address
        sb.AppendLine( "\t\t<pulse>" + thisAddress + "</pulse>" )
        
        sb.AppendLine( "\t</meta>" )
        sb.AppendLine( "</jobList>" )
        
        returnVal = sb.ToString()
    else:
        sb.AppendLine( "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" )
        sb.AppendLine( "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">" )
        sb.AppendLine( "<plist version=\"1.0\">" )
        sb.AppendLine( "<dict>" )
        
        # jobs array
        sb.AppendLine( "\t<key>jobs</key>" )
        sb.AppendLine( "\t<array>" )
        
        # add each job
        for job in jobs:
            if ( job != None and job["Status"] != "Deleted"):
                try:
                    lastJobUpdate = DateTime.Parse( job["LastWriteTime"] )
                except:
                    lastJobUpdate = None
                
                # if there was no update time given, or the update time is before this jobs last update
                if ( lastupdate == None or pulseaddress != thisAddress or DateTime.Compare( lastupdate, lastJobUpdate ) < 0 ):
                    sb.AppendLine( "\t\t<dict>" )
                    sb.AppendLine( "\t\t\t<key>name</key><string>" + SecurityElement.Escape( job["Name"] ) + "</string>" )
                    sb.AppendLine( "\t\t\t<key>comment</key><string>" + SecurityElement.Escape( job["Comment"] ) + "</string>" )
                    sb.AppendLine( "\t\t\t<key>plugin</key><string>" + job["PluginName"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>uname</key><string>" + job["UserName"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>status</key><string>" + job["Status"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>jobid</key><string>" + job["JobId"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>taskcount</key><string>" + job["TaskCount"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>completed</key><string>" + job["CompletedChunks"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>errors</key><string>" + job["ErrorReports"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>group</key><string>" + job["Group"] + "</string>" )
                    sb.AppendLine( "\t\t\t<key>pool</key><string>" + job["Pool"] + "</string>" )
                    sb.AppendLine( "\t\t</dict>" )
                # if the job is up to date, just print it's id to retrieve its data
                else:
                    sb.AppendLine( "\t\t<string>" + job["JobId"] + "</string>" )
                
                plugins[job["PluginName"]] = True
                users[job["UserName"]] = True
                statuses[job["Status"]] = True
                groups[job["Group"]] = True
                pools[job["Pool"]] = True
        
        sb.AppendLine( "\t</array>" )
        
        # meta dictionary
        sb.AppendLine( "\t<key>meta</key>" )
        sb.AppendLine( "\t<dict>" )
        
        # add each section
        listKeys( "plugin", plugins, sb, True )
        listKeys( "uname", users, sb, True )
        listKeys( "status", statuses, sb, True )
        listKeys( "group", groups, sb, True )
        listKeys( "pool", pools, sb, True )
        
        # add the new update time
        sb.AppendLine( "\t\t<key>update</key>" )
        sb.AppendLine( "\t\t<string>" + toPlatformIndDateTime( DateTime.Now ) + "</string>" )
        
        # add Pulse's mac address
        sb.AppendLine( "\t\t<key>pulse</key>" )
        sb.AppendLine( "\t\t<string>" + thisAddress + "</string>" )
        
        sb.AppendLine( "\t</dict>" )
        
        sb.AppendLine( "</dict>" )
        sb.AppendLine( "</plist>" )
        
        returnVal = sb.ToString()
    
    return returnVal

def toPlatformIndDateTime( dt ):
    day = dt.Day
    month = dt.Month
    year = dt.Year
    
    second = dt.Second
    minute = dt.Minute
    hour = dt.Hour
    
    return str(day) + "/" + str(month) + "/" + str(year) + "_" + str(hour) + ":" + str(minute) + ":" + str(second)

# accepts "day/month/year hour:min:sec"
def fromPlatformIndDateTime( dt ):
    dt = str(dt)
    
    (date, time) = dt.split( "_" )
    (day, month, year) = date.split( "/" )
    (hour, minute, second) = time.split( ":" )
    
    return DateTime( int(year), int(month), int(day), int(hour), int(minute), int(second) )

def listKeys( title, dict, sb, useplist ):
    if ( useplist == False ):
        # print the dict
        sb.AppendLine( "\t\t<m" + title + "s>" )
        
        # print the values
        for key in dict:
            sb.AppendLine( "\t\t\t<m" + title + ">" + key + "</m" + title  + ">" )
        
        # close the dict
        sb.AppendLine( "\t\t</m" + title + "s>" )
    else:
        # print the dict
        sb.AppendLine( "\t\t<key>" + title + "</key>" )
        sb.AppendLine( "\t\t<dict>" )
        
        # print the values
        for key in dict:
            sb.AppendLine( "\t\t\t<key>" + key + "</key><true />" )
        
        # close the dict
        sb.AppendLine( "\t\t</dict>" )
        
def EgoSortDictArray( array, user ):
    userArray = []
    otherArray = []
    
    for i in range( 0, len(array) ):
        if ( String.Compare( array[i]["UserName"], user, True ) == 0 ):
            userArray.append( array[i] )
        else:
            otherArray.append( array[i] )
    
    for i in range( 0, len(otherArray) ):
        userArray.append( otherArray[i] )
    
    return userArray

def SortDictArrayByKey( array, key, order ):
    arrayList = []
    for item in array:
        arrayList.append(item)
    
    return mergesort( arrayList, key, order )
    
def mergesort( list, key, order ):
    # base case
    if ( len( list ) <= 1 ):
        return list
    
    # get left and right list
    left = list[:len(list)/2]
    right = list[len(list)/2:len(list)]
    
    # recursively sort the list
    left = mergesort( left, key, order )
    right = mergesort( right, key, order )
    
    # merge the lists into ret
    return merge( left, right, key, order )

def merge( left, right, key, order ):
    # init return list
    ret = []
    
    # init position in left and right lists
    leftPos = 0
    rightPos = 0
    
    # get the length of the two lists
    lenLeft = len( left )
    lenRight = len( right )
    
    # merge the lists
    if ( order == None or order == "0" ):
        while ( leftPos < lenLeft and rightPos < lenRight ):
            if ( String.Compare( key, "SubmitDateTime", True ) != 0 ):
                # Normal String Compare
                if ( left[leftPos] == None ):
                    leftPos += 1
                elif ( right[rightPos] == None ):
                    rightPos += 1
                elif ( String.Compare( left[leftPos][key], right[rightPos][key], True ) <= 0 ):
                    ret.append( left[leftPos] )
                    leftPos += 1
                else:
                    ret.append( right[rightPos] )
                    rightPos += 1
            else:
                # Compare Dates
                if ( left[leftPos] == None ):
                    leftPos += 1
                elif ( right[rightPos] == None ):
                    rightPos += 1
                else:
                    try:
                        if ( DateTime.Compare( DateTime.Parse( left[leftPos][key] ), DateTime.Parse( right[rightPos][key] ) ) >= 0 ):
                            ret.append( left[leftPos] )
                            leftPos += 1
                        else:
                            ret.append( right[rightPos] )
                            rightPos += 1
                    except:
                        leftPos += 1
    else:
        while ( leftPos < lenLeft and rightPos < lenRight ):
            if ( String.Compare( key, "SubmitDateTime", True ) != 0 ):
                # Normal String Compare
                if ( left[leftPos] == None ):
                    leftPos += 1
                elif ( right[rightPos] == None ):
                    rightPos += 1
                elif ( String.Compare( left[leftPos][key], right[rightPos][key], True ) >= 0 ):
                    ret.append( left[leftPos] )
                    leftPos += 1
                else:
                    ret.append( right[rightPos] )
                    rightPos += 1
            else:
                # Compare Dates
                if ( left[leftPos] == None ):
                    leftPos += 1
                elif ( right[rightPos] == None ):
                    rightPos += 1
                else:
                    try:
                        if ( DateTime.Compare( DateTime.Parse( left[leftPos][key] ), DateTime.Parse( right[rightPos][key] ) ) <= 0 ):
                            ret.append( left[leftPos] )
                            leftPos += 1
                        else:
                            ret.append( right[rightPos] )
                            rightPos += 1
                    except:
                        leftPos += 1
    
    # extend ret with the remaining list
    if ( leftPos < lenLeft ):
        while ( leftPos < lenLeft ):
            if ( left[leftPos] == None ):
                leftPos += 1
            else:
                ret.append( left[leftPos] )
                leftPos += 1
    else:
        while ( rightPos < lenRight ):
            if ( right[rightPos] == None ):
                rightPos += 1
            else:
                ret.append( right[rightPos] )
                rightPos += 1
    
    return ret
