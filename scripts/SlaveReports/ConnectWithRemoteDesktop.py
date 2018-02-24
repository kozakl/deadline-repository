##------------------------------------------------------------
## ConnectWithRemoteDesktop.py
## Created November 2, 2012 by Diana Carrier
##
## Slave error report script to connect to remote slave with Remote Desktop (SlaveReport - Windows only).
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

import traceback

def __main__():
    # Get the list of selected reports.
    selectedReports = MonitorUtils.GetSelectedSlaveReports()
    
    # Get the unique slave names for the selected reports.
    slaveNames = []
    for report in selectedReports:
        # Make sure we only keep unique names.
        if report.SlaveName != "" and report.SlaveName != "(no slave)" and report.SlaveName not in slaveNames:
            slaveNames.append(report.SlaveName)
    
    # If no slave names could be extracted, then quit.
    if len(slaveNames) == 0:
        scriptDialog = DeadlineScriptDialog()
        scriptDialog.ShowMessageBox("No slave names could be gathered for the selected reports.", "No Slaves")
        return
    
    # Load the slave infos for the selected slaves.
    slaveInfoSettings = RepositoryUtils.GetSlaveInfoSettings(slaveNames, True)
    
    # Get the list of selected machine names from the slave infos.
    machineNames = SlaveUtils.GetMachineNameOrIPAddresses(slaveInfoSettings)
    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "ConnectWithRemoteDesktop.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)
        
        # Call the main RDC script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
