
###############################################################
## Imports
###############################################################
from System.Diagnostics import *
from System.IO import *
from System import TimeSpan

from Deadline.Events import *
from Deadline.Scripting import *

import re
import sys
import os

#################################################################################################
## This is the function called by Deadline to get an instance of the Puppet event listener.
#################################################################################################
def GetDeadlineEventListener():
    return PuppetEventListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The Puppet event listener class.
###############################################################
class PuppetEventListener (DeadlineEventListener):
    def __init__( self ):
        self.OnSlaveIdleCallback += self.OnSlaveIdle
        self.OnSlaveStartedCallback += self.OnSlaveStarted

    def Cleanup( self ):
        del self.OnSlaveIdleCallback
        del self.OnSlaveStartedCallback

    ## This is called when a slave becomes idle.
    def OnSlaveIdle(self, string):
        self.PuppetUpdate()

    def OnSlaveStarted(self, string):
        self.PuppetUpdate

    def PuppetUpdate(self):
        ClientUtils.LogText("Preparing for Puppet Update")
        deadlineBin = ClientUtils.GetBinDirectory()

        puppetPathList = self.GetConfigEntry("PuppetPath")

        puppetPath = FileUtils.SearchFileList( puppetPathList )

        if puppetPath.strip() == "":
            ClientUtils.LogText("Puppet executable was not found in the semicolon separated list \"" + puppetPathList + "\". The path to the executable can be configured from the Event Configuration in the Deadline Monitor.")
            return

        arguments = " agent -t"

        verbose = self.GetBooleanPluginInfoEntryWithDefault("Verbose", False)
        if verbose:
            arguments += " --verbose"

        return self.RunProcess(puppetPath, arguments, deadlineBin, -1)
