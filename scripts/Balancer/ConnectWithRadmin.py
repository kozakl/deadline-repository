##------------------------------------------------------------
## ConnectWithRadmin.py
## Created October 19, 2012 by Diana Carrier
##
## Connects to remote slave with Radmin. (BalancerList)
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
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithRadmin.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main Radmin script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
