##------------------------------------------------------------
## ConnectWithRemoteDesktop.py
## Created November 2, 2012 by Diana Carrier
##
## Slave List script to connect to remote slave with Remote Desktop (Windows only).
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *

import traceback

def __main__():
    # Get the selected slave info settings.
    selectedSlaveInfoSettings = MonitorUtils.GetSelectedSlaveInfoSettings()
    
    # Get the list of selected machine names from the slave info settings.
    machineNames = SlaveUtils.GetMachineNameOrIPAddresses(selectedSlaveInfoSettings)
    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithRemoteDesktop.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main RDC script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
