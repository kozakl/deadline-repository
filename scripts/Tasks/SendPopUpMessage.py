##------------------------------------------------------------
## SendPopUpMessage.py
## Created October 21, 2013 by Mike Owen
##
## Send pop up message to currently logged in user (Task)
##------------------------------------------------------------
from System.IO import *
from Deadline.Scripting import *
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

import traceback

def __main__():

    global scriptDialog

    # Get the list of selected tasks.
    selectedTasks = MonitorUtils.GetSelectedTasks()
    
    # Get the unique slave names for the selected tasks.
    slaveNames = []
    for task in selectedTasks:
        # Only check completed or rendering tasks.
        if task.TaskStatus == "Completed" or task.TaskStatus == "Rendering":
            # Make sure we only keep unique names.
            if task.TaskSlaveName != "" and task.TaskSlaveName not in slaveNames:
                slaveNames.append(task.TaskSlaveName)
    
    # If no slave names could be extracted, then quit.
    if len(slaveNames) == 0:
        scriptDialog = DeadlineScriptDialog()
        scriptDialog.ShowMessageBox("No slave names could be gathered for the selected tasks. Check that the selected tasks are Rendering or Completed.", "No Slaves")
        return

    # Load the slave infos for the selected slaves.
    slaveInfos = RepositoryUtils.GetSlaveInfos(slaveNames, True)
    
    # Get the list of selected machine names from the slave infos.
    machineNames = SlaveUtils.GetMachineNames(slaveInfos)

    if len(machineNames) > 0:
        nameList = ",".join(machineNames)
        generalScript = Path.Combine(RepositoryUtils.GetRootDirectory("scripts/General"), "SendPopUpMessage.py")
        generalScript = PathUtils.ToPlatformIndependentPath(generalScript)

        # Call the main SendPopupMessage script and pass the list of machine names.
        ClientUtils.ExecuteScript(generalScript, nameList)
