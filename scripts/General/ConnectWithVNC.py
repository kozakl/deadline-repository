##------------------------------------------------------------
## ConnectWithVNC.py
## Created October 30, 2012 by Diana Carrier
##
## General script to connect to remote slave with VNC. (GeneralScript)
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
    scriptDialog.SetTitle( "Choose Machines to Connect to with VNC" )
    
    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "SlavesLabel", "LabelControl", "Machine Name(s)", 0, 0, "Specify which machines to connect to. Use a comma to separate multiple machine names.", False )
    scriptDialog.AddControlToGrid( "SlavesBox", "TextControl", "", 0, 1, colSpan=2 )

    scriptDialog.AddControlToGrid( "ExeLabel", "LabelControl", "VNC Viewer", 1, 0, "The VNC viewer executable to use.", False )
    scriptDialog.AddSelectionControlToGrid( "ExeBox", "FileBrowserControl", "", "All Files (*)", 1, 1, colSpan=2 )

    scriptDialog.AddControlToGrid( "PasswordLabel", "LabelControl", "Password", 2, 0, "The VNC password.", False )
    scriptDialog.AddControlToGrid( "PasswordBox", "PasswordControl", "", 2, 1, colSpan=2 )

    scriptDialog.AddControlToGrid( "PortLabel", "LabelControl", "VNC Port", 3, 0, "The VNC port.", False )
    scriptDialog.AddRangeControlToGrid( "PortBox", "RangeControl", 5900, 1, 65536, 0, 1, 3, 1, expand=False )
    scriptDialog.AddSelectionControlToGrid( "RememberPasswordBox", "CheckBoxControl", False, "Remember Password", 3, 2, "Enable to remember your password between sessions." )
    
    scriptDialog.AddSelectionControlToGrid( "HideWindowBox", "CheckBoxControl", False, "Hide this window if running from a right-click Scripts menu", 4, 0, "If enabled, this window will be hidden if run from a right-click menu in the Monitor. You can always run it from the main Scripts menu to see this window.", colSpan=3 )
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel1", 0, 0 )
    startButton = scriptDialog.AddControlToGrid( "SelectButton", "ButtonControl", "OK", 0, 1, expand=False )
    startButton.ValueModified.connect(connectWithVNC)
    closeButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    closeButton.ValueModified.connect(cancelButtonPressed)
    scriptDialog.EndGrid()
    
    settings = ("SlavesBox","PortBox","ExeBox","RememberPasswordBox","PasswordBox", "HideWindowBox")
    scriptDialog.LoadSettings( getSettingsFilename(), settings )
    scriptDialog.EnabledStickySaving( settings, getSettingsFilename() )
    
    if not scriptDialog.GetValue("RememberPasswordBox"):
        scriptDialog.SetValue("PasswordBox", "")
    
    showWindow = True
    if len(args) > 0:
        scriptDialog.SetValue( "SlavesBox", args[0] )
        
        if scriptDialog.GetValue("HideWindowBox"):
            showWindow = False
        
    if showWindow:
        scriptDialog.ShowDialog( True )
    else:
        connectWithVNC()

def getSettingsFilename():
    return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), "VncSettings.ini" )
    
def cancelButtonPressed():
    global scriptDialog
    global settings
    
    if not scriptDialog.GetValue("RememberPasswordBox"):
        scriptDialog.SetValue("PasswordBox", "")
    
    #scriptDialog.SaveSettings(getSettingsFilename(),settings)
    scriptDialog.CloseDialog()

def connectWithVNC():
    global scriptDialog
    try:
        system = platform.system()
        
        slaves = scriptDialog.GetValue("SlavesBox").strip()
        if slaves == "":
            scriptDialog.ShowMessageBox("Please specify at least one machine name.", "Error")
            return
        
        vncViewer = scriptDialog.GetValue("ExeBox").strip()
        if system == 'Linux' and len(vncViewer) == 0:
            vncViewer = PathUtils.GetApplicationPath("vncviewer")
            if vncViewer == "":
                scriptDialog.ShowMessageBox("The 'vncviwer' tool could not be found in the PATH.", "Error")
                return
        else:
            if system == 'Darwin':
                # On OSX, try to handle if they just have the .app package selected.
                if Path.GetFileName(vncViewer).lower() == "chicken.app":
                    vncViewer = Path.Combine( vncViewer, "Contents/MacOS/Chicken" )
                elif Path.GetFileName(vncViewer).lower() == "chicken of the vnc.app":
                    vncViewer = Path.Combine( vncViewer, "Contents/MacOS/Chicken of the VNC" )
            
            if not File.Exists( vncViewer ):
                scriptDialog.ShowMessageBox("The specified VNC Viewer does not exist.", "Error")
                return
        
        port = scriptDialog.GetValue("PortBox")
        password = scriptDialog.GetValue("PasswordBox")
            
        cancelButtonPressed()
        
        slaveNames = slaves.split(",")
        for currSlaveName in slaveNames:
            slaveName = currSlaveName.strip()
            
            arguments = ""
            if system == 'Windows':
                if Path.GetFileNameWithoutExtension(vncViewer).lower() == "vncviewer":
                    #Real VNC arguments
                    configFile = Path.Combine( ClientUtils.GetDeadlineTempPath(), 'config.vnc')
                    writer = StreamWriter( configFile, False, Encoding.Default )
                    writer.WriteLine('[Connection]')
                    writer.WriteLine('Host=' + slaveName)
                    writer.WriteLine('Port=' + str(port))
                    if len(password) > 0:
                        writer.WriteLine('Password=' + StringUtils.GetEncryptedVncPasswordString(password))
                    writer.Close()
                    
                    arguments = "-shared -config \"%s\"" % configFile
                    
                elif Path.GetFileNameWithoutExtension(vncViewer).lower() == "tvnviewer":
                    #Tight VNC arguments
                    if len(password) > 0:
                        arguments = '-host="%s" -port="%s" -password="%s"' % (slaveName, port, password)
                    else:
                        arguments = '-host="%s" -port="%s"' % (slaveName, port)
                        
                else:
                    scriptDialog.ShowMessageBox("Unrecognized VNC viewer executable. Currently only RealVNC and TightVNC are supported.", "Error")
                    return
                
            elif system == 'Linux':
                if Path.GetFileNameWithoutExtension(vncViewer).lower() == "vncviewer":
                    #Real VNC arguments
                    if len(password) > 0:
                        configFile = Path.Combine( ClientUtils.GetDeadlineTempPath(), 'config.vnc')
                        writer = StreamWriter( configFile, False, Encoding.Default )
                        writer.WriteLine(StringUtils.GetEncryptedVncPasswordString(password))
                        writer.Close()
                    
                        arguments = '-shared -passwd "%s" %s::%s' % (configFile,slaveName,port)
                    else:
                        arguments = '-shared -xdialog %s::%s' % (slaveName,port)
                    
                elif Path.GetFileNameWithoutExtension(vncViewer).lower() == "gvncviewer":
                    #gvncviewer - no option for password?
                    #arguments = "-shared %s::%s" %(slaveName, port)
                    arguments = "%s" % slaveName
                
                else:
                    scriptDialog.ShowMessageBox("Unrecognized VNC viewer executable. Currently only vncviewer and gvncviewer are supported.", "Error")
                    return
                
            elif system == 'Darwin':
                if Path.GetFileNameWithoutExtension(vncViewer).lower() == "chicken" or Path.GetFileNameWithoutExtension(vncViewer).lower() == "chicken of the vnc":
                    # Setting the password currently not supported. Need to figure out how to create a password file...
                    arguments = slaveName + ":" + str(port)
                else:
                    arguments = "-shared %s::%s" %(slaveName, port)
            else:
                scriptDialog.ShowMessageBox(system + "is not a supported platform.", "Error")
                return
        
            process = ProcessUtils.SpawnProcess(vncViewer, arguments)
            time.sleep(0.50)
    except:
        scriptDialog.ShowMessageBox(str(traceback.format_exc()), "Error")
