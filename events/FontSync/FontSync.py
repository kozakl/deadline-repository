###############################################################
## Imports
###############################################################
from System import *
from System.Diagnostics import *
from System.IO import *
from System.Text.RegularExpressions import *

from Deadline.Events import *
from Deadline.Scripting import *

###############################################################
## Give Deadline an instance of this class so it can use it.
###############################################################
def GetDeadlineEventListener():
    return FontSyncListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()
    
###############################################################
## The FontSync event listener class.
###############################################################
class FontSyncListener (DeadlineEventListener):
    def __init__( self ):

        self.OnSlaveStartingJobCallback += self.SlaveStartedJob
        self.OnSlaveStartedCallback += self.SlaveStarted
    
    def Cleanup( self ):
        del self.OnSlaveStartedCallback
        del self.OnSlaveStartingJobCallback
            
    def SlaveStartedJob(self, slaveName, job):

        eventType = self.GetConfigEntryWithDefault( "SyncEvent", "On Slave Job Started" )
        if eventType == "On Slave Job Started":
            self.SyncFont()
            
    def SlaveStarted(self, slaveName):
        
        eventType = self.GetConfigEntryWithDefault( "SyncEvent", "On Slave Job Started" )
        if eventType != "On Slave Job Started":
            self.SyncFont()
        
    def SyncFont(self):
        # Perform font folder synchronization if necessary.
        networkFontFolder = ""
        localFontFolderList = ""

        if SystemUtils.IsRunningOnWindows():
            networkFontFolder = self.GetConfigEntryWithDefault( "FontFolderNetworkWindows", "" )
            if self.GetBooleanConfigEntryWithDefault( "UseTempFontFolderWindows", False ):
                localFontFolderList = Path.Combine( Path.GetTempPath(), "DeadlineFonts" )
                if not Directory.Exists( localFontFolderList ):
                    Directory.CreateDirectory( localFontFolderList )
            else:
                localFontFolderList = self.GetConfigEntryWithDefault( "FontFolderWindows", "" )
        elif SystemUtils.IsRunningOnMac():
            networkFontFolder = self.GetConfigEntryWithDefault( "FontFolderNetworkMacOSX", "" )
            localFontFolderList = self.GetConfigEntryWithDefault( "FontFolderMacOSX", "" )
            
        timeoutValue = self.GetIntegerConfigEntryWithDefault("FontSyncTimeout", 1000 )
        if len(networkFontFolder) > 0:
            self.LogInfo( "Synchronizing with network Font folder '" + networkFontFolder + "'" )
            if not Directory.Exists( networkFontFolder ):
                self.FailRender( "Could not synchronize with network Font folder '" + networkFontFolder + "' because it does not exist" )
            
            localFontFolder = DirectoryUtils.SearchDirectoryList( localFontFolderList )
            if( localFontFolder == "" ):
                self.FailRender( "Could not synchronize with network Font folder because a local Font folder was not found in the semicolon separated list '" + localFontFolderList + "'" )
            
            self.LogInfo( "Synchronizing to local Font folder '" + localFontFolder + "'" )
            
            fontFiles = Directory.GetFiles( networkFontFolder )
            if len( fontFiles ) > 0:
                if SystemUtils.IsRunningOnWindows():
                    skipExisting = self.GetBooleanConfigEntryWithDefault("SkipExisting", False )
                    DirectoryUtils.SynchronizeFiles( fontFiles, localFontFolder, skipExisting )
                    
                    fontFilesToRegister = []
                    for fontFile in fontFiles:
                        localFontFile = Path.Combine( localFontFolder, Path.GetFileName( fontFile ) )
                        fontFilesToRegister.append(localFontFile)
                    
                    PathUtils.RegisterFonts( fontFilesToRegister, timeoutValue )
                    
                elif SystemUtils.IsRunningOnMac():
                    rsync = PathUtils.GetApplicationPath( "rsync" )
                    if rsync == "":
                        self.LogWarning( "rsync could not be found in the PATH, skipping Font synchronization" )
                    else:
                        arguments = "-vaE"
                        for fontFile in fontFiles:
                            arguments = arguments + " \"" + fontFile + "\""
                        arguments = arguments + " \"" + localFontFolder + "\""
                        self.RunProcess( rsync, arguments, "", -1 )
            else:
                self.LogInfo( "There are no fonts in network Font folder '" + networkFontFolder + "'" )
