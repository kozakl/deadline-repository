from System.IO import *
from System.Text import *

from Deadline.Scripting import *

#This script is used to exactly replicate the output provided by the old "GetFarmStatisticsEx" command for DeadlineCommand.
#The only difference is that it uses the Data cached by Pulse, and therefore runs quicker.
#Another script is provided which outputs ALL the jobs' properties.
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
            
        sb.AppendLine( "[%s]" % jobs[index]["JobId"] )
        sb.AppendLine( "%s=%s" % ("AuxiliarySubmissionFileNames", jobs[index]["AuxiliarySubmissionFileNames"] ) )
        sb.AppendLine( "%s=%s" % ("Comment", jobs[index]["Comment"] ) )
        sb.AppendLine( "%s=%s" % ("CompletedDateTime", jobs[index]["CompletedDateTime"] ) )
        sb.AppendLine( "%s=%s" % ("ConcurrentTasks", jobs[index]["ConcurrentTasks"] ) )
        sb.AppendLine( "%s=%s" % ("Department", jobs[index]["Department"] ) )
        sb.AppendLine( "%s=%s" % ("JobDependencies", jobs[index]["JobDependencies"] ) )
        sb.AppendLine( "%s=%s" % ("JobDependencyPercentage", jobs[index]["JobDependencyPercentage"] ) )
        sb.AppendLine( "%s=%s" % ("ErrorReports", jobs[index]["ErrorReports"] ) )
        sb.AppendLine( "%s=%s" % ("FramesList", jobs[index]["FramesList"] ) )
        sb.AppendLine( "%s=%s" % ("Group", jobs[index]["Group"] ) )
        #sb.AppendLine( "%s=%s" % ("IgnoreBadJobDetection", jobs[index]["IgnoreBadJobDetection"] ) )
        #sb.AppendLine( "%s=%s" % ("IgnoreFailedJobDetection", jobs[index]["IgnoreFailedJobDetection"] ) )
        #sb.AppendLine( "%s=%s" % ("IgnoreFailedTaskDetection", jobs[index]["IgnoreFailedTaskDetection"] ) )
        sb.AppendLine( "%s=%s" % ("JobId", jobs[index]["JobId"] ) )
        sb.AppendLine( "%s=%s" % ("LimitGroups", jobs[index]["LimitGroups"] ) )
        sb.AppendLine( "%s=%s" % ("LimitTasksToNumberOfCpus", jobs[index]["LimitTasksToNumberOfCpus"] ) )
        sb.AppendLine( "%s=%s" % ("MachineLimit", jobs[index]["MachineLimit"] ) )
        sb.AppendLine( "%s=%s" % ("MachineLimitProgress", jobs[index]["MachineLimitProgress"] ) )
        sb.AppendLine( "%s=%s" % ("WhitelistFlag", jobs[index]["WhitelistFlag"] ) )
        sb.AppendLine( "%s=%s" % ("ListedSlaves", jobs[index]["ListedSlaves"] ) )
        sb.AppendLine( "%s=%s" % ("Name", jobs[index]["Name"] ) )
        #sb.AppendLine( "%s=%s" % ("NotificationMethod", jobs[index]["NotificationMethod"] ) )
        sb.AppendLine( "%s=%s" % ("NotificationEmails", jobs[index]["NotificationEmails"] ) )
        sb.AppendLine( "%s=%s" % ("NotificationTargets", jobs[index]["NotificationTargets"] ) )
        sb.AppendLine( "%s=%s" % ("OnJobComplete", jobs[index]["OnJobComplete"] ) )
        sb.AppendLine( "%s=%s" % ("OnTaskTimeout", jobs[index]["OnTaskTimeout"] ) )
        sb.AppendLine( "%s=%s" % ("OutputDirectories", jobs[index]["OutputDirectories"] ) )
        sb.AppendLine( "%s=%s" % ("OutputFileNames", jobs[index]["OutputFileNames"] ) )
        sb.AppendLine( "%s=%s" % ("OverrideNotificationMethod", jobs[index]["OverrideNotificationMethod"] ) )
        sb.AppendLine( "%s=%s" % ("PluginName", jobs[index]["PluginName"] ) )
        sb.AppendLine( "%s=%s" % ("Pool", jobs[index]["Pool"] ) )
        sb.AppendLine( "%s=%s" % ("PostJobScript", jobs[index]["PostJobScript"] ) )
        sb.AppendLine( "%s=%s" % ("PostTaskScript", jobs[index]["PostTaskScript"] ) )
        sb.AppendLine( "%s=%s" % ("PreJobScript", jobs[index]["PreJobScript"] ) )
        sb.AppendLine( "%s=%s" % ("PreTaskScript", jobs[index]["PreTaskScript"] ) )
        sb.AppendLine( "%s=%s" % ("Priority", jobs[index]["Priority"] ) )
        sb.AppendLine( "%s=%s" % ("ReloadRenderer", jobs[index]["ReloadRenderer"] ) )
        sb.AppendLine( "%s=%s" % ("SequentialJobFlag", jobs[index]["SequentialJobFlag"] ) )
        sb.AppendLine( "%s=%s" % ("SlaveTimeoutSeconds", jobs[index]["TaskTimeoutSeconds"] ) )
        sb.AppendLine( "%s=%s" % ("StartedDateTime", jobs[index]["StartedDateTime"] ) )
        sb.AppendLine( "%s=%s" % ("Status", jobs[index]["Status"] ) )
        sb.AppendLine( "%s=%s" % ("SubmitDateTime", jobs[index]["SubmitDateTime"] ) )
        sb.AppendLine( "%s=%s" % ("SubmitMachineName", jobs[index]["SubmitMachineName"] ) )
        sb.AppendLine( "%s=%s" % ("TaskCount", jobs[index]["TaskCount"] ) )
        sb.AppendLine( "%s=%s" % ("TasksQueued", jobs[index]["QueuedChunks"] ) )
        sb.AppendLine( "%s=%s" % ("TasksRendering", jobs[index]["RenderingChunks"] ) )
        sb.AppendLine( "%s=%s" % ("TasksSuspended", jobs[index]["SuspendedChunks"] ) )
        sb.AppendLine( "%s=%s" % ("TasksCompleted", jobs[index]["CompletedChunks"] ) )
        sb.AppendLine( "%s=%s" % ("TasksFailed", jobs[index]["FailedChunks"] ) )
        sb.AppendLine( "%s=%s" % ("UserName", jobs[index]["UserName"] ) )
            
    
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

    sb.Insert( 0, "Disabled Machines: %d\n" % disabledMachines )
    sb.Insert( 0, "Offline Machines: %d\n" % offlineMachines )
    sb.Insert( 0, "Stalled Machines: %d\n" % stalledMachines )
    sb.Insert( 0, "Idle Machines: %d\n" % idleMachines )
    sb.Insert( 0, "Rendering Machines: %d\n" % renderingMachines )
    
    sb.Insert( 0, "Corrupt Jobs: 0\n" )
    sb.Insert( 0, "FailedJobs: %d\n" % failedJobs )
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
