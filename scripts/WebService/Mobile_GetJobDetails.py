from System.IO import *
from System.Security import *
from System.Text import *

from Deadline.Scripting import *

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__( dlArgs, qsArgs ):
    returnVal = ""
    
    jobId = ""
    nonplist = None
    
    # The jobId doesn't have a proper key, which is why we do the following.
    for key in qsArgs.keys():
        if key == "plist":
            nonplist = qsArgs[key]
        elif key.lower() == "jobid":
            jobId = qsArgs[key]
        else:
            jobId = key
    
    # Get the job from pulse
    job = WebServiceUtils.GetJobInfo(jobId)
    
    sb = StringBuilder()

    if ( nonplist != None ):
        # Add the PList header stuff
        sb.AppendLine( "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" )
        sb.AppendLine( "<jobDetails>" )
        
        if ( job != None ):
            sb.AppendLine( "\t<name>" + SecurityElement.Escape( job["Name"] ) + "</name>" )
            sb.AppendLine( "\t<comment>" + SecurityElement.Escape( job["Comment"] ) + "</comment>" )
            sb.AppendLine( "\t<plugin>" + job["PluginName"] + "</plugin>" )
            sb.AppendLine( "\t<uname>" + job["UserName"] + "</uname>" )
            sb.AppendLine( "\t<status>" + job["Status"] + "</status>" )
            sb.AppendLine( "\t<priority>" + job["Priority"] + "</priority>" )
            sb.AppendLine( "\t<jobid>" + job["JobId"] + "</jobid>" )
            sb.AppendLine( "\t<submit>" + job["SubmitDateTimeString"] + "</submit>" )
            sb.AppendLine( "\t<department>" + SecurityElement.Escape( job["Department"] ) + "</department>" )
            sb.AppendLine( "\t<frameslist>" + job["FramesList"] + "</frameslist>" )
            sb.AppendLine( "\t<taskcount>" + job["TaskCount"] + "</taskcount>" )
            sb.AppendLine( "\t<pool>" + job["Pool"] + "</pool>" )
            sb.AppendLine( "\t<group>" + job["Group"] + "</group>" )
            sb.AppendLine( "\t<completed>" + job["CompletedChunks"] + "</completed>" )
            sb.AppendLine( "\t<queued>" + job["QueuedChunks"] + "</queued>" )
            sb.AppendLine( "\t<suspended>" + job["SuspendedChunks"] + "</suspended>" )
            sb.AppendLine( "\t<rendering>" + job["RenderingChunks"] + "</rendering>" )
            sb.AppendLine( "\t<failed>" + job["FailedChunks"] + "</failed>" )
            sb.AppendLine( "\t<pending>" + job["PendingChunks"] + "</pending>" )
            sb.AppendLine( "\t<errors>" + job["ErrorReports"] + "</errors>" )
            
        else:
            sb.AppendLine( "<string>The selected job does not exist, please refresh the job list.</string>" )
        
        # Close all of the tags
        sb.AppendLine( "</jobDetails>" )

        returnVal = sb.ToString()
        
    else:		
        # Add the PList header stuff
        sb.AppendLine( "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" )
        sb.AppendLine( "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">" )
        sb.AppendLine( "<plist version=\"1.0\">" )
        sb.AppendLine( "<dict>" )
        
        if ( job != None ):
            # Make the jobdetails dictionary
            sb.AppendLine( "\t<key>jobdetails</key>" )
            sb.AppendLine( "\t<dict>" )
            
            # Add data to the dictionary
            sb.AppendLine( "\t\t<key>name</key><string>" + SecurityElement.Escape( job["Name"] ) + "</string>" )
            sb.AppendLine( "\t\t<key>comment</key><string>" + SecurityElement.Escape( job["Comment"] ) + "</string>" )
            sb.AppendLine( "\t\t<key>plugin</key><string>" + job["PluginName"] + "</string>" )
            sb.AppendLine( "\t\t<key>uname</key><string>" + job["UserName"] + "</string>" )
            sb.AppendLine( "\t\t<key>status</key><string>" + job["Status"] + "</string>" )
            sb.AppendLine( "\t\t<key>priority</key><string>" + job["Priority"] + "</string>" )
            sb.AppendLine( "\t\t<key>jobid</key><string>" + job["JobId"] + "</string>" )
            sb.AppendLine( "\t\t<key>submit</key><string>" + job["SubmitDateTimeString"] + "</string>" )
            sb.AppendLine( "\t\t<key>department</key><string>" + SecurityElement.Escape( job["Department"] ) + "</string>" )
            sb.AppendLine( "\t\t<key>frameslist</key><string>" + job["FramesList"] + "</string>" )
            sb.AppendLine( "\t\t<key>taskcount</key><string>" + job["TaskCount"] + "</string>" )
            sb.AppendLine( "\t\t<key>pool</key><string>" + job["Pool"] + "</string>" )
            sb.AppendLine( "\t\t<key>group</key><string>" + job["Group"] + "</string>" )
            sb.AppendLine( "\t\t<key>completed</key><string>" + job["CompletedChunks"] + "</string>" )
            sb.AppendLine( "\t\t<key>queued</key><string>" + job["QueuedChunks"] + "</string>" )
            sb.AppendLine( "\t\t<key>suspended</key><string>" + job["SuspendedChunks"] + "</string>" )
            sb.AppendLine( "\t\t<key>rendering</key><string>" + job["RenderingChunks"] + "</string>" )
            sb.AppendLine( "\t\t<key>failed</key><string>" + job["FailedChunks"] + "</string>" )
            sb.AppendLine( "\t\t<key>pending</key><string>" + job["PendingChunks"] + "</string>" )
            sb.AppendLine( "\t\t<key>errors</key><string>" + job["ErrorReports"] + "</string>" )
            
            sb.AppendLine( "\t</dict>" )
        else:
            sb.AppendLine( "<key>invalid</key>" )
            sb.AppendLine( "<string>The selected job does not exist, please refresh the job list.</string>" )
        
        # Close all of the tags
        sb.AppendLine( "</dict>" )
        sb.AppendLine( "</plist>" )

        returnVal = sb.ToString()
    
    return returnVal
