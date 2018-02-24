##------------------------------------------------------------
## SendPopUpMessage.py
## Created October 18, 2013 by Mike Owen
##
## Balancer list script to send pop up message to currently logged in user (BalancerList)
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *

import traceback

def __main__():
    # Get the selected balancer infos.
    selectedBalancerInfos = MonitorUtils.GetSelectedBalancerInfos()
    
    # Get the list of selected machine names from the balancer infos.
    machineNames = BalancerUtils.GetMachineNames(selectedBalancerInfos)
    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "SendPopUpMessage.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main SendPopupMessage script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
