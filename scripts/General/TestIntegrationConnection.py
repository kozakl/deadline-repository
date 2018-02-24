import os

from System.IO import *

from Deadline.Scripting import *
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

########################################################################
## Globals
########################################################################
scriptDialog = None
shotgunSettings = {}
fTrackSettings = {}
nimSettings = {}
IntegrationOptions = ["Shotgun","FTrack","NIM"]

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__():
    global scriptDialog
    
    scriptDialog = DeadlineScriptDialog()
    scriptDialog.SetTitle( "Test Integration Connection" )
    
    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "Separator", "SeparatorControl", "Project Management", 0, 0, colSpan=4 )
    
    scriptDialog.AddControlToGrid( "IntegrationLabel", "LabelControl", "Project Management", 1, 0, "", False )
    scriptDialog.AddComboControlToGrid( "IntegrationTypeBox", "ComboControl", "Shotgun", IntegrationOptions, 1, 1, expand=False )
    connectButton = scriptDialog.AddControlToGrid( "IntegrationConnectButton", "ButtonControl", "Connect...", 1, 2, expand=False )
    connectButton.ValueModified.connect(ConnectButtonPressed)
    
    scriptDialog.AddControlToGrid( "IntegrationVersionLabel", "LabelControl", "Version", 2, 0, "The Project Management version name.", False )
    scriptDialog.AddControlToGrid( "IntegrationVersionBox", "TextControl", "", 2, 1, colSpan=3 )

    scriptDialog.AddControlToGrid( "IntegrationDescriptionLabel", "LabelControl", "Description", 3, 0, "The Project Management version description.", False )
    scriptDialog.AddControlToGrid( "IntegrationDescriptionBox", "TextControl", "", 3, 1, colSpan=3 )

    scriptDialog.AddControlToGrid( "IntegrationEntityInfoLabel", "LabelControl", "Selected Entity", 4, 0, "Information about the Project Management entity that the version will be created for.", False )
    entityInfoBox = scriptDialog.AddControlToGrid( "IntegrationEntityInfoBox", "MultiLineTextControl", "", 4, 1, colSpan=3 )
    entityInfoBox.ReadOnly = True
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "HSpacer", 0, 0 )
    closeButton = scriptDialog.AddControlToGrid( "CloseButton", "ButtonControl", "Close", 0, 2, expand=False )
    closeButton.ValueModified.connect(scriptDialog.closeEvent)
    scriptDialog.EndGrid()
    
    scriptDialog.ShowDialog( False )
    
def ConnectButtonPressed( *args ):
    global scriptDialog
    script = ""
    projMgmt = scriptDialog.GetValue("IntegrationTypeBox")
    
    if projMgmt == "Shotgun":
        script = RepositoryUtils.GetRepositoryFilePath( "events/Shotgun/ShotgunUI.py", True )
    elif projMgmt == "FTrack":
        script = RepositoryUtils.GetRepositoryFilePath( "submission/FTrack/Main/FTrackUI.py", True )
    elif projMgmt == "NIM":
        script = RepositoryUtils.GetRepositoryFilePath( "events/NIM/NIM_UI.py", True )
    
    output = ClientUtils.ExecuteCommandAndGetOutput( ( "-ExecuteScript", script ) )
    
    updated = ProcessLines( output.splitlines(), projMgmt )
    if updated:
        updateDisplay()
    else:
        # No information or an error occurred in the script
        ClientUtils.LogText( output )

def ProcessLines( lines, projMgmt ):
    global shotgunSettings
    global fTrackSettings
    global nimSettings
    
    tempKVPs = {}
    
    for line in lines:
        line = line.strip()
        tokens = line.split( '=', 1 )
        
        if len( tokens ) > 1:
            key = tokens[0]
            value = tokens[1]
            tempKVPs[key] = value
    if len(tempKVPs)>0:
        if projMgmt == "Shotgun":
            shotgunSettings = tempKVPs
        elif projMgmt == "FTrack":
            fTrackSettings = tempKVPs
        elif projMgmt == "NIM":
            nimSettings = tempKVPs
        return True
    return False

def updateDisplay():
    global fTrackSettings
    global shotgunSettings
    global nimSettings
    
    displayText = ""

    if scriptDialog.GetValue("IntegrationTypeBox") == "Shotgun":
        if 'UserName' in shotgunSettings:
            displayText += "User Name: %s\n" % shotgunSettings[ 'UserName' ]
        if 'TaskName' in shotgunSettings:
            displayText += "Task Name: %s\n" % shotgunSettings[ 'TaskName' ]
        if 'ProjectName' in shotgunSettings:
            displayText += "Project Name: %s\n" % shotgunSettings[ 'ProjectName' ]
        if 'EntityName' in shotgunSettings:
            displayText += "Entity Name: %s\n" % shotgunSettings[ 'EntityName' ]	
        if 'EntityType' in shotgunSettings:
            displayText += "Entity Type: %s\n" % shotgunSettings[ 'EntityType' ]
        if 'DraftTemplate' in shotgunSettings:
            displayText += "Draft Template: %s\n" % shotgunSettings[ 'DraftTemplate' ]
    
        scriptDialog.SetValue( "IntegrationEntityInfoBox", displayText )
        scriptDialog.SetValue( "IntegrationVersionBox", shotgunSettings.get( 'VersionName', "" ) )
        scriptDialog.SetValue( "IntegrationDescriptionBox", shotgunSettings.get( 'Description', "" ) )
    
    elif scriptDialog.GetValue("IntegrationTypeBox") == "FTrack":
        if 'FT_Username' in fTrackSettings:
            displayText += "User Name: %s\n" % fTrackSettings[ 'FT_Username' ]
        if 'FT_TaskName' in fTrackSettings:
            displayText += "Task Name: %s\n" % fTrackSettings[ 'FT_TaskName' ]
        if 'FT_ProjectName' in fTrackSettings:
            displayText += "Project Name: %s\n" % fTrackSettings[ 'FT_ProjectName' ]
    
        scriptDialog.SetValue( "IntegrationEntityInfoBox", displayText )
        scriptDialog.SetValue( "IntegrationVersionBox", fTrackSettings.get( 'FT_AssetName', "" ) )
        scriptDialog.SetValue( "IntegrationDescriptionBox", fTrackSettings.get( 'FT_Description', "" ) )
    
    elif scriptDialog.GetValue("IntegrationTypeBox") == "NIM":
        if 'nim_user' in nimSettings:
            displayText += "User Name: %s\n" % nimSettings[ 'nim_user' ]
        if 'nim_taskID' in nimSettings:
            displayText += "Task Id: %s\n" % nimSettings[ 'nim_taskID' ]
        if 'nim_showName' in nimSettings:
            displayText += "Show Name: %s\n" % nimSettings[ 'nim_showName' ]
    
        scriptDialog.SetValue( "IntegrationEntityInfoBox", displayText )
        scriptDialog.SetValue( "IntegrationVersionBox", nimSettings.get( 'nim_assetName', "" ) )
        scriptDialog.SetValue( "IntegrationDescriptionBox", nimSettings.get( 'nim_description', "" ) )
