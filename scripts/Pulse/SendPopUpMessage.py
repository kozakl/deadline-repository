##------------------------------------------------------------
## SendPopUpMessage.py
## Created October 18, 2013 by Mike Owen
##
## Pulse list script to send pop up message to currently logged in user (PulseList)
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *

import traceback

def __main__():
    # Get the selected pulse infos.
    selectedPulseInfos = MonitorUtils.GetSelectedPulseInfos()
    
    # Get the list of selected machine names from the pulse infos.
    machineNames = PulseUtils.GetMachineNames(selectedPulseInfos)
    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "SendPopUpMessage.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main SendPopupMessage script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
