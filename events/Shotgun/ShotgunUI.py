import sys
import time
import re
import webbrowser
import traceback
import json
import functools

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from System import *
from System.Collections.Specialized import *
from System.IO import *
from System.Text import *
from System.Threading import *

from Deadline.Scripting import *

from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

########################################################################
## Globals
########################################################################
scriptDialog = None

shotgunPath = None
shotgunImported = False #keeps track of whether or not we added Shotgun to the PATH

stickySettings = {} #a dictionary of sticky settings
advancedMode = False #tracks whether or not we're using advanced Mode
versionSelectMode = False #tracks if the control is used to select an existing version

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__( *args ):
    global scriptDialog
    global versionSelectMode
    appName = ""
    versionSelectMode = False

    #Parse out the args (if any)
    for arg in args:
        argLower = str(arg).lower()
        if argLower == "selectversion":
            versionSelectMode = True
        else:
            appName = arg

    scriptDialog = ShotgunDialog( appName, versionSelectMode )

    # Add control buttons
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "HSpacer", 0, 0 )
    okButton = scriptDialog.AddControlToGrid( "OkButton", "ButtonControl", "OK", 0, 1, expand=False )
    okButton.clicked.connect( OKButtonClicked )
    cancelButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    cancelButton.clicked.connect( CancelButtonClicked )
    scriptDialog.EndGrid()
    
    #look for errors or warnings
    errors, warnings = scriptDialog.CheckShotgunSetup()
    if len( errors ) > 0:
        message = "Deadline's Shotgun integration does not seem to be configured properly.\n\nThe following errors must be rectified in the Shotgun Event Plugin configuration before proceeding:\n"
        for error in errors:
            message += ("    ERROR: %s\n" % error)
        
        scriptDialog.ShowMessageBox( message, "Shotgun Configuration Error" )
        CancelButtonClicked()
    else:
        if len( warnings ) > 0:
            message = ""
            for warning in warnings:
                message += (warning + "\n\n")
                
            scriptDialog.ShowMessageBox( message.rstrip( '\n' ), "Shotgun Configuration Warning" )

        scriptDialog.ShowDialog( True )

def OKButtonClicked():
    global scriptDialog

    if not scriptDialog.Validate(): 
        return

    settingsDict = scriptDialog.GetSettingsDictionary()
    
    for key in settingsDict.keys():
        ClientUtils.LogText( "%s=%s" % ( key, settingsDict[key] ) )

    scriptDialog.CloseConnection()
    super( ShotgunDialog, scriptDialog ).accept()

def CancelButtonClicked():
    scriptDialog.CloseConnection()
    super( ShotgunDialog, scriptDialog ).reject()

########################################################################
## Subclass of DeadlineControlDialog for the UI
########################################################################
class ShotgunDialog( DeadlineScriptDialog ):
    settings = None

    newTaskMenu = None
    newEntityMenu = None

    updatingUI = False #variable used to bypass event handlers when values change programmatically
    
    def __init__( self, parentAppName="", versionSelectModeFlag = False, parent=None, shotgunInfo={} ):
        global shotgunPath
        global advancedMode
        global versionSelectMode
        versionSelectMode = versionSelectModeFlag
        super( ShotgunDialog, self ).__init__( parent )

        shotgunPath = RepositoryUtils.GetRepositoryPath( "events/Shotgun", True )
        AddShotgunToPath()
        try:
            #Try to import shotgun stuff; fail nicely if it doesn't work
            import ShotgunUtils
        except:
            self.ShowMessageBox( "An error occurred when trying to import the Shotgun API.\n\nPlease ensure that the Shotgun API has been added to your Shotgun event folder.", "Error" )
            self.ShowMessageBox( traceback.format_exc(), "ERROR" )
            return
            
        self.enableUI = True
        self.shotgunInfo = shotgunInfo
        
        #Get the shotgun plugin config values   
        self.sgConfig = RepositoryUtils.GetEventPluginConfig( 'Shotgun' )
        advancedMode = StringUtils.ParseBooleanWithDefault( self.sgConfig.GetConfigEntryWithDefault( "EnableAdvancedWorkflow", "False" ), False )
        self.versionTemplates = self.sgConfig.GetConfigEntryWithDefault( "VersionNameTemplates", "" ).split( ';' )
        self.sgURL = self.sgConfig.GetConfigEntryWithDefault( "ShotgunURL", "" )
        
        self.appName = parentAppName
        self.logMessages = [""]
        self.dataValidated = False
        self.settingsDict = {}

        #append a / if there isn't one
        if not IsNoneOrWhiteSpace( self.sgURL ) and not self.sgURL.endswith( "/" ):
            self.sgURL += "/"
        
        shotgunAPIVersion = ShotgunUtils.GetShotgunAPIVersion()
        
        #clean out empty templates
        for template in self.versionTemplates:
            if IsNoneOrWhiteSpace( template ):
                self.versionTemplates.remove( template )
        
        #Create our SG connection object, and hook up the signals
        self.shotgunConnection = ShotgunConnection()
        self.shotgunConnection.logMessage.connect( self.WriteToLogBox )
        self.shotgunConnection.errorOccurred.connect( self.ShowErrorMessage )
        self.shotgunConnection.progressUpdated.connect( self.UpdateProgBar )
        self.shotgunConnection.workCompleted.connect( self.AsyncCallback )
        
        self.shotgunConnection.userUpdated.connect( self.SGUserUpdated )
        self.shotgunConnection.tasksUpdated.connect( self.SGTasksUpdated )
        self.shotgunConnection.projectsUpdated.connect( self.SGProjectsUpdated )
        self.shotgunConnection.entitiesUpdated.connect( self.SGEntitiesUpdated )
        self.shotgunConnection.versionsUpdated.connect( self.SGVersionsUpdated )
        
        title = "Shotgun Settings"
        #change the title to include the Shotgun API version
        if not IsNoneOrWhiteSpace( shotgunAPIVersion ):
            title += " (API v%s)" % shotgunAPIVersion

        self.SetTitle( title )

        dialogWidth = 480
        labelWidth = 140
        controlHeight = -1 #20
        padding = 6

        self.AddControl( "Separator1", "SeparatorControl", "Shotgun Fields", dialogWidth, controlHeight )
        
        self.AddRow()
        self.AddControl( "LoginLabel", "LabelControl", "Login Name", labelWidth, controlHeight, "Shotgun Login Name")
        self.loginBox = self.AddControl( "LoginBox", "TextControl", "", 228, controlHeight )
        self.loginBox.ValueModified.connect(self.LoginNameChanged)
        
        self.loginButton = self.AddControl( "LoginButton", "ButtonControl", "Connect", 100, controlHeight )
        # create a partial so we can pass in a boolean to show popups while still preserving pyqt arguments
        self.loginButton.ValueModified.connect( functools.partial( self.LoginButtonPressed, True ) )
        self.EndRow()
        
        self.AddRow()
        self.AddControl( "UserLabel", "LabelControl", "Connected User", labelWidth, controlHeight, "The user currently connected." )
        self.AddControl( "UserBox", "ReadOnlyTextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
        self.EndRow()
        self.AddRow()
        self.AddControl( "TaskLabel", "LabelControl", "Task", labelWidth, controlHeight, "Select an assigned task for the current user." )
        self.taskBox = self.AddComboControl( "TaskBox", "ComboControl", "", (), dialogWidth - (labelWidth + padding) - 25, controlHeight )
        self.taskBox.ValueModified.connect(self.ShotgunTaskChanged)
        self.newTaskButton = self.AddControl( "NewTaskButton", "ButtonControl", "+", 20, controlHeight, "Click to add a new task for the current user." )
        self.newTaskButton.ValueModified.connect(self.NewTaskButton_Pressed)
        
        #context menu
        self.newTaskMenu = QMenu()
        item = QAction( "New Task...", self )
        item.triggered.connect( self.NewTaskMenuItem_Click )
        self.newTaskMenu.addAction( item )
        
        self.EndRow()
        self.AddRow()
        self.AddControl( "ProjectLabel", "LabelControl", "Project", labelWidth, controlHeight, "The project for the current task." )
        
        #only use a drop down if we're using advanced workflow
        if advancedMode:
            self.projectBox = self.AddComboControl( "ProjectBox", "ComboControl", "", (), dialogWidth - (labelWidth + padding), controlHeight )
            self.projectBox.ValueModified.connect(self.ShotgunProjectChanged)
        else:
            self.AddControl( "ProjectBox", "ReadOnlyTextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
            
        self.EndRow()
        self.AddRow()
        self.AddControl( "EntityLabel", "LabelControl", "Entity", labelWidth, controlHeight, "The entity for the current task." )
        
        #only use a drop down if we're using advanced workflow
        if advancedMode:
            self.entityBox = self.AddComboControl( "EntityBox", "ComboControl", "", (), dialogWidth - (labelWidth + padding) - 25, controlHeight )
            self.entityBox.ValueModified.connect(self.ShotgunEntityChanged)
            
            self.newEntityButton = self.AddControl( "NewEntityButton", "ButtonControl", "+", 20, controlHeight )
            self.newEntityButton.ValueModified.connect(self.NewEntityButton_Pressed)
            
            #context menu
            self.newEntityMenu = QMenu()
            item = QAction( "New Asset...", self )
            item.triggered.connect( self.NewAssetMenuItem_Click )
            self.newEntityMenu.addAction( item )
            
            item = QAction( "New Element...", self )
            item.triggered.connect( self.NewElementMenuItem_Click )
            self.newEntityMenu.addAction( item )
            
            item = QAction( "New Shot...", self )
            item.triggered.connect( self.NewShotMenuItem_Click )
            self.newEntityMenu.addAction( item )
        else:
            self.AddControl( "EntityBox", "ReadOnlyTextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
            
        self.EndRow()
        
        if versionSelectMode:
            self.AddRow()
            self.AddControl( "VersionLabel", "LabelControl", "Version", labelWidth, controlHeight, "The Version template for the task." )
            self.versionControl = self.AddComboControl( "VersionCombo", "ComboControl", "Version", (), dialogWidth - (labelWidth + padding), controlHeight )
            self.versionControl.ValueModified.connect(self.ShotgunVersionChanged)
            self.EndRow()
            
            self.AddRow()
            self.AddControl( "DescriptionLabel", "LabelControl", "Description", labelWidth, controlHeight, "The task description.")
            self.AddControl( "DescriptionBox", "ReadOnlyTextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
            self.EndRow()
        else:
            self.AddRow()
            self.AddControl( "TemplateLabel", "LabelControl", "Version Name", labelWidth, controlHeight, "The Version template for the task."  )
            
            #if we have templates, use an editable combo box
            if len( self.versionTemplates ) > 0:
                self.templateBox = self.AddComboControl( "TemplateBox", "EditableComboControl", "", tuple( self.versionTemplates ), dialogWidth - (labelWidth + padding), controlHeight )
                self.templateBox.ValueModified.connect(self.VersionTemplateChanged)
            else:   
                self.templateBox = self.AddControl( "TemplateBox", "TextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
                self.templateBox.ValueModified.connect(self.VersionTemplateChanged)
            
            self.EndRow()
            self.AddRow()
            self.AddControl( "PreviewLabel", "LabelControl", "Version Name Preview", labelWidth, controlHeight, "A preview of the current Version template." )
            self.AddControl( "PreviewBox", "ReadOnlyTextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
            self.EndRow()
            self.AddRow()
            self.AddControl( "DescriptionLabel", "LabelControl", "Description", labelWidth, controlHeight, "The task description." )
            self.AddControl( "DescriptionBox", "TextControl", "", dialogWidth - (labelWidth + padding), controlHeight )
            self.EndRow()
        
        self.AddRow()
        self.AddControl( "LogLabel", "LabelControl", "Shotgun Log:", labelWidth, -1 )
        self.EndRow()
        
        self.AddRow()
        self.logBox = self.AddComboControl( "LogBox", "ListControl", "", (""), dialogWidth, 100 )
        self.logBox.setSelectionMode( QAbstractItemView.ExtendedSelection )
        self.EndRow()
        
        self.AddRow()
        self.AddRangeControl( "ProgressBar", "ProgressBarControl", 0, 0, 100, 0, 0, labelWidth, 20)
        self.AddControl( "StatusLabel", "LabelControl", "", 160, controlHeight )
        self.EndRow()
        
        self.settings = ()

        if self.isShotgunInfoPulled():
            self.getShotgunInfo()
        else:
            self.loadStickySettings( self.GetStickyFilename() )
        if self.sgConfig.GetBooleanConfigEntryWithDefault( "AutoConnect", True ):
            self.LoginButtonPressed( False )
      
        self.UpdateEnabledStatus()
    
    def isShotgunInfoPulled( self ):
        return bool( self.shotgunInfo )

    def getShotgunInfo( self ):
        self.SetValue( "LoginBox", self.shotgunInfo.get( "UserLogin", "" ) )
        self.SetValue( "UserBox", self.shotgunInfo.get( "UserName", "" ) )
        self.SetValue( "ProjectBox", self.shotgunInfo.get( "ProjectName", "" ) )
        self.SetValue( "EntityBox", self.shotgunInfo.get( "EntityName", "" ) )
        if "ProjectName" in self.shotgunInfo and "EntityName" in self.shotgunInfo and "TaskName" in self.shotgunInfo:
            task = "%s > %s > %s" % ( self.shotgunInfo[ "ProjectName" ], self.shotgunInfo[ "EntityName" ], self.shotgunInfo[ "TaskName" ] )
            self.SGTasksUpdated( [ task ], task )
        self.compareShotgunAndStickySettings()

    def compareShotgunAndStickySettings( self ):
        global stickySettings

        try:
            with open( self.GetStickyFilename(), "r" ) as settingsFile:
                stickySettings = json.loads( settingsFile.read() )
        except:
            pass
        
        if "ProjectName" not in self.shotgunInfo or self.shotgunInfo[ "ProjectName" ] != stickySettings.get( "ProjectName", "" ):
            return
        
        if "EntityName" not in self.shotgunInfo or self.shotgunInfo[ "EntityName" ] != stickySettings.get( "EntityName", "" ):
            return
        
        if "TaskName" not in self.shotgunInfo or self.shotgunInfo[ "TaskName" ] != stickySettings.get( "TaskName", "" ):
            return

        # load the rest of the sticky settings
        global versionSelectMode
        try:
            if versionSelectMode:
                version = stickySettings["VersionName"]
                self.SGVersionsUpdated( [version], version )
                self.selectedVersion = version
            else:
                self.SetValue( "TemplateBox", stickySettings["VersionName"] )
        except:
            pass
        
        try:
            self.SetValue( "DescriptionBox", stickySettings["DescriptionName"] )
        except:
            pass

    def loadStickySettings( self, fileName ):
        global stickySettings
        global versionSelectMode
        
        stickySettings = {}
        try:
            self.WriteToLogBox( "Retrieving sticky settings... ", True )
            settingsFile = open( fileName, "r" )
            stickySettings = json.loads( settingsFile.read() )
            settingsFile.close()
        except:
            pass
        
        try:
            self.SetValue( "LoginBox", stickySettings["User"] )
        except:
            pass
        
        try:
            self.SetValue( "UserBox", stickySettings["ConnectedUser"] )
        except:
            pass
        
        try:
            task = stickySettings["ProjectName"] + " > " + stickySettings["EntityName"] + " > " + stickySettings["TaskName"]
            
            self.SGTasksUpdated( [ task ], task )
        except:
            pass
        
        try:
            self.SetValue( "ProjectBox", stickySettings["ProjectName"] )
        except:
            pass
            
        try:
            self.SetValue( "EntityBox", stickySettings["EntityName"] )
        except:
            pass
                        
        try:
            if versionSelectMode:
                version = stickySettings["VersionName"]
                self.SGVersionsUpdated( [version], version )
                self.selectedVersion = version
            else:
                self.SetValue( "TemplateBox", stickySettings["VersionName"] )
        except:
                pass
        
        try:
            self.SetValue( "DescriptionBox", stickySettings["DescriptionName"] )
        except:
            pass
        
        try:
            #Always try to close the file
            settingsFile.close()
        except:
            pass

        self.WriteToLogBox( "done!" )
        
    def saveStickySettings( self, fileName ):
        global stickySettings
        
        connected = (self.shotgunConnection != None and self.shotgunConnection.currentUser != None)
        
        if connected or self.isShotgunInfoPulled():
            stickySettings = {}
            
            if connected:
                user = self.shotgunConnection.currentUser.get( "login", None )
            else:
                user = self.shotgunInfo.get( "UserLogin", None )
            if not IsNoneOrWhiteSpace( user ):
                stickySettings["User"] = user
            
            stickySettings["ConnectedUser"] = self.GetValue( "UserBox")
            
            taskName = self.GetValue( "TaskBox" )
            
            stickySettings["TaskName"] = taskName
            
            if not IsNoneOrWhiteSpace( taskName ):
                if connected:
                    task = self.shotgunConnection.sgTaskDict[ taskName ]

                    stickySettings["TaskName"] = task['content']
                    stickySettings["ProjectName"] = task['project']['name']
                    stickySettings["EntityName"] = task['entity']['name']
                    
                    stickySettings["TaskId"] = task['id']
                    stickySettings["ProjectId"] = task['project']['id']
                    stickySettings["EntityId"] = task['entity']['id']
                    stickySettings["EntityType"] = task['entity']['type']
                else:
                    stickySettings["TaskName"] = self.shotgunInfo.get( "TaskName", "" )
                    stickySettings["ProjectName"] = self.shotgunInfo.get( "ProjectName", "" )
                    stickySettings["EntityName"] = self.shotgunInfo.get( "EntityName", "" )

                    stickySettings["TaskId"] = self.shotgunInfo.get( "TaskId", "" )
                    stickySettings["ProjectId"] = self.shotgunInfo.get( "ProjectId", "" )
                    stickySettings["EntityId"] = self.shotgunInfo.get( "EntityId", "" )
                    stickySettings["EntityType"] = self.shotgunInfo.get( "EntityType", "" )
            else:
                #Check project/entity names; we just need to filter on the most specific one (Entity -> Project -> no filter)
                projectName = self.GetValue( "ProjectBox" )
                entityName = self.GetValue( "EntityBox" )
                
                project = self.shotgunConnection.sgProjectDict[ projectName ]
                entity = self.shotgunConnection.sgEntityDict[ entityName ]

                stickySettings["TaskName"] = "None"
                stickySettings["ProjectName"] = projectName
                stickySettings["EntityName"] = entityName
                
                stickySettings["TaskId"] = "-1"
                stickySettings["ProjectId"] = project['id']
                stickySettings["EntityId"] = entity['id']
                stickySettings["EntityType"] = entity['type']
                
            versionName = ""
            if versionSelectMode:
                versionName = self.GetValue( "VersionCombo" )
            else:
                versionName = self.ApplyTemplate( self.GetValue( "TemplateBox" ), False )
                
            stickySettings["VersionName"] = versionName
            stickySettings["DescriptionName"] = self.GetValue( "DescriptionBox" )
            
        self.WriteToLogBox( "Retrieving sticky settings... ", True )
        
        settingsFile = open( fileName, "w" )
        settingsFile.write( json.dumps( stickySettings ))
        settingsFile.close()
    
    def reject( self ):
        parent = self.parent()
        if parent == None:
            QDialog.reject()
        else:
            # The parent dialog is 4 levels up, the levels in-between consist of widgets and tab controls which don't implement reject
            self.window().reject()

    #Updates the UI with a new user
    @pyqtSlot( str )
    def SGUserUpdated( self, newUser ):
        self.updatingUI = True
        self.SetValue( "UserBox", newUser )
        self.updatingUI = False

    #Updates the UI with new tasks
    @pyqtSlot( tuple, str )
    def SGTasksUpdated( self, newTasks, selectedTask ):
        self.updatingUI = True
        self.SetItems( "TaskBox", newTasks )
        self.SetValue( "TaskBox", selectedTask )
        self.updatingUI = False

    #Updates the UI with new projects
    @pyqtSlot( tuple, str )
    def SGProjectsUpdated( self, newProjects, selectedProject ):
        global advancedMode
        self.updatingUI = True
        if len(newProjects) > 0 and advancedMode:
            self.SetItems( "ProjectBox", newProjects )
        
        self.SetValue( "ProjectBox", selectedProject )
        self.updatingUI = False

    #Updates the UI with new entities
    @pyqtSlot( tuple, str )
    def SGEntitiesUpdated( self, newEntities, selectedEntity ):
        global advancedMode
        self.updatingUI = True
        if len(newEntities) > 0 and advancedMode:
            self.SetItems( "EntityBox", newEntities )
        
        self.SetValue( "EntityBox", selectedEntity )
        self.updatingUI = False

    #Updates the UI with new versions
    @pyqtSlot( tuple, str )
    def SGVersionsUpdated( self, newVersions, selectedVersion ):
        self.updatingUI = True
        
        if len( newVersions ) == 0 and IsNoneOrWhiteSpace( selectedVersion ):
            #Code was doing this before in this case, must be trickery to get it to change the displayed value without exploding
            self.SetItems( "VersionCombo", (selectedVersion, ) )
            self.SetValue( "VersionCombo", selectedVersion )
            self.SetItems( "VersionCombo", newVersions )
        else:
            self.SetItems( "VersionCombo", newVersions )
            self.SetValue( "VersionCombo", selectedVersion )
            
        self.updatingUI = False

    #Slot that updates the progress bar & status message
    @pyqtSlot( int, str )
    def UpdateProgBar( self, progress, statusMessage ):
        
        self.SetValue( "ProgressBar", progress )
        self.SetValue( "StatusLabel", statusMessage )

    #Slot that displays an error message in a popup message box
    @pyqtSlot( str )
    def ShowErrorMessage( self, errorMessage ):
        self.ShowMessageBox( errorMessage, "Error" )
        
    #Adds a line to the log box (in a thread-safe manner)
    @pyqtSlot( str, bool )
    def WriteToLogBox( self, strAppending, suppressNewLine=False ):
        try:
            #Make sure it's a python string! (and not a filthy QString)
            strAppending = str( strAppending )
            lines = strAppending.splitlines()
            
            for line in lines:
                self.logMessages[ len( self.logMessages ) - 1 ] += line
                
                if not suppressNewLine or lines.index(line) < len(lines) - 1:
                    self.logMessages.append( "" )
                
                self.SetItems( "LogBox", tuple( self.logMessages ) )
        except:
            #the log box might just not be initialized, just supress the exception
            ClientUtils.LogText( str( traceback.format_exc() ) )

    @pyqtSlot()
    def AsyncCallback( self ):
                
        #General updating stuff that should be done whenever an operation completes
        self.UpdateTaskFilter()
        self.VersionTemplateChanged( None )
        self.UpdateEnabledStatus()
        
    #Updates the enabled status of all controls on the form to match their status (values)  
    def UpdateEnabledStatus( self ):
        global advancedMode
        global versionSelectMode
        #Check if we're working on something in the background thread
        finishedWorking = (self.shotgunConnection.workerThread == None or not self.shotgunConnection.workerThread.IsAlive)
        
        #Check which fields are empty -- this will help us determine which controls should be enabled
        connected = (self.shotgunConnection != None and self.shotgunConnection.currentUser != None)
        pulled = self.isShotgunInfoPulled()
        taskEmpty = IsNoneOrWhiteSpace( self.GetValue( "TaskBox" ) )
        projectEmpty =  IsNoneOrWhiteSpace( self.GetValue( "ProjectBox" ) )
        entityEmpty = IsNoneOrWhiteSpace( self.GetValue( "EntityBox" ) )
        
        #login related stuff
        loginName = self.GetValue( "LoginBox" )
        loginEmpty = IsNoneOrWhiteSpace( loginName )
        loginChanged = False
        
        if connected:
            loginChanged = (self.shotgunConnection.currentUser['login'] != loginName)
        
        self.SetEnabled( "LoginLabel", finishedWorking and self.enableUI )
        self.SetEnabled( "LoginBox", finishedWorking and self.enableUI )
        self.SetEnabled( "LoginButton", finishedWorking and not loginEmpty and self.enableUI )
        
        if connected and not loginChanged:
            self.SetValue( "LoginButton", "Refresh" )
        else:
            self.SetValue( "LoginButton", "Connect" )
        
        self.SetEnabled( "UserLabel", ( connected or pulled ) and finishedWorking and self.enableUI )
        self.SetEnabled( "UserBox", connected and finishedWorking and self.enableUI )
        
        self.SetEnabled( "TaskLabel", ( connected or pulled ) and finishedWorking and self.enableUI )
        self.SetEnabled( "TaskBox", connected and finishedWorking and self.enableUI )
        self.SetEnabled( "NewTaskButton", connected and finishedWorking and self.enableUI )
        
        self.SetEnabled( "ProjectLabel", ( connected or pulled ) and finishedWorking and (not advancedMode or taskEmpty) and self.enableUI )
        self.SetEnabled( "ProjectBox", connected and finishedWorking and (not advancedMode or taskEmpty) and self.enableUI )
        
        self.SetEnabled( "EntityLabel", ( connected or pulled ) and finishedWorking and ( not advancedMode or (taskEmpty and not projectEmpty) ) and self.enableUI )
        self.SetEnabled( "EntityBox", connected and finishedWorking and ( not advancedMode or (taskEmpty and not projectEmpty) ) and self.enableUI )
        
        if advancedMode:
            self.SetEnabled( "NewEntityButton", ( connected or pulled ) and finishedWorking and taskEmpty and not projectEmpty and self.enableUI )
        
        if versionSelectMode:
            self.SetEnabled( "VersionLabel", ( connected or pulled ) and finishedWorking and not entityEmpty and self.enableUI )
            self.SetEnabled( "VersionCombo", ( connected or pulled ) and finishedWorking and not entityEmpty and self.enableUI )
        else:
            self.SetEnabled( "TemplateLabel", ( connected or pulled ) and finishedWorking and self.enableUI )
            self.SetEnabled( "TemplateBox", ( connected or pulled ) and finishedWorking and self.enableUI )
            self.SetEnabled( "PreviewLabel", ( connected or pulled ) and finishedWorking and self.enableUI )
            self.SetEnabled( "PreviewBox", ( connected or pulled ) and finishedWorking and self.enableUI )
        
        self.SetEnabled( "DescriptionLabel", ( connected or pulled ) and finishedWorking and self.enableUI )
        self.SetEnabled( "DescriptionBox", ( connected or pulled ) and finishedWorking and self.enableUI )

    #Updates the filters on the Task list
    def UpdateTaskFilter( self ):
        #If we already have a Task selected, don't do any of this stuff
        taskName = self.GetValue( "TaskBox" )
        if not IsNoneOrWhiteSpace( taskName ):
            return
        
        #Check project/entity names; we just need to filter on the most specific one (Entity -> Project -> no filter)
        projectName = self.GetValue( "ProjectBox" )
        entityName = self.GetValue( "EntityBox" )
        
        newTaskItems = [""]
        if not IsNoneOrWhiteSpace( entityName ):
            #Filter tasks based on the Entity
            self.WriteToLogBox( "Filtering Tasks for Entity '%s'... " % entityName, True )
            entity = self.shotgunConnection.sgEntityDict.get( entityName, None )
            
            for key, value in self.shotgunConnection.sgTaskDict.iteritems():
                if entity == None or (entity['id'] == value['entity']['id'] and entity['type'] == value['entity']['type']):
                    newTaskItems.append( key )
            
        elif not IsNoneOrWhiteSpace( projectName ):
            #Filter tasks based on the Project
            self.WriteToLogBox( "Filtering Tasks for Project '%s'... " % projectName, True )
            project = self.shotgunConnection.sgProjectDict.get( projectName, None )
        
            for key, value in self.shotgunConnection.sgTaskDict.iteritems():
                if project == None or project['id'] == value['project']['id']:
                    newTaskItems.append( key )
        else:
            #Clear any filters that might be currently applied
            self.WriteToLogBox( "Clearing Task filters... ", True )
            for key, value in self.shotgunConnection.sgTaskDict.iteritems():
                newTaskItems.append( key )
        
        #Sort the list and update the Task list
        newTaskItems.sort()
        self.updatingUI = True 
        self.SetItems( "TaskBox", tuple( newTaskItems ) )
        self.updatingUI = False
        self.WriteToLogBox( "done!" )

        self.UpdateEnabledStatus()

    #Checks the provided Shotgun settings dictionary (taken from Shotgun.dlinit) to make sure required values have been set up
    def CheckShotgunSetup( self ):
        warnings = []
        errors = []
        
        if IsNoneOrWhiteSpace( self.sgURL ):
            errors.append( "The Shotgun URL has not been set." )
        
        if self.sgConfig.GetConfigEntryWithDefault( "ShotgunScriptName", "" ).strip() == "":
            errors.append( "The Shotgun Script Name has not been set." )
            
        if self.sgConfig.GetConfigEntryWithDefault( "ShotgunScriptKey", "" ).strip() == "":
            errors.append( "The Shotgun Script Key has not been set." )
        
        sgEnabled = self.sgConfig.GetConfigEntryWithDefault( "State", "" ).strip()
        if 'ENABLED' not in sgEnabled.upper():
            warnings.append( "The Shotgun Event Plugin is currently disabled.\n\nThe Shotgun Event Plugin must be enabled in order for Shotgun integration to work properly." )
        
        return errors, warnings

    def ShotgunTaskChanged( self, *args ):
        global advancedMode
        global versionSelectMode
        taskName = self.GetValue( "TaskBox" )
        self.shotgunConnection.selectedTask = taskName
        
        #Make sure we don't chain events when we're updating values in code
        if self.updatingUI:
            
            return
        
        if len( self.GetItems( "TaskBox" ) ) > 0:
            #Get Versions if required
            if versionSelectMode:
                self.shotgunConnection.GetVersionsForTaskAsync( taskName )
                
            projectNames = [ ]
            entityNames = [ ]
            if not IsNoneOrWhiteSpace( taskName ):
                task = self.shotgunConnection.sgTaskDict[ taskName ]
                if task['project'] != None and task['entity'] != None:
                    projectNames.append( task['project']['name'] )
                    entityNames.append( task['entity']['name'] )
            else:
                projectNames.append( " " )
                entityNames.append( " " )
                
                if advancedMode:
                    for key in self.shotgunConnection.sgProjectDict.keys():
                        projectNames.append( key )
                
                projectNames.sort()
            
            self.updatingUI = True
            
            if advancedMode:
                self.SetItems( "ProjectBox", tuple( projectNames ) )
            
            if len( projectNames ) > 0:
                self.SetValue( "ProjectBox", projectNames[ 0 ] )
            
            if advancedMode:
                self.SetItems( "EntityBox", tuple( entityNames ) )
            
            if len( entityNames ) > 0:
                self.SetValue( "EntityBox", entityNames[ 0 ] )
                
            self.updatingUI = False
        
        if not IsNoneOrWhiteSpace( taskName ):
            self.shotgunConnection.SetEpisodeAndSequence( taskName )
 
        self.UpdateTaskFilter()
        self.VersionTemplateChanged( None )
        self.UpdateEnabledStatus()
        
    def ShotgunProjectChanged( self, *args ):
        projectName = self.GetValue( "ProjectBox" )
        self.shotgunConnection.selectedProject = projectName
        
        #Make sure we don't chain events when we're updating values in code
        if self.updatingUI:
            return
        
        if len( self.GetItems( "ProjectBox" ) ) > 0:
            self.shotgunConnection.GetEntitiesForProjectAsync( projectName )
        
        self.UpdateTaskFilter()
        self.VersionTemplateChanged( None )
        self.UpdateEnabledStatus()
        
    def ShotgunEntityChanged( self, *args ):
        global versionSelectMode
        entityName = self.GetValue( "EntityBox" )
        self.shotgunConnection.selectedEntity = entityName
        
        #Make sure we don't chain events when we're updating values in code
        if self.updatingUI:
            return
        
        if len( self.GetItems( "EntityBox" ) ) > 0:
            taskName = self.GetValue( "TaskBox" )
            
            if versionSelectMode and IsNoneOrWhiteSpace( taskName ):
                self.shotgunConnection.GetVersionsForEntityAsync( entityName )
        
        self.UpdateTaskFilter()
        self.VersionTemplateChanged( None )
        self.UpdateEnabledStatus()
        
    def ShotgunVersionChanged( self, *args ):
        if self.updatingUI:
            return
            
        description = ""
        if len( self.GetItems( "VersionCombo" ) ) > 0:
            versionName = self.GetValue( "VersionCombo" )
            if not IsNoneOrWhiteSpace( versionName ) and self.shotgunConnection.sgVersionDict.has_key( versionName ):
                version = self.shotgunConnection.sgVersionDict[versionName]
                if version.has_key( 'description' ):
                    description = version['description']
                
        self.SetValue( "DescriptionBox", description )
        
        self.UpdateEnabledStatus()

    #Returns the template string with placeholder values swapped out (optionally replacing {jobid} with a dummy value)
    def ApplyTemplate( self, templateString, dummyJobID=True ):
        global advancedMode
        global stickySettings
                
        pulled = self.isShotgunInfoPulled()

        if not self.shotgunConnection.currentUser and not pulled:
            try:
                return stickySettings[ "VersionName" ]
            except:
                return ""
        
        #might not be logged in for whatever reason
        if self.shotgunConnection.currentUser != None:
            #could change this to actual user name if users prefer (instead of login)
            userName = self.shotgunConnection.currentUser['login']
            templateString = re.sub( '(?i)\$\{user\}', userName, templateString )
        elif pulled:
            userName = self.shotgunInfo.get( 'LoginName', '' )
            templateString = re.sub( '(?i)\$\{user\}', userName, templateString )

        
        #might not be a task selected
        displayTaskName = self.GetValue("TaskBox")
        if not IsNoneOrWhiteSpace( displayTaskName ):
            if self.shotgunConnection.currentUser:
                task = self.shotgunConnection.sgTaskDict[ displayTaskName ]
                templateString = re.sub( '(?i)\$\{task\}', task['content'], templateString )
                templateString = re.sub( '(?i)\$\{project\}', task['project']['name'], templateString )
                templateString = re.sub( '(?i)\$\{shot\}', task['entity']['name'], templateString )
                templateString = re.sub( '(?i)\$\{entity\}', task['entity']['name'] + "-" + str(task['entity']['id']), templateString )
                templateString = re.sub( '(?i)\$\{sequence\}', self.shotgunConnection.taskSequence, templateString )
                templateString = re.sub( '(?i)\$\{episode\}', self.shotgunConnection.taskEpisode, templateString )
            else:
                # shotgun info was pulled and there's no connection, so populate with pulled info
                templateString = re.sub( '(?i)\$\{task\}', self.shotgunInfo.get( 'TaskName', '' ), templateString )
                templateString = re.sub( '(?i)\$\{project\}', self.shotgunInfo.get( 'ProjectName', '' ), templateString )
                templateString = re.sub( '(?i)\$\{shot\}', self.shotgunInfo.get( 'EntityName', '' ), templateString )
                templateString = re.sub( '(?i)\$\{entity\}', '%s-%s' % ( self.shotgunInfo.get( 'EntityName', '' ), self.shotgunInfo.get( 'EntityId', '' ) ), templateString )
                # cannot get sequence and episode from shotgun context
                templateString = re.sub( '(?i)\$\{sequence\}', 'SEQUENCE', templateString )
                templateString = re.sub( '(?i)\$\{episode\}', 'EPISODE', templateString )

        elif advancedMode:
            #no task selected, check project/entity
            projectName = self.GetValue("ProjectBox")
            if not IsNoneOrWhiteSpace( projectName ):
                templateString = re.sub( '(?i)\$\{project\}', projectName, templateString )
            
                #might have to change this later if we want {shot} to ONLY pull shots (not whatever's selected in the entity box)
                displayEntityName = self.GetValue("EntityBox")
                if not IsNoneOrWhiteSpace( displayEntityName ):
                    entityName = self.shotgunConnection.sgEntityDict[ displayEntityName ]['code']
                    templateString = re.sub( '(?i)\$\{shot\}', entityName, templateString )
        
        if dummyJobID:
            templateString = re.sub( '(?i)\$\{jobid\}', '5179861c4bdf861258c1a61d', templateString )
        
        return templateString

    def VersionTemplateChanged( self, *args ):
        global versionSelectMode
        connected = (self.shotgunConnection != None and self.shotgunConnection.currentUser != None)
        if not versionSelectMode and ( connected or self.isShotgunInfoPulled() ):
            templateString = self.GetValue( "TemplateBox" )
            self.SetValue( "PreviewBox", self.ApplyTemplate( templateString ) )

    def LoginNameChanged( self, *args ):
        self.UpdateEnabledStatus()
        return

    def LoginButtonPressed( self, *args ):
        if self.shotgunConnection and self.GetValue( "LoginBox" ):
            # if this function is called from the user clicking the button, then the button object will also be passed in
            showPopup = args[0]
            self.shotgunConnection.ConnectToShotgunAsync( self.GetValue( "LoginBox" ), showPopup )
        
        self.UpdateEnabledStatus()

    def NewTaskButton_Pressed( self, *args):
        if len( args ) > 0:
            button = args[0]
            self.newTaskMenu.exec_( button.mapToGlobal( QPoint( 0, 0 ) ) )

    def NewEntityButton_Pressed( self, *args ):
        if len( args ) > 0:
            button = args[0]
            self.newEntityMenu.exec_( button.mapToGlobal( QPoint( 0, 0 ) ) )

    def NewSGItemBrowser( self, itemName, additionalArgs="" ):
        if not IsNoneOrWhiteSpace( self.sgURL ):
            newEntityURL = self.sgURL + "new/" + itemName + "?show_nav=no"
            projectName = self.GetValue( "ProjectBox" )
            
            if not IsNoneOrWhiteSpace( projectName ):
                #Need to swap spaces for '%20' to make this a valid url
                newEntityURL += '&project=' + projectName.replace( " ", "%20" )
            
            newEntityURL += additionalArgs
            
            webbrowser.open( newEntityURL, 1, True )

    def NewAssetMenuItem_Click( self, *args):
        self.NewSGItemBrowser( "Asset" )
        
    def NewElementMenuItem_Click(self, *args):
        self.NewSGItemBrowser( "Element" )
        
    def NewShotMenuItem_Click(self, *args):
        self.NewSGItemBrowser( "Shot" )

    def NewTaskMenuItem_Click(self,*args):
        #TODO: Figure out how to default users.  Probably using the default={...} argument (not like project).... 
        #if currentUser != None:
        #   NewSGItemBrowser( "Task", "&task_assignees=" + currentUser.get( "name", "" ) )
        #else:
        self.NewSGItemBrowser( "Task", "&defaults={%22sg_status_list%22:%22rdy%22}" )

    def GetSettingsFilename(self):
        return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), str(self.appName) + "ShotgunSettings.ini" )
        
    def GetStickyFilename( self ):
        return Path.Combine( ClientUtils.GetUsersSettingsDirectory(), str(self.appName) + "ShotgunSticky.txt" )

    def Validate( self, *args ):
        global advancedMode
        global versionSelectMode
        global stickySettings

        connected = (self.shotgunConnection != None and self.shotgunConnection.currentUser != None)
        pulled = self.isShotgunInfoPulled()
        
        self.settingsDict = {}

        try:
            self.WriteToLogBox( "Validating selected values..." )
            userName = ""
            taskName = self.GetValue( "TaskBox" )
            projectName = self.GetValue( "ProjectBox" )
            entityName = self.GetValue( "EntityBox" )
            description = self.ApplyTemplate( self.GetValue( "DescriptionBox" ), False )
            
            if versionSelectMode:
                versionName = self.GetValue( "VersionCombo" )
            else:
                versionName = self.ApplyTemplate( self.GetValue( "TemplateBox" ), False )
            
            draftTemplate = ""
            if connected:
                if not IsNoneOrWhiteSpace( taskName ):
                    draftTemplate = self.shotgunConnection.sgTaskDict[taskName].get( "draftTemplate", "" )
            
            validationPassed = True
            
            if connected:
                #Need to have a valid user logged in
                if self.shotgunConnection.currentUser == None:
                    self.WriteToLogBox( "Validation failed on User Name" )
                    validationPassed = False
                else:
                    userName = self.shotgunConnection.currentUser.get( "login", None )
                    
                    if IsNoneOrWhiteSpace( userName ):
                        self.WriteToLogBox( "Validation failed on User Name" )
                        validationPassed = False
            elif pulled:
                userName = self.shotgunInfo.get( "UserLogin", None )
                if IsNoneOrWhiteSpace( userName ):
                    self.WriteToLogBox( "Validation failed on User Name" )
                    validationPassed = False
            else:
                try:
                    userName = stickySettings["User"]
                    if userName == "":
                        self.WriteToLogBox( "Validation failed on User Name" )
                        validationPassed = False
                except:
                    self.WriteToLogBox( "Validation failed on User Name" )
                    validationPassed = False
                
            #Need to either have Project & Entity, or Task specified
            if IsNoneOrWhiteSpace( taskName ) and (IsNoneOrWhiteSpace( projectName ) or IsNoneOrWhiteSpace( entityName ) or not advancedMode):
                self.WriteToLogBox( "Validation failed on Task or Project/Entity" )
                validationPassed = False
                
            #Need to specify a version name
            if IsNoneOrWhiteSpace( versionName ):
                self.WriteToLogBox( "Validation failed on Version Name" )
                validationPassed = False
            
            if not validationPassed:
                validationMessage = ""
                if versionSelectMode:
                    validationMessage = "You must complete the Shotgun form in order to select an existing Shotgun Version for this job.\n\nPlease fill in any missing info before proceeding."
                else:
                    validationMessage = "You must complete the Shotgun form in order to create a new Shotgun Version for this job.\n\nPlease fill in any missing info before proceeding."
                
                self.ShowMessageBox( validationMessage, "Shotgun Form Incomplete" )
                return
            
            self.WriteToLogBox( "Validating passed!" )

            self.WriteToLogBox( "Building output... ", True )
            
            self.settingsDict["VersionName"] = versionName
            self.settingsDict["Description"] = description
            self.settingsDict["UserName"] = userName
            
            if connected:
                if not IsNoneOrWhiteSpace( taskName ):
                    task = self.shotgunConnection.sgTaskDict[ taskName ]

                    self.settingsDict["TaskName"] = task['content']
                    self.settingsDict["ProjectName"] = task['project']['name']
                    self.settingsDict["EntityName"] = task['entity']['name']

                    self.settingsDict["TaskId"] = task['id']
                    self.settingsDict["ProjectId"] = task['project']['id']
                    self.settingsDict["EntityId"] = task['entity']['id']
                    self.settingsDict["EntityType"] = task['entity']['type']
                else:
                    project = self.shotgunConnection.sgProjectDict[ projectName ]
                    entity = self.shotgunConnection.sgEntityDict[ entityName ]

                    self.settingsDict["TaskName"] = "None"
                    self.settingsDict["ProjectName"] = projectName
                    self.settingsDict["EntityName"] = entityName

                    self.settingsDict["TaskId"] = "-1"
                    self.settingsDict["ProjectId"] = project['id']
                    self.settingsDict["EntityId"] = entity['id']
                    self.settingsDict["EntityType"] = entity['type']
                
                if versionSelectMode:
                    version = self.shotgunConnection.sgVersionDict[ versionName ]
                    pathField = self.sgConfig.GetConfigEntryWithDefault('VersionEntityPathToFramesField', "")
                    firstFrameField = self.sgConfig.GetConfigEntryWithDefault('VersionEntityFirstFrameField', "")
                    lastFrameField = self.sgConfig.GetConfigEntryWithDefault('VersionEntityLastFrameField', "")

                    self.settingsDict["VersionId"] = version['id']
                    self.settingsDict["PathToFrames"] = version.get(pathField, "")
                    self.settingsDict["FirstFrame"] = version.get(firstFrameField, "")
                    self.settingsDict["LastFrame"] = version.get(lastFrameField, "")
            elif pulled:
                    self.settingsDict["TaskName"] = self.shotgunInfo.get( "TaskName", "" )
                    self.settingsDict["ProjectName"] = self.shotgunInfo.get( "ProjectName", "" )
                    self.settingsDict["EntityName"] = self.shotgunInfo.get( "EntityName", "" )

                    self.settingsDict["TaskId"] = self.shotgunInfo.get( "TaskId", "" )
                    self.settingsDict["ProjectId"] = self.shotgunInfo.get( "ProjectId", "" )
                    self.settingsDict["EntityId"] = self.shotgunInfo.get( "EntityId", "" )
                    self.settingsDict["EntityType"] = self.shotgunInfo.get( "EntityType", "" )
            else:
                if not IsNoneOrWhiteSpace( taskName ):
                    self.settingsDict["TaskName"] = stickySettings['TaskName']
                    self.settingsDict["ProjectName"] = stickySettings['ProjectName']
                    self.settingsDict["EntityName"] = stickySettings['EntityName']

                    self.settingsDict["TaskId"] = stickySettings['TaskId']
                    self.settingsDict["ProjectId"] = stickySettings['ProjectId']
                    self.settingsDict["EntityId"] = stickySettings['EntityId']
                    self.settingsDict["EntityType"] = stickySettings['EntityType']
                else:
                    project = self.shotgunConnection.sgProjectDict[ projectName ]
                    entity = self.shotgunConnection.sgEntityDict[ entityName ]

                    self.settingsDict["TaskName"] = "None"
                    self.settingsDict["ProjectName"] = projectName
                    self.settingsDict["EntityName"] = entityName

                    self.settingsDict["TaskId"] = "-1"
                    self.settingsDict["ProjectId"] = stickySettings['ProjectId']
                    self.settingsDict["EntityId"] = stickySettings['EntityId']
                    self.settingsDict["EntityType"] = stickySettings['EntityType']

            self.settingsDict["DraftTemplate"] = draftTemplate

            self.WriteToLogBox( "done!" )
            
            if connected:
                #switch the contents of the login box to be the current user, so it gets stickied properly
                self.SetValue( "LoginBox", userName )
            elif pulled:
                self.SetValue( "LoginBox", self.shotgunInfo.get( "UserLogin", "" ) )
            
            self.WriteToLogBox( "Saving sticky settings... ", True )
            self.saveStickySettings( self.GetStickyFilename() )
                
            self.WriteToLogBox( "done!" )
        except:
            #if an error occurred while trying to close the dialog, this UI stuff might fail -- don't want it to generate another exception
            try:
                self.WriteToLogBox( "UNEXPECTED ERROR:" )
                self.WriteToLogBox( str( sys.exc_info()[0] ) )
                self.WriteToLogBox( str( sys.exc_info()[1] ) )
                self.WriteToLogBox( "---END ERROR INFO---" )
                
                self.ShowMessageBox( "An error occurred while preparing output.\nSee Shotgun log window for more details.", "ERROR!" )
                validationPassed = False
            except:
                validationPassed = False

        self.dataValidated = validationPassed

        return validationPassed

    def GetSettingsDictionary( self ):
        if not self.dataValidated:
            self.ShowMessageBox( "Shotgun data has not been validated.", "Warning" )
        return self.settingsDict

    def CloseConnection( self, *args ):
        #Make sure to abort non-ui threads first, so that they don't keep running
        if self.shotgunConnection.workerThread != None and self.shotgunConnection.workerThread.IsAlive:
            self.shotgunConnection.workerThread.Abort()
        
        if self.shotgunConnection.progressThread != None and self.shotgunConnection.progressThread.IsAlive:
            self.shotgunConnection.progressThread.Abort()

        #Invoke parent function to handle closing properly
        super( ShotgunDialog, self ).accept()

########################################################################
## Shotgun connection layer used to do async work
########################################################################
class ShotgunConnection(QObject):
    workerThread = None #Thread to do actual work in the background
    progressThread = None #Thread for updating progress bar, in order to look "busy"
    
    errorMessage = ""
    statusMessage = ""
    
    selectedTask = ""
    selectedProject = ""
    selectedEntity = ""
    selectedVersion = ""
    taskSequence = "" # The sequence which corresponds to the currently selected task (the task's shot's sequence)
    taskEpisode = "" # The episode which corresponds to the currently selected task (the task's shot's episode)
    
    currentUser = None #connected user
    sgProjectDict = {} #dictionary of Shotgun Projects
    sgTaskDict = {} #dictionary of Shotgun Tasks
    sgEntityDict = {} #dictionary of Shotgun Entities
    versionTemplates = [] #list of version templates
    sgVersionDict = None #dictionary of Shotgun Versions
    
    #Signals used as callbacks to the main thread
    logMessage = pyqtSignal( str, bool )
    errorOccurred = pyqtSignal( str )
    workCompleted = pyqtSignal()
    
    userUpdated = pyqtSignal( str )
    tasksUpdated = pyqtSignal( tuple, str )
    projectsUpdated = pyqtSignal( tuple, str )
    entitiesUpdated = pyqtSignal( tuple, str )
    versionsUpdated = pyqtSignal( tuple, str )
    progressUpdated = pyqtSignal( int, str )
    
    def __init__( self ):
        super( ShotgunConnection, self ).__init__()
    
    #Status thread that periodically updates the UI thread with more info
    def LookBusy( self, showPopup ):
        progress = 0
        
        #Keep looping until the worker thread finishes
        while self.workerThread.IsAlive and IsNoneOrWhiteSpace( self.errorMessage ):
            progress = ( progress + 2 ) % 101
            
            dots = ""
            for i in range( 0, progress / 25 ):
                dots = dots + "."
            
            self.progressUpdated.emit( progress, self.statusMessage + dots )
            Thread.Sleep( 50 )
        
        resetProg = 0
        if IsNoneOrWhiteSpace( self.errorMessage ):
            #no error, rejoice!
            resetProg = 100
            self.progressUpdated.emit( resetProg, "Shotgun request complete" )
        else:
            #there was an error, display it
            resetProg = 0
            self.progressUpdated.emit( resetProg, "error :(" )
            if showPopup:
                self.errorOccurred.emit( self.errorMessage )
            self.errorMessage = ""
        
        self.workCompleted.emit()
        
        #clear the status label after a few secs
        Thread.Sleep( 2500 )
        try:
            self.progressUpdated.emit( resetProg, "" )
        except:
            pass
    
    def ConnectToShotgunAsync( self, userName, showPopup ):
        #TODO: Check if we're already doing async work?
        self.workerThread = Thread( ParameterizedThreadStart( self.ConnectToShotgunMT ) )
        self.workerThread.IsBackground = True
        
        self.progressThread = Thread( ParameterizedThreadStart( self.LookBusy ) )
        self.progressThread.IsBackground = True
        
        # ParamterizedThreadStart only supports a single parameter
        self.workerThread.Start( (userName, showPopup) )
        self.progressThread.Start( showPopup )
        
    #Does the initial connection to shotgun
    def ConnectToShotgunMT( self, params ):
        global shotgunPath
        global stickySettings
        global advancedMode
        global versionSelectMode

        userName, showPopup = params

        try:
            self.statusMessage = "connecting"
            
            newUser = None
            try:
                AddShotgunToPath()
                import ShotgunUtils
                
                self.logMessage.emit( "Connecting to Shotgun as '%s'... " % userName, True )
                newUser = ShotgunUtils.GetUser( userName, shotgunPath )

                if newUser != None:
                    self.logMessage.emit( "done!", False )
                else:
                    self.logMessage.emit( "failed.", False )
            except:
                # always want to put something in errorMessage regardless of popup status because errorMessage will make the progress thread show an error
                # if popups are shown then don't show the log message because it's redundant
                self.errorMessage = "An error occurred while attempting to connect to Shotgun.\nSee Shotgun log window for more details."
                if not showPopup:
                    self.logMessage.emit( "An error occurred while attempting to connect to Shotgun.", False )
                raise
            
            if newUser != None:
                #Initialize defaults to None
                defaultTask = None
                defaultProject = None
                defaultEntity = None
                defaultVersion = None
                
                if self.currentUser == None:
                    #It's our first time through, so load the sticky settings
                    defaultTask = stickySettings.get( "TaskBox", None )
                    
                    if advancedMode:
                        defaultProject = stickySettings.get("ProjectName")
                        defaultEntity = stickySettings.get("EntityName")
                        defaultVersion = stickySettings.get("VersionName")
                elif self.currentUser == newUser:
                    #refreshing, default to current settings
                    defaultTask = self.selectedTask
                    defaultProject = self.selectedProject
                    defaultEntity = self.selectedEntity
                    if versionSelectMode:
                        defaultVersion = self.selectedVersion
                
                #update current user
                self.currentUser = newUser
                self.userUpdated.emit( self.currentUser['name'] )
                
                defaultedTask = self.GetTasksForUserMT( (self.currentUser['login'], defaultTask, ) )
                if not IsNoneOrWhiteSpace( defaultedTask ): 
                    self.SetEpisodeAndSequence( defaultedTask )

                #don't need to fill these out if we're not doing advanced workflow, or if we already have a task (and therefore a project/entity)
                if advancedMode:
                    defaultedProject = self.GetProjectsForUserMT( (self.currentUser['login'], defaultProject, ) )
                    
                    #only need to load entities if no task was defaulted
                    if IsNoneOrWhiteSpace( defaultedTask ):
                        defaultedEntity = self.GetEntitiesForProjectMT( (defaultedProject, defaultEntity, ) )
                        
                        if versionSelectMode and not IsNoneOrWhiteSpace( defaultedEntity ):
                            self.GetVersionsForEntityMT( (defaultedEntity, defaultVersion, ) )
                    else:
                        #Update the Project/Entity boxes based on the selected Task
                        taskObj = self.sgTaskDict.get( defaultTask, None )
                        projectName = ""
                        if taskObj != None and taskObj['project'] != None:
                            projectName = self.sgTaskDict[ defaultTask ]['project']['name']
                        
                        entityName = ""
                        if taskObj != None and taskObj['entity'] != None:
                            entityName = self.sgTaskDict[ defaultTask ]['entity']['name']
                        
                        self.projectsUpdated.emit( ( projectName, ), projectName )
                        self.entitiesUpdated.emit( ( entityName, ), entityName )
                        
                        #Grab versions, if applicable
                        if versionSelectMode:
                            self.GetVersionsForTaskMT( (defaultedTask, defaultVersion, ) )
                elif not IsNoneOrWhiteSpace( defaultedTask ):
                    taskObj = self.sgTaskDict[ defaultedTask ]
                    self.projectsUpdated.emit( tuple(), taskObj['project']['name'] )
                    self.entitiesUpdated.emit( tuple(), taskObj['entity']['name'] )
                    #Grab versions, if applicable
                    if versionSelectMode:
                        self.GetVersionsForTaskMT( (defaultedTask, defaultVersion, ) )
            else:
                self.errorMessage = "Failed to connect to Shotgun with the given login name. Please double-check your login and try again."
                if not showPopup:
                    self.logMessage.emit( "Failed to connect to Shotgun with the given login name.\nPlease double-check your login and try again.", False )
            
        except:
            #Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while connecting to Shotgun.\nSee Shotgun log window for more details."
                if not showPopup:
                    self.logMessage.emit( "An error occurred while connecting to Shotgun.", False )
                    
            self.logMessage.emit( "UNEXPECTED ERROR:", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )
        
    def GetTasksForUserMT( self, args ):
        global shotgunPath
        
        user, defaultTask = args
        
        try:
            tasks = []
            taskNames = []
            self.sgTaskDict = {}
            
            #fall back to current value as a default
            if defaultTask == None:
                defaultTask = self.selectedTask
            
            self.statusMessage = "fetching tasks"
            
            if user != None:
                AddShotgunToPath()
                import ShotgunUtils
                
                self.logMessage.emit( "Getting Task list for user '%s'... " % user, True )
                tasks = ShotgunUtils.GetTasks( user, None, shotgunPath )
                self.logMessage.emit( "done!", False )
                
                taskNames.append( " " )
            
            severalBackups = False
            backupDefault = None
            for task in tasks:
                if task['project'] != None and task['entity'] != None and task['content'] != None:
                    taskName = task['project']['name'] + " > " + task['entity']['name'] + " > " + task['content']
                    
                    #need a unique display name for each entity, so append [id] if it's already in the dict
                    if taskName in self.sgTaskDict and self.sgTaskDict[taskName]['id'] != task['id']:
                        taskName = "%s [id: %d]" % (taskName, task['id'])
                    
                    #check if *just* the task name matches our default (if multiples, ignore these)
                    if defaultTask == task['content']:
                        if not severalBackups and backupDefault == None:
                            backupDefault = taskName
                        else:
                            severalBackups = True
                            backupDefault = None
                    
                    self.sgTaskDict[ taskName ] = task
                    taskNames.append( taskName )
            
            taskNames.sort()
                
            #default to the given task, if available
            if not IsNoneOrWhiteSpace( defaultTask ) and defaultTask in taskNames:
                pass
            elif not IsNoneOrWhiteSpace( backupDefault ):
                defaultTask = backupDefault
            elif len( taskNames ) > 0:
                defaultTask = taskNames[0]
            else:
                defaultTask = None
            
            if not IsNoneOrWhiteSpace( defaultTask ):
                self.logMessage.emit( "Defaulting to task: '%s'" % defaultTask, False )
            
            self.tasksUpdated.emit( tuple( taskNames ), defaultTask )
            
            return defaultTask
            
        except:
            #Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while attempting to collect Task Names from Shotgun.\nSee Shotgun log window for more details."
                
            self.logMessage.emit( "UNEXPECTED ERROR:", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )

        return None
    
    #Gets SG Projects for a given user
    #Returns the defaulted project, if applicable
    def GetProjectsForUserMT( self, args ):
        global shotgunPath
        
        user, defaultProject = args
        
        try:
            projects = []
            projectNames = []
            self.sgProjectDict = {}
            
            #fall back on currently selected value as default
            if defaultProject == None:
                defaultProject = self.selectedProject
            
            self.statusMessage = "fetching projects"
            
            if user != None:
                AddShotgunToPath()
                import ShotgunUtils
                
                self.logMessage.emit( "Getting Project list for user '%s'... " % user, True )
                projects = ShotgunUtils.GetProjects( shotgunPath )
                self.logMessage.emit( "done!", False )
                
                projectNames.append( " " )
            
            backupDefault = None
            for project in projects:
                projectName = project['name']
                self.sgProjectDict[ projectName ] = project
                
                #check case insensitive as a backup
                if projectName.lower() == defaultProject.lower():
                    backupDefault = projectName
                
                projectNames.append( projectName )
            
            projectNames.sort()
            
            #default to the previously selected project, if available
            if not IsNoneOrWhiteSpace( defaultProject ) and defaultProject in projectNames:
                pass
            elif not IsNoneOrWhiteSpace( backupDefault ):
                defaultProject = backupDefault
            elif len( projectNames ) > 0:
                defaultProject = projectNames[0]
            else:
                defaultProject = None
            
            #set the default project
            if not IsNoneOrWhiteSpace( defaultProject ):
                self.logMessage.emit( "Defaulting to project: '%s'" % defaultProject, False )
            
            self.projectsUpdated.emit( tuple( projectNames ), defaultProject )
            
            return defaultProject
        except:
            #Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while attempting to collect Project Names from Shotgun.\nSee Shotgun log window for more details."
            
            self.logMessage.emit( "UNEXPECTED ERROR:", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )
        
        return None
    
    def GetEntitiesForProjectAsync( self, projectName, defaultEntity=None ):
        #TODO: Check if we're already doing async work?
        self.statusMessage = "connecting" # initial status message for progress bar
        self.workerThread = Thread( ParameterizedThreadStart( self.GetEntitiesForProjectMT ) )
        self.workerThread.IsBackground = True
        self.progressThread = Thread( ParameterizedThreadStart( self.LookBusy ) )
        self.progressThread.IsBackground = True
        
        self.workerThread.Start( (projectName, defaultEntity, ) )
        self.progressThread.Start( True )
    
    #Gets SG Entities (Shots/Assets) for a given project
    #Returns the defaulted entity, if applicable
    def GetEntitiesForProjectMT( self, args ):
        global shotgunPath
        
        projectName, defaultEntity = args
        
        try:
            self.sgEntityDict = {}
            entityNames = [" "]
            
            #fall back on currently selected value as a default
            if defaultEntity == None:
                defaultEntity = self.selectedEntity
            
            self.statusMessage =  "fetching entities"
            
            backupDefault = None
            if not IsNoneOrWhiteSpace( projectName ):
                shots = []
                assets = []
                shotNames = []
                assetNames = []
                elementNames = []
                
                project = self.sgProjectDict[ projectName ]
                
                AddShotgunToPath()
                import ShotgunUtils
                
                self.logMessage.emit( "Getting Entity lists for project '%s'... " % projectName, True )
                shots, assets, elements = ShotgunUtils.GetShotsAssetsAndElements( project['id'], shotgunPath )
                self.logMessage.emit( "done!", False )
                
                for shot in shots:
                    shotName = shot['code']
                    
                    if shot.get( "sg_sequence", None ):
                        shotName = "%s > %s" % (shot['sg_sequence']['name'], shotName)
                        
                    #need a unique display name for each entity, so append [id] if it's already in the dict
                    if shotName in self.sgEntityDict and self.sgEntityDict[shotName]['id'] != shot['id']:
                        shotName = "%s [id: %d]" % (shotName, shot['id'])
                        
                    #check *just* the shot name as a backup
                    if shot['code'] == defaultEntity:
                        backupDefault = shotName
                    
                    self.sgEntityDict[ shotName ] = shot
                    shotNames.append( shotName )
                    
                for asset in assets:
                    assetName = asset['code']
                    
                    #need a unique display name for each entity, so append [id] if it's already in the dict
                    if assetName in self.sgEntityDict and self.sgEntityDict[assetName]['id'] != asset['id']:
                        assetName = "%s [id: %d]" % (assetName, asset['id'])
                    
                    #check *just* the asset name as a backup
                    if asset['code'] == defaultEntity:
                        backupDefault = assetName
                    
                    self.sgEntityDict[ assetName ] = asset
                    assetNames.append( assetName )
                    
                for element in elements:
                    elementName = element['code']
                    
                    #need a unique display name for each entity, so append [id] if it's already in the dict
                    if elementName in self.sgEntityDict and self.sgEntityDict[elementName]['id'] != element['id']:
                        elementName = "%s [id: %d]" % (elementName, element['id'])
                    
                    #check *just* the element name as a backup
                    if element['code'] == defaultEntity:
                        backupDefault = elementName
                    
                    self.sgEntityDict[ elementName ] = element
                    elementNames.append( elementName )
            
                shotNames.sort()
                entityNames.extend( shotNames )
                
                assetNames.sort()
                entityNames.extend( assetNames )
                
                elementNames.sort()
                entityNames.extend( elementNames )
            
            #default to given entity if available
            if not IsNoneOrWhiteSpace( defaultEntity ) and defaultEntity in entityNames:
                pass
            elif not IsNoneOrWhiteSpace( backupDefault ):
                defaultEntity = backupDefault
            elif len( entityNames ) > 0:
                defaultEntity = entityNames[0]
            else:
                defaultEntity = None
            
            #set the default entity
            if not IsNoneOrWhiteSpace( defaultEntity ):
                self.logMessage.emit( "Defaulting to entity: '%s'" % defaultEntity, False )
                
            self.entitiesUpdated.emit( tuple( entityNames ), defaultEntity )
            
            return defaultEntity
        except:
            #Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while attempting to collect Entity Names from Shotgun.\nSee Shotgun log window for more details."
            
            self.logMessage.emit( "UNEXPECTED ERROR:", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )
            
        return None
        
    def GetVersionsForEntityAsync( self, entityName, defaultVersion=None ):
        #TODO: Check if we're already doing async work?
        statusMessage = "connecting" # initial status message for progress bar
        self.workerThread = Thread( ParameterizedThreadStart( self.GetVersionsForEntityMT ) )
        self.workerThread.IsBackground = True
        self.progressThread = Thread( ParameterizedThreadStart( self.LookBusy ) )
        self.progressThread.IsBackground = True
        
        self.workerThread.Start( (entityName, defaultVersion, ) )
        self.progressThread.Start( True )
        
    def GetVersionsForEntityMT( self, args ):
        global shotgunPath
        
        entityName, defaultVersion = args
        
        try:
            self.statusMessage =  "fetching versions"
            
            versionCodes = [ "" ]
            self.sgVersionDict = {}
            
            #fall back on currently selected value as a default
            if defaultVersion == None:
                defaultVersion = self.selectedVersion
            
            if not IsNoneOrWhiteSpace( entityName ):
                AddShotgunToPath()
                import ShotgunUtils
                
                self.logMessage.emit( "Getting Version list for entity '%s'... " % entityName, True )
                versions = ShotgunUtils.GetVersions( self.sgEntityDict[entityName]['type'], self.sgEntityDict[entityName]['id'], shotgunPath )
                self.logMessage.emit( "done!", False )
                
                for version in versions :
                    versionCode = version['code']
                    
                    #need a unique display name for each version, so append [#] if it's already in the dict
                    versionDisplayName = versionCode
                    index = 0
                    while versionDisplayName in self.sgVersionDict:
                        index += 1
                        versionDisplayName = "%s [%d]" % (versionCode, index)
                    
                    versionCodes.append( versionDisplayName )
                    self.sgVersionDict[versionDisplayName] = version
            
            #default to given version if available
            if not IsNoneOrWhiteSpace( defaultVersion ) and defaultVersion in versionCodes:
                pass
            elif len( versionCodes ) > 0:
                defaultVersion = versionCodes[0]
            else:
                defaultVersion = None
            
            #set the default version
            if not IsNoneOrWhiteSpace( defaultVersion ):
                self.logMessage.emit( "Defaulting to version: '%s'" % defaultVersion, False )
                
            self.versionsUpdated.emit( tuple( versionCodes ), defaultVersion )
                
            return defaultVersion
        except:
            #Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while attempting to collect Version Names from Shotgun.\nSee Shotgun log window for more details."
            
            self.logMessage.emit( "UNEXPECTED ERROR:", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )
            
        return None
        
    def GetVersionsForTaskAsync( self, taskName, defaultVersion=None ):
        #TODO: Check if we're already doing async work?
        self.statusMessage = "connecting" # initial status message for progress bar
        
        self.workerThread = Thread( ParameterizedThreadStart( self.GetVersionsForTaskMT ) )
        self.workerThread.IsBackground = True
        self.progressThread = Thread( ParameterizedThreadStart( self.LookBusy ) )
        self.progressThread.IsBackground = True
        
        self.workerThread.Start( (taskName, defaultVersion, ) )
        self.progressThread.Start( True )

    def GetVersionsForTaskMT( self, args ):
        global shotgunPath
        
        taskName, defaultVersion = args
        
        try:
            self.statusMessage =  "fetching versions"
            
            versionCodes = [ "" ]
            self.sgVersionDict = {}
            
            #fall back on currently selected value as a default
            if defaultVersion == None:
                defaultVersion = self.selectedVersion
            
            if not IsNoneOrWhiteSpace( taskName ):
                AddShotgunToPath()
                import ShotgunUtils
                
                self.logMessage.emit( "Getting Version list for task '%s'... " % taskName, True )
                versions = ShotgunUtils.GetVersions( self.sgTaskDict[taskName]['entity']['type'], self.sgTaskDict[taskName]['entity']['id'], shotgunPath )
                self.logMessage.emit( "done!", False )
                
                for version in versions :
                    versionCode = version['code']
                    
                    #need a unique display name for each version, so append [#] if it's already in the dict
                    versionDisplayName = versionCode
                    index = 0
                    while versionDisplayName in self.sgVersionDict:
                        index += 1
                        versionDisplayName = "%s [%d]" % (versionCode, index)
                    
                    versionCodes.append( versionDisplayName )
                    self.sgVersionDict[versionDisplayName] = version
                    
                versionCodes.sort()
            
            #default to given version if available
            if not IsNoneOrWhiteSpace( defaultVersion ) and defaultVersion in versionCodes:
                pass
            elif len( versionCodes ) > 0:
                defaultVersion = versionCodes[0]
            else:
                defaultVersion = None
            
            #set the default version
            if not IsNoneOrWhiteSpace( defaultVersion ):
                self.logMessage.emit( "Defaulting to version: '%s'" % defaultVersion, False )
                    
            self.versionsUpdated.emit( tuple( versionCodes ), defaultVersion )
            
            return defaultVersion
        except:
            #Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while attempting to collect Version Names from Shotgun.\nSee Shotgun log window for more details."
            
            self.logMessage.emit( "UNEXPECTED ERROR:", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )
            
        return None

    # This is where the sequence and episode tags are set. The API is scraped to find the proper values
    def SetEpisodeAndSequence( self, taskName ):
        import ShotgunUtils
        mysg = ShotgunUtils.GetShotgun()
        task = self.sgTaskDict[ taskName ]
        
        try:
            filters = [ ['project', 'is', {'type': 'Project', 'id': task['project']['id'] } ], [ 'shots', 'in', {'type': 'Shot', 'id': task['entity']['id'] } ] ]
            fields = ['code', 'shots']
            order = [{'field_name':'created_at','direction':'desc'}]
            seqs = mysg.find("Sequence", filters, fields, order)

            if( len( seqs ) > 0 ):
               self.taskSequence = seqs[0]['code'] + "-" + str(seqs[0]['id'])
            else:
                self.taskSequence = ""
                
        except:
            self.taskSequence = ""
        
        try:
            filters = [ ['project', 'is', {'type': 'Project', 'id': task['project']['id'] } ], ['sg_episode', 'is_not', None], ['id', 'is', task['entity']['id'] ] ] # My project, my shot's ID, episode not null
            fields = ['sg_episode']
            seqs = mysg.find("Shot", filters, fields, order)

            if( len( seqs ) > 0 ):
                self.taskEpisode = seqs[0]['sg_episode']['name']
            else:
                self.taskEpisode = ""
        except:
            self.taskEpisode = ""
        # set the new string representing the sequence of this task and its corresponding shot

####################################################
# Utility functions
###################################################

#Ensures Shotgun stuff is in the PATH so we can import the Shotgun modules
def AddShotgunToPath():
    global shotgunPath
    global shotgunImported
    
    if shotgunPath == None:
        shotgunPath = RepositoryUtils.GetRepositoryPath( "events/Shotgun", True )
        
    if not shotgunImported:
        sys.path.append( shotgunPath )
        shotgunImported = True
        
    return shotgunPath

def IsNoneOrWhiteSpace( someString ):
    return someString == None or someString.strip() == ""