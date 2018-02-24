##------------------------------------------------------------
## SendPopUpMessage.py
## Created October 21, 2013 by Mike Owen
##
## General script to send pop up message to currently logged in user (GeneralScript)
##------------------------------------------------------------
from System import *
from System.Collections.Specialized import *
from System.IO import *
from System.Text import *
from Deadline.Scripting import *

import traceback
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

########################################################################
## Globals
########################################################################
scriptDialog = None
settings = None

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__(*args):
    global scriptDialog
    global settings
    global MessageBox

    dialogWidth = 620
    dialogHeight = 210

    scriptDialog = DeadlineScriptDialog()

    scriptDialog.SetSize(dialogWidth, dialogHeight)
    scriptDialog.SetTitle( "Send Pop-up Message" )

    scriptDialog.AddGrid()
    scriptDialog.AddControlToGrid( "SlavesLabel", "LabelControl", "Machine Name(s)", 0, 0, "Specify which machines to send pop up message to. Use a comma to separate multiple machine names.", False)
    scriptDialog.AddControlToGrid( "SlavesBox", "TextControl", "", 0, 1 )
    scriptDialog.EndGrid()

    scriptDialog.AddGrid()
    InsertFileButton = scriptDialog.AddControlToGrid("InsertFileButton", "ButtonControl", "Insert File Path", 0, 0, tooltip="Insert a file path at the current cursor location.", expand=False )
    InsertFileButton.ValueModified.connect(InsertFilePressed)
    
    InsertFolderButton = scriptDialog.AddControlToGrid("InsertFolderButton", "ButtonControl", "Insert Folder Path", 0, 1, tooltip="Insert a folder path at the current cursor location.", expand=False )
    InsertFolderButton.ValueModified.connect(InsertFolderPressed)
    
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel2", 0, 2 )
    
    LoadButton = scriptDialog.AddControlToGrid("LoadButton", "ButtonControl", "Load", 0, 3, tooltip="Load a message from a file.", expand=False)
    LoadButton.ValueModified.connect(LoadPressed)
    
    SaveButton = scriptDialog.AddControlToGrid("SaveButton", "ButtonControl", "Save", 0, 4, tooltip="Save the current message to a file.", expand=False)
    SaveButton.ValueModified.connect(SavePressed)

    ClearButton=scriptDialog.AddControlToGrid("ClearButton", "ButtonControl", "Clear", 0, 5, tooltip="Clear the current message.", expand=False)
    ClearButton.ValueModified.connect(ClearPressed)
    scriptDialog.EndGrid()
    
    scriptDialog.AddGrid()
    MessageBox = scriptDialog.AddControlToGrid("MessageBox","MultiLineTextControl","",0, 0, "", expand=True )
    scriptDialog.EndGrid()

    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "DummyLabel2", 0, 0 )
    sendButton = scriptDialog.AddControlToGrid( "SendButton", "ButtonControl", "OK", 0, 1, expand=False )
    sendButton.ValueModified.connect(sendMessage)
    cancelButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    cancelButton.ValueModified.connect(scriptDialog.closeEvent)
    scriptDialog.EndGrid()
    
    settings = ("SlavesBox", "MessageBox")
    scriptDialog.LoadSettings( getSettingsFilename(), settings )
    scriptDialog.EnabledStickySaving( settings, getSettingsFilename() )

    if len(args) > 0:
        scriptDialog.SetValue( "SlavesBox", args[0] )
    
    scriptDialog.ShowDialog( True )

def InsertFilePressed(self):
    global scriptDialog
    
    selection = scriptDialog.ShowOpenFileBrowser( "", "All Files (*)" )
    if selection != None and selection != "":
        selection = ("\"%s\"" % selection)
        MessageBox.insertPlainText(selection)
        
def InsertFolderPressed(self):
    global scriptDialog
    
    selection = scriptDialog.ShowFolderBrowser( "" )
    if selection != None and selection != "":
        selection = ("\"%s\"" % selection)
        MessageBox.insertPlainText(selection)
        
def LoadPressed(self):
    global scriptDialog
    
    selection = scriptDialog.ShowOpenFileBrowser( "", "All Files (*)" )
    if selection != None and selection != "":
        file = open( selection, "r" )
        text = file.read().replace( "\r\n", "\n" )
        scriptDialog.SetItems( "MessageBox", tuple(text.split( "\n" )) )
        file.close()
    
def SavePressed(self):
    global scriptDialog
    
    selection = scriptDialog.ShowSaveFileBrowser( "", "All Files (*)" )
    if selection != None and selection != "":
        file = open( selection, "w" )
        for line in scriptDialog.GetItems("MessageBox"):
            file.write( line + "\n" )
        file.close()

def ClearPressed(self):
    global scriptDialog
    scriptDialog.SetValue("MessageBox","")
    
def getSettingsFilename():
    return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), "PopupMessageSettings.ini" )

def sendMessage():
    global scriptDialog

    try:
        slaves = scriptDialog.GetValue("SlavesBox")
        if slaves.strip() == "":
            scriptDialog.ShowMessageBox("Please specify at least one machine name.", "Error")
            return

        messageLines = scriptDialog.GetItems("MessageBox")
        if len(messageLines) == 0:
            scriptDialog.ShowMessageBox( "Empty messages NOT allowed.", "Error" )
            return
        
        message = "\n".join(messageLines)

        scriptDialog.closeEvent(None)

        args = StringCollection()
        args.Add( "-SendPopupMessage" )
        args.Add( "%s" % slaves)
        args.Add( "%s" % message)

        ClientUtils.ExecuteCommand( args )
    except:
        scriptDialog.ShowMessageBox(str(traceback.format_exc()), "Error")
