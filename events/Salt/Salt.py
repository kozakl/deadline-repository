
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

##############################################################################################
## This is the function called by Deadline to get an instance of the Salt event listener.
##############################################################################################
def GetDeadlineEventListener():
    return SaltEventListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The Salt event listener class.
###############################################################
class SaltEventListener (DeadlineEventListener):
    def __init__( self ):
        self.OnSlaveIdleCallback += self.OnSlaveIdle
        self.OnSlaveStartedCallback += self.OnSlaveStarted

    def Cleanup( self ):
        del self.OnSlaveIdleCallback
        del self.OnSlaveStartedCallback

    ## This is called when a slave becomes idle.
    def OnSlaveIdle(self, string):
        self.SaltUpdate()

    def OnSlaveStarted(self, string):
        self.SaltUpdate()

    def SaltUpdate(self):
        ClientUtils.LogText("Preparing for Salt Update")
        deadlineBin = ClientUtils.GetBinDirectory()

        saltExeList = self.GetConfigEntry("SaltExe")

        saltExe = FileUtils.SearchFileList( saltExeList )

        if saltExe.strip() == "":
            ClientUtils.LogText("Salt executable was not found in the semicolon separated list \"" + saltExeList + "\". The path to the executable can be configured from the Event Configuration in the Deadline Monitor.")
            return

        arguments = " state.highstate"

        logging = self.GetConfigEntry("Logging")
        arguments += " -l \"%s\"" % logging

        return self.RunProcess(saltExe, arguments, deadlineBin, -1)
