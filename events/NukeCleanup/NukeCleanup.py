###############################################################
## Imports
###############################################################
import os

from Deadline.Events import *
from Deadline.Scripting import *

###############################################################
## Give Deadline an instance of this class so it can use it.
###############################################################
def GetDeadlineEventListener():
    return NukeTmpFilesCleanUpListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The NukeTmpFilesCleanUpListener event listener class.
###############################################################
class NukeTmpFilesCleanUpListener ( DeadlineEventListener ):
    def __init__( self ):
        self.OnJobFinishedCallback += self.OnJobFinished
        self.OnJobStartedCallback += self.OnJobStarted

    def Cleanup( self ):
        del self.OnJobFinishedCallback
        del self.OnJobStartedCallback

    def OnJobStarted( self, job ):
        eventType = self.GetConfigEntryWithDefault( "CleanTmpFilesEvent", "On Job Started" )

        if 'Nuke' in job.PluginName and ( eventType == "On Job Started" or eventType == "On Job Started and On Job Finished" ):
            self.LogInfo( "[ER] - Job started, cleaning up Temp files" )
            self.RemoveFiles( job )

    def OnJobFinished( self, job ):
        eventType = self.GetConfigEntryWithDefault( "CleanTmpFilesEvent", "On Job Started" )

        if 'Nuke' in job.PluginName and ( eventType == "On Job Finished" or eventType == "On Job Started and On Job Finished" ):
            self.LogInfo( "[ER] - Job finished, cleaning up Temp files" )
            self.RemoveFiles( job )
    
    def RemoveFiles( self, job ):
        self.LogInfo( "[ER] - Cleaning up of *.tmp files started" )

        removed = 0
        i = 0

        for d in job.JobOutputDirectories:
            self.LogInfo( "[ER] - Cleaning %s" % d )

            for i, f in enumerate( os.listdir( os.path.realpath( d ) ) ):
                if os.path.splitext( f )[-1] == ".tmp":
                    try:
                        tmpfile = os.path.join( d, f )
                        os.remove( tmpfile )
                        removed += 1
                    except OSError:
                        self.LogWarning( "[ER] - Can't delete: %s" % tmpfile )

        self.LogInfo( "[ER] - Total files %s - Temp files removed: %s" % ( i, removed ) )
        self.LogInfo( "[ER] - Cleaning up of *.tmp files finished" )