from System.IO import *
from System.Text import *

from Deadline.Scripting import *

#This script is akin to the GetFarmStatisticsEx.py script, except it prints out more data and some of the entries have different names
########################################################################
## Main Function Called By Deadline
########################################################################
def __main__( dlArgs, qsArgs ):
    returnVal = ""
    
    jobids = RepositoryUtils.GetJobIds()
    slaves = WebServiceUtils.GetSlaves()
    jobs = WebServiceUtils.GetJobs()
    
    sb = StringBuilder()
    
    renderingJobs = 0
    queuedJobs = 0
    suspendedJobs = 0
    completedJobs = 0
    deletedJobs = 0
    failedJobs = 0
    pendingJobs = 0
    erroredJobs = 0
    
    for index in range(len(jobs)):
        status = jobs[index]["Status"]
        if( status == "Active" ):
            if( int(jobs[index]["RenderingChunks"]) > 0 ):
                renderingJobs += 1
            else:
                queuedJobs += 1
        elif( status == "Completed" ):
            completedJobs += 1
        elif( status == "Deleted" ):
            deletedJobs += 1
        elif( status == "Failed" ):
            failedJobs += 1
        elif( status == "Suspended" ):
            suspendedJobs += 1
        elif( status == "Pending" ):
            pendingJobs += 1
                
        if( int(jobs[index]["ErrorReports"]) > 0 ):
            erroredJobs += 1
            
        sb.AppendLine( "\n[%s]" % jobs[index]["JobId"] )
        
        for key in jobs[index].Keys:
            sb.AppendLine( "%s=%s" % (key, jobs[index][key]) )
            
    
    renderingMachines = 0
    idleMachines = 0
    stalledMachines = 0
    offlineMachines = 0
    disabledMachines = 0
    
    for index in range(len(slaves)):
        if slaves[index]["Enabled"].lower() == "true":
            status = slaves[index]["SlaveStatus"]
            if( status == "Idle" ):
                idleMachines += 1
            elif( status == "Stalled" ):
                stalledMachines += 1
            elif( status == "Offline" ):
                offlineMachines += 1
            elif( status == "Rendering" ):
                renderingMachines += 1
        else:
            disabledMachines += 1
            
        sb.AppendLine("\n[%s]" % slaves[index]["SlaveName"])
        for key in slaves[index].Keys:
            sb.AppendLine("%s=%s" % (key, slaves[index][key]))

    sb.Insert( 0, "Disabled Machines: %d\n" % disabledMachines )
    sb.Insert( 0, "Offline Machines: %d\n" % offlineMachines )
    sb.Insert( 0, "Stalled Machines: %d\n" % stalledMachines )
    sb.Insert( 0, "Idle Machines: %d\n" % idleMachines )
    sb.Insert( 0, "Rendering Machines: %d\n" % renderingMachines )
    sb.Insert( 0, "Failed Jobs: %d\n" % failedJobs )
    sb.Insert( 0, "Deleted Jobs: %d\n" % deletedJobs )
    sb.Insert( 0, "Completed Jobs: %d\n" % completedJobs )
    sb.Insert( 0, "Pending Jobs: %d\n" % pendingJobs )
    sb.Insert( 0, "Suspended Jobs: %d\n" % suspendedJobs )
    sb.Insert( 0, "Errored Jobs: %d\n" % erroredJobs )
    sb.Insert( 0, "Rendering Jobs: %d\n" % renderingJobs )
    sb.Insert( 0, "Queued Jobs: %d\n" % queuedJobs )
    sb.Insert( 0, "Repository time: %s\n" % RepositoryUtils.GetRepositoryDateTime().ToString( "MM/dd/yyyy HH:mm:ss" ) )

    returnVal = sb.ToString()
        
    return returnVal
