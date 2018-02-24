##------------------------------------------------------------
## ConnectWithVNC.py
## Created October 19, 2012 by Diana Carrier
##
## Connects to remote slave with VNC. (SlaveList)
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
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithVNC.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main VNC script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
