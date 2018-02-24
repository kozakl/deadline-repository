##------------------------------------------------------------
## StartOrStopService.py
## Created September 28, 2008 by Ryan Russell
##
## Starts or stops the specified service on the selected machines.
##------------------------------------------------------------

from System.IO import *
from Deadline.Scripting import *

from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

scriptDialog = None

def __main__():
    global scriptDialog
    
    scriptDialog = DeadlineScriptDialog()
    scriptDialog.SetSize( 450, 68 )
    scriptDialog.AllowResizingDialog( False )
    scriptDialog.SetTitle( "Start/Stop Service (For Windows Only)" )
    
    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "NameLabel", "LabelControl", "Service Name", 0, 0, "The name of the Windows Service to start or stop.", False )
    scriptDialog.AddControlToGrid( "NameBox", "TextControl", "", 0, 1 )
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel1", 0, 0 )
    startButton = scriptDialog.AddControlToGrid( "StartButton", "ButtonControl", "Start", 0, 1, expand=False )
    startButton.ValueModified.connect(StartButtonPressed)
    stopButton = scriptDialog.AddControlToGrid( "StopButton", "ButtonControl", "Stop", 0, 2, expand=False )
    stopButton.ValueModified.connect(StopButtonPressed)
    closeButton = scriptDialog.AddControlToGrid( "CloseButton", "ButtonControl", "Close", 0, 3, expand=False )
    closeButton.ValueModified.connect(CloseButtonPressed)
    scriptDialog.EndGrid()
    
    scriptDialog.ShowDialog( True )

def StartButtonPressed( *args ):
    global scriptDialog
    
    serviceName = scriptDialog.GetValue( "NameBox" ).strip()
    if serviceName == "":
        scriptDialog.ShowMessageBox( "Please specify a service name.", "Error" )
    else:
        selectedSlaveInfoSettings = MonitorUtils.GetSelectedSlaveInfoSettings()
    
        # Get the list of selected machine names from the slave info settings.
        machineNames = SlaveUtils.GetMachineNameOrIPAddresses(selectedSlaveInfoSettings)
        for machineName in machineNames:
            SlaveUtils.SendRemoteCommand( machineName, "Execute cmd /C net start \"" + serviceName + "\"" )

def StopButtonPressed( *args ):
    global scriptDialog
    
    serviceName = scriptDialog.GetValue( "NameBox" )
    if serviceName == "":
        scriptDialog.ShowMessageBox( "Please specify a service name.", "Error" )
    else:
        selectedSlaveInfoSettings = MonitorUtils.GetSelectedSlaveInfoSettings()
    
        # Get the list of selected machine names from the slave info settings.
        machineNames = SlaveUtils.GetMachineNameOrIPAddresses(selectedSlaveInfoSettings)
        for machineName in machineNames:
            SlaveUtils.SendRemoteCommand( machineName, "Execute cmd /C net stop \"" + serviceName + "\"" )

def CloseButtonPressed( *args ):
    global scriptDialog
    scriptDialog.CloseDialog()
