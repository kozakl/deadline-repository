##------------------------------------------------------------
## ConnectWithRemoteDesktop.py
## Created November 2, 2012 by Diana Carrier
##
## Balancer List script to connect to remote balancer with Remote Desktop (BalancerScript - Windows only).
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *

import traceback

def __main__():
    # Get the selected balancer infos.
    selectedBalancerInfoSettings = MonitorUtils.GetSelectedBalancerInfoSettings()
    
    # Get the list of selected machine names from the balancer infos.
    machineNames = BalancerUtils.GetMachineNameOrIPAddresses(selectedBalancerInfoSettings)
    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithRemoteDesktop.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main RDC script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
