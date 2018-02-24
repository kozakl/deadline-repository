##------------------------------------------------------------
## ConnectWithRemoteDesktop.py
## Created November 2, 2012 by Diana Carrier
##
## Pulse List script to connect to remote pulse with Remote Desktop (PulseScript - Windows only).
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *

import traceback

def __main__():
    # Get the selected pulse infos.
    selectedPulseInfoSettings = MonitorUtils.GetSelectedPulseInfoSettings()
    
    # Get the list of selected machine names from the pulse infos.
    machineNames = PulseUtils.GetMachineNameOrIPAddresses(selectedPulseInfoSettings)
    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithRemoteDesktop.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main RDC script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
