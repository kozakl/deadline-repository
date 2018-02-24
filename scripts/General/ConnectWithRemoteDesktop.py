##------------------------------------------------------------
## ConnectWithRemoteDesktop.py
## Created November 2, 2012 by Diana Carrier
##
## General script to connect to remote slave with Remote Desktop (GeneralScript - Windows only).
##------------------------------------------------------------
from System import *
from System.Collections.Specialized import *
from System.IO import *
from System.Text import *
from System.Diagnostics import ProcessWindowStyle
from Deadline.Scripting import *

import os
import traceback
import platform
import time

from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

scriptDialog = None
settings = None

def __main__(*args):
    global scriptDialog
    global settings

    dialogWidth = 450
    dialogHeight = 0

    scriptDialog = DeadlineScriptDialog()
    scriptDialog.SetSize(dialogWidth, dialogHeight)
    scriptDialog.SetTitle( "Choose Machines to Connect to with RDC" )
    
    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "SlavesLabel", "LabelControl", "Machine Name(s)", 0, 0, "Specify which machines to connect to. Use a comma to separate multiple machine names.", False )
    scriptDialog.AddControlToGrid( "SlavesBox", "TextControl", "", 0, 1 )
    
    noSettingsBox = scriptDialog.AddRadioControlToGrid( "NoSettingsBox", "RadioControl", True, "No Settings", "RadioGroup", 1, 0, "When this option is chosen, no existing RDP settings are used to connect.", False )
    noSettingsBox.ValueModified.connect(settingsChanged)
    
    useSettingsFileBox = scriptDialog.AddRadioControlToGrid( "UseSettingsFileBox", "RadioControl", False, "Settings File", "RadioGroup", 2, 0, "When this option is chosen, the specified RDP config file is used to connect.", False )
    useSettingsFileBox.ValueModified.connect(settingsChanged)
    scriptDialog.AddSelectionControlToGrid( "SettingsFileBox", "FileBrowserControl", "", "RDP Files (*.rdp);;All Files (*.*)", 2, 1 )
    
    useSettingsFolderBox = scriptDialog.AddRadioControlToGrid( "UseSettingsDirBox", "RadioControl", False, "Settings Folder", "RadioGroup", 3, 0, "When this option is enabled, existing RDP config files in this folder are used to connect. If the machine does not have an RDP config file, you'll have the option to save one before connecting.", False )
    useSettingsFolderBox.ValueModified.connect(settingsChanged)
    scriptDialog.AddSelectionControlToGrid( "SettingsDirBox", "FolderBrowserControl", "", "", 3, 1 )
    
    scriptDialog.AddSelectionControlToGrid( "HideWindowBox", "CheckBoxControl", False, "Hide this window if running from a right-click Scripts menu", 4, 0, "If enabled, this window will be hidden if run from a right-click menu in the Monitor. You can always run it from the main Scripts menu to see this window.", colSpan=2 )
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel1", 0, 0 )
    startButton = scriptDialog.AddControlToGrid( "SelectButton", "ButtonControl", "OK", 0, 1, expand=False )
    startButton.ValueModified.connect(connectWithRDC)
    closeButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    closeButton.ValueModified.connect(cancelButtonPressed)
    scriptDialog.EndGrid()
    
    settings = ("SlavesBox", "NoSettingsBox", "UseSettingsFileBox", "SettingsFileBox", "UseSettingsDirBox", "SettingsDirBox", "HideWindowBox")
    scriptDialog.LoadSettings( getSettingsFilename(), settings )
    scriptDialog.EnabledStickySaving( settings, getSettingsFilename() )
    
    settingsChanged()
        
    showWindow = True
    if len(args) > 0:
        scriptDialog.SetValue( "SlavesBox", args[0] )
        
        if scriptDialog.GetValue("HideWindowBox"):
            showWindow = False
    
    if showWindow:
        scriptDialog.ShowDialog( True )
    else:
        autoConnect = True
        
        # Check if there are any issues accessing the settings file or folder.
        if scriptDialog.GetValue( "UseSettingsFileBox" ):
            settingsFile = scriptDialog.GetValue( "SettingsFileBox" )
            if not File.Exists( settingsFile ):
                scriptDialog.ShowMessageBox("The specified settings file '%s' does not exist." % settingsFile, "Error")
                autoConnect = False
        elif scriptDialog.GetValue( "UseSettingsDirBox" ):
            settingsDir = scriptDialog.GetValue( "SettingsDirBox" )
            if not Directory.Exists( settingsDir ):
                scriptDialog.ShowMessageBox("The specified settings folder '%s' does not exist." % settingsDir, "Error")
                autoConnect = False
        
        # If errors prevent auto-connect from working, just display the window.
        if autoConnect:
            connectWithRDC()
        else:
            scriptDialog.ShowDialog( True )
    
def getSettingsFilename():
    return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), "RdcSettings.ini" )
    
def cancelButtonPressed():
    global scriptDialog
    global settings
    
    #scriptDialog.SaveSettings(getSettingsFilename(),settings)
    scriptDialog.CloseDialog()

def settingsChanged():
    global scriptDialog
    
    scriptDialog.SetEnabled( "SettingsFileBox", scriptDialog.GetValue( "UseSettingsFileBox" ) )
    scriptDialog.SetEnabled( "SettingsDirBox", scriptDialog.GetValue( "UseSettingsDirBox" ) )

def connectWithRDC():
    global scriptDialog
    try:
        system = platform.system()
        if system != 'Windows':
            scriptDialog.ShowMessageBox("RDC is only available on Windows.", "Error")
            return
        
        # Check if there are any issues accessing the settings file or folder.
        if scriptDialog.GetValue( "UseSettingsFileBox" ):
            settingsFile = scriptDialog.GetValue( "SettingsFileBox" )
            if not File.Exists( settingsFile ):
                scriptDialog.ShowMessageBox("The specified settings file '%s' does not exist." % settingsFile, "Error")
                return
        elif scriptDialog.GetValue( "UseSettingsDirBox" ):
            settingsDir = scriptDialog.GetValue( "SettingsDirBox" )
            if not Directory.Exists( settingsDir ):
                scriptDialog.ShowMessageBox("The specified settings folder '%s' does not exist." % settingsDir, "Error")
                return
        
        slaves = scriptDialog.GetValue("SlavesBox").strip()
        if slaves == "":
            scriptDialog.ShowMessageBox("Please specify at least one machine name.", "Error")
            return
            
        rdcViewer = Path.Combine(Environment.SystemDirectory, "mstsc.exe")
        if not File.Exists( rdcViewer ):
            scriptDialog.ShowMessageBox("The RDC executable 'mstsc.exes' coult not be found in %s." % Environment.SystemDirectory, "Error")
            return
            
        cancelButtonPressed()
        
        slaveNames = slaves.split(",")
        for currSlaveName in slaveNames:
            slaveName = currSlaveName.strip()
            arguments = "/v:\"%s\"" % slaveName
            
            if scriptDialog.GetValue( "UseSettingsFileBox" ):
                # If a settings file is specified, prepend it to the arguments.
                settingsFile = scriptDialog.GetValue( "SettingsFileBox" )
                arguments = "\"" + settingsFile + "\" " + arguments
            
            elif scriptDialog.GetValue( "UseSettingsDirBox" ):
                # If a settings folder is specified, we either create it if it doesn't exist, or prepend it to the arguments.
                settingsDir = scriptDialog.GetValue( "SettingsDirBox" )
                settingsFile = Path.Combine( settingsDir, slaveName + ".rdp" )
                if not File.Exists( settingsFile ):
                    File.WriteAllText( settingsFile, "full address:s:" + slaveName )
                    arguments = "/edit \"" + settingsFile + "\""
                else:
                    arguments = "\"" + settingsFile + "\" " + arguments
            
            ProcessUtils.SpawnProcess(rdcViewer, arguments)
            time.sleep(0.50)
        
    except:
        scriptDialog.ShowMessageBox(str(traceback.format_exc()), "Error")
