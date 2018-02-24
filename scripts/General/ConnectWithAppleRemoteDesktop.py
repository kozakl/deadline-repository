##------------------------------------------------------------
## ConnectWithAppleRemoteDesktop.py
## Created October 2, 2013 by Ryan Gagnon
##
## General script to connect to remote slave with Apple Remote Desktop. (GeneralScript)
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
import subprocess
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
    scriptDialog.SetTitle( "Choose Machines to Connect to with ARD" )
    scriptDialog.SetSize(dialogWidth, dialogHeight)
    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "SlavesLabel", "LabelControl", "Machine IP Address(s)", 0, 0, "Specify which machines to connect to. Use a comma to separate multiple machine names.", False)
    scriptDialog.AddControlToGrid( "SlavesBox", "TextControl", "", 0, 1 )
    
    scriptDialog.AddSelectionControlToGrid( "HideWindowBox", "CheckBoxControl", False, "Hide this window if running from a right-click Scripts menu", 1, 0, "If enabled, this window will be hidden if run from a right-click menu in the Monitor. You can always run it from the main Scripts menu to see this window.", colSpan=2 )
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel1", 0, 0 )
    startButton = scriptDialog.AddControlToGrid( "SelectButton", "ButtonControl", "OK", 0, 1, expand=False )
    startButton.ValueModified.connect(connectWithARD)
    closeButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    closeButton.ValueModified.connect(cancelButtonPressed)
    scriptDialog.EndGrid()
    
    settings = ("SlavesBox", "HideWindowBox")
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
        connectWithARD()
    
def getSettingsFilename():
    return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), "RdcSettings.ini" )
    
def cancelButtonPressed():
    global scriptDialog
    global settings
    
    #scriptDialog.SaveSettings(getSettingsFilename(),settings)
    scriptDialog.CloseDialog()

def connectWithARD():
    global scriptDialog
    try:
        if not SystemUtils.IsRunningOnMac():
            scriptDialog.ShowMessageBox("Apple Remote Desktop is only available on Mac OS X.", "Error")
            return
        
        slaves = scriptDialog.GetValue("SlavesBox").strip()
        if slaves == "":
            scriptDialog.ShowMessageBox("Please specify at least one machine IP address.", "Error")
            return
            
            
        cancelButtonPressed()
        
        slaveIPs = slaves.split(",")
        for currSlaveIP in slaveIPs:
            slaveIP = currSlaveIP.strip()
            arguments = "/v:\"%s\"" % slaveIP
            script = ""
            script += 'set theIPAddress to "'
            script += slaveIP
            script += '"\n'
            script += "set numberOfComputers to 0\n"
            script += 'tell application "Remote Desktop"\n'
            script += "    activate\n"
            script += "    set theComputers to (every computer whose Internet address is theIPAddress)\n"
            script += "    set numberOfComputers to (count theComputers)\n"
            script += "    if (numberOfComputers > 0) then\n"
            script += "        control theComputers\n"
            script += "    else\n"
            script += '        error "Remote Desktop has no computers with the IP Address " & theIPAddress\n'
            script += "    end if\n"
            script += "end tell"
            
            osa = subprocess.Popen(['osascript', '-'], stdin=subprocess.PIPE)
            osa.communicate(script)
            time.sleep(0.5)
    except:
        scriptDialog.ShowMessageBox(str(traceback.format_exc()), "Error")
