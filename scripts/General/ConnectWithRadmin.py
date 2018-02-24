##------------------------------------------------------------
## ConnectWithRadmin.py
## Created October 30, 2012 by Diana Carrier
##
## General script to connect to remote slave with Radmin. (GeneralScript)
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
    scriptDialog.SetTitle( "Choose Machines to Connect to with Radmin" )
    
    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "SlavesLabel", "LabelControl", "Machine Name(s)", 0, 0, "Specify which machines to connect to. Use a comma to separate multiple machine names.", False)
    scriptDialog.AddControlToGrid( "SlavesBox", "TextControl", "", 0, 1, colSpan=2 )

    scriptDialog.AddControlToGrid( "ExeLabel", "LabelControl", "Radmin Viewer", 1, 0, "The Radmin viewer executable to use.", False )
    scriptDialog.AddSelectionControlToGrid( "ExeBox", "FileBrowserControl", "", "All Files (*)", 1, 1, colSpan=2 )

    scriptDialog.AddControlToGrid( "PortLabel", "LabelControl", "Radmin Port", 2, 0, "The Radmin port.", False )
    scriptDialog.AddRangeControlToGrid( "PortBox", "RangeControl", 4899, 1, 65536, 0, 1, 2, 1 )
    scriptDialog.AddHorizontalSpacerToGrid("HSpacer1", 2, 2)

    scriptDialog.AddSelectionControlToGrid( "HideWindowBox", "CheckBoxControl", False, "Hide this window if running from a right-click Scripts menu", 3, 0, "If enabled, this window will be hidden if run from a right-click menu in the Monitor. You can always run it from the main Scripts menu to see this window.", colSpan=2 )
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel1", 0, 0 )
    startButton = scriptDialog.AddControlToGrid( "SelectButton", "ButtonControl", "OK", 0, 1, expand=False )
    startButton.ValueModified.connect(connectWithRadmin)
    closeButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    closeButton.ValueModified.connect(cancelButtonPressed)
    scriptDialog.EndGrid()
    
    settings = ("SlavesBox","PortBox","ExeBox", "HideWindowBox")
    scriptDialog.LoadSettings( getSettingsFilename(), settings )
    scriptDialog.EnabledStickySaving( settings, getSettingsFilename() )
        
    showWindow = True
    if len(args) > 0:
        scriptDialog.SetValue( "SlavesBox", args[0] )
        
        if scriptDialog.GetValue("HideWindowBox"):
            showWindow = False
        
    if showWindow:
        scriptDialog.ShowDialog( True )
    else:
        connectWithRadmin()

def getSettingsFilename():
    return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), "RadminSettings.ini" )
    
def cancelButtonPressed():
    global scriptDialog
    global settings
    
    #scriptDialog.SaveSettings(getSettingsFilename(),settings)
    scriptDialog.CloseDialog()

def connectWithRadmin():
    global scriptDialog
    try:
        system = platform.system()
        if system != 'Windows':
            scriptDialog.ShowMessageBox("Radmin is only available on Windows.", "Error")
            return
            
        slaves = scriptDialog.GetValue("SlavesBox").strip()
        if slaves == "":
            scriptDialog.ShowMessageBox("Please specify at least one machine name.", "Error")
            return
        
        radminViewer = scriptDialog.GetValue("ExeBox").strip()
        if not File.Exists( radminViewer ):
            scriptDialog.ShowMessageBox("The specified Radmin Viewer does not exist.", "Error")
            return
    
        port = scriptDialog.GetValue("PortBox")
            
        cancelButtonPressed()
        
        slaveNames = slaves.split(",")
        for currSlaveName in slaveNames:
            slaveName = currSlaveName.strip()
            arguments = "/connect:%s:%s" % (slaveName,port)
            ProcessUtils.SpawnProcess(radminViewer, arguments)
            time.sleep(0.50)
        
    except:
        scriptDialog.ShowMessageBox(str(traceback.format_exc()), "Error")
