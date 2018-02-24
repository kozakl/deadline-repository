##------------------------------------------------------------
## SendPopUpMessage.py
## Created October 18, 2013 by Mike Owen
##
## Send pop up message to currently logged in user (SlaveList)
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
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "SendPopUpMessage.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)

        # Call the main SendPopupMessage script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)