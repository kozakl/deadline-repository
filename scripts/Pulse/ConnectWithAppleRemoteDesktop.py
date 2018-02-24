##------------------------------------------------------------
## ConnectWithAppleRemoteDesktop.py
## Created October 2, 2013 by Ryan Gagnon
##
## Pulse script to connect to remote slave with Apple Remote Desktop. (PulseScript)
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *

import traceback

def __main__():
    # Get the selected pulse infos.
    selectedPulseInfoSettings = MonitorUtils.GetSelectedPulseInfoSettings()
    
    # Get the list of selected machine names from the pulse infos.
    machineIPs = PulseUtils.GetMachineNameOrIPAddresses(selectedPulseInfoSettings)
    if len(machineIPs) > 0:
        ipList = ",".join(machineIPs)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithAppleRemoteDesktop.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main RDC script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, ipList)