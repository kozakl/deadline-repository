from __future__ import print_function
import os
import sys
import traceback
import time
import threading
import json

import nim_core.nim_api as nimAPI

from System.Threading import *

from Deadline.Scripting import *
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

########################################################################
## Globals
########################################################################
scriptDialog = None

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__( *args ):
    global scriptDialog
    parentAppName = ""

    if len( args ) > 0:
        parentAppName = args[0]

    scriptDialog = NimDialog( parentAppName )

    # Add control buttons
    scriptDialog.AddGrid()
    scriptDialog.AddHorizontalSpacerToGrid( "HSpacer", 0, 0 )
    okButton = scriptDialog.AddControlToGrid( "OkButton", "ButtonControl", "OK", 0, 1, expand=False )
    okButton.clicked.connect( OKButtonClicked )
    cancelButton = scriptDialog.AddControlToGrid( "CancelButton", "ButtonControl", "Cancel", 0, 2, expand=False )
    cancelButton.clicked.connect( CancelButtonClicked )
    scriptDialog.EndGrid()

    scriptDialog.ShowDialog( True )

def OKButtonClicked():
    global scriptDialog

    if not scriptDialog.Validate():
        return

    settingsDict = scriptDialog.GetSettingsDictionary()
    
    for key in settingsDict.keys():
        ClientUtils.LogText( "%s=%s" % ( key, settingsDict[key] ) )

    scriptDialog.CloseConnection()
    super( NimDialog, scriptDialog ).accept()

def CancelButtonClicked():
    scriptDialog.CloseConnection()
    super( NimDialog, scriptDialog ).reject()

########################################################################
## Subclass of DeadlineScriptDialog for the UI
########################################################################
class NimDialog( DeadlineScriptDialog ):
    # Signals used as callbacks to the main thread. They need to be defined at the class level
    logMessage = pyqtSignal( str, bool )
    workCompleted = pyqtSignal()
    progressUpdated = pyqtSignal( int, str )

    def __init__( self, parentAppName="", parent=None, nimInfo={} ):
        super( NimDialog, self ).__init__( parent )

        self.parentAppName = parentAppName
        self.enableUI = True

        self.nimInfo = nimInfo

        self.nim_user = ""
        self.nim_userID = ""
        self.nim_jobID = ""
        self.nim_showID = ""
        self.nim_shotID = ""
        self.nim_assetID = ""

        self.nim_jobName = ""
        self.nim_showName = ""
        self.nim_class = ""
        self.nim_taskID = ""
        self.nim_shotName = ""
        self.nim_assetName = ""
        self.nim_elementTypeID = ""
        self.nim_itemID = ""

        self.nim_users = None
        self.nim_usersDict = {}
        self.pref_user = ""

        self.nim_jobs = None
        self.nim_jobsDict = {}
        self.pref_job = ""

        self.nim_assets = None
        self.nim_assetsDict = {}
        self.pref_asset = ""

        self.nim_shows = None
        self.nim_showsDict = {}
        self.pref_show = ""

        self.nim_shots = None
        self.nim_shotsDict = {}
        self.pref_shot = ""

        self.nim_tasks = None
        self.nim_tasksDict = {}
        self.pref_task = ""

        self.nim_elementTypes = None
        self.nim_elementTypesDict = {}
        self.pref_elementType = ""

        self.logMessages = [""]
        self.errorMessage = ""
        self.statusMessage = ""

        self.workerThread = None
        self.progressThread = None

        # Hook up the signals
        self.logMessage.connect( self.writeToLogBox )
        self.progressUpdated.connect( self.UpdateProgressBar )
        self.workCompleted.connect( self.AsyncCallback )

        # Sticky settings
        self.settings = ( "nim_userChooser", "nim_jobChooser", "nim_typeChooser", "nim_assetChooser", "nim_showChooser", "nim_shotChooser", "TaskBox", "nim_elementTypeChooser", "RenderBox", "DescriptionBox" )
        self.settingsDict = {}

        self.config = RepositoryUtils.GetEventPluginConfig( "NIM" )


        self.loaded = False
        self.pulledSettings = False
        self.pulledFromScene = False
        
        self.SetTitle( "NIM Scene Information" )

        dialogWidth = 480
        controlHeight = -1 #20

        self.AddControl( "Separator1", "SeparatorControl", "NIM Fields", dialogWidth, controlHeight )

        self.AddGrid()
        curRow = 0

        #User
        self.AddControlToGrid( "UserLabel", "LabelControl", "User", curRow, 0, "The current user.", expand=False )
        self.nim_userChooser = self.AddControlToGrid( "nim_userChooser", "ComboControl", "", curRow, 1, colSpan=1 )
        self.loginButton = self.AddControlToGrid( "LoginButton", "ButtonControl", "Refresh", curRow, 2, expand=False )
        self.loginButton.ValueModified.connect( self.loginButtonPressed )
        self.loginButton.setDefault( True ) #Start off with the login button as default
        curRow += 1

        #Job Name
        self.AddControlToGrid( "JobLabel", "LabelControl", "Job", curRow, 0, "The job for the current task.", expand=False )
        self.nim_jobChooser = self.AddControlToGrid( "nim_jobChooser", "ComboControl", "", curRow, 1, colSpan=2 )
        curRow += 1

        #Type Name
        self.AddControlToGrid( "TypeLabel", "LabelControl", "Type", curRow, 0, "Select a task type.", expand=False )
        self.nim_typeChooser = self.AddComboControlToGrid( "nim_typeChooser", "ComboControl", "", (), curRow, 1, colSpan=2 )
        self.nim_typeChooser.addItem("Asset")
        self.nim_typeChooser.addItem("Shot")
            
        curRow += 1
        
        #Asset Name
        self.AddControlToGrid( "nim_assetLabel", "LabelControl", "Asset", curRow, 0, "The asset for the current task.", expand=False )
        self.nim_assetChooser = self.AddControlToGrid( "nim_assetChooser", "ComboControl", "", curRow, 1, colSpan=2 )
        curRow += 1

        #Show Name
        self.AddControlToGrid( "nim_showLabel", "LabelControl", "Show", curRow, 0, "The show for the current task.", expand=False )
        self.nim_showChooser = self.AddControlToGrid( "nim_showChooser", "ComboControl", "", curRow, 1, colSpan=2 )
        curRow += 1

        #Shot Name
        self.AddControlToGrid( "nim_shotLabel", "LabelControl", "Shot", curRow, 0, "The shot for the current task.", expand=False )
        self.nim_shotChooser = self.AddControlToGrid( "nim_shotChooser", "ComboControl", "", curRow, 1, colSpan=2 )
        curRow += 1

        self.AddControlToGrid( "TaskLabel", "LabelControl", "Task", curRow, 0, "Select a task that is assigned to the current user.", expand=False )
        self.nim_taskChooser = self.AddComboControlToGrid( "TaskBox", "ComboControl", "", (), curRow, 1, colSpan=2 )
        curRow += 1

        self.AddControlToGrid( "nim_elementLabel", "LabelControl", "Element Type", curRow, 0, "", expand=False )
        self.nim_elementTypeChooser = self.AddComboControlToGrid( "nim_elementTypeChooser", "ComboControl", "", (), curRow, 1, colSpan=2 )
        curRow += 1
        
        self.AddControlToGrid( "RenderLabel", "LabelControl", "Render Name", curRow, 0, "The name to give the new Render.", expand=False )
        self.AddControlToGrid( "RenderBox", "TextControl", "", curRow, 1, colSpan=2 )
        curRow += 1

        self.AddControlToGrid( "DescriptionLabel", "LabelControl", "Description", curRow, 0, "A comment describing the render.", expand=False )
        self.AddControlToGrid( "DescriptionBox", "TextControl", "", curRow, 1, colSpan=2 )
        curRow += 1
        self.EndGrid()

        self.AddGrid()
        curRow = 0
        self.AddControlToGrid( "LogLabel", "LabelControl", "NIM Log:", curRow, 0, expand=False )
        curRow += 1

        self.logBox = self.AddComboControlToGrid( "LogBox", "ListControl", "", (""), curRow, 0, colSpan=5 )
        self.logBox.setSelectionMode( QAbstractItemView.ExtendedSelection )
        curRow += 1

        self.EndGrid()

        self.AddGrid()
        curRow = 0
        self.AddRangeControlToGrid( "ProgressBar", "ProgressBarControl", 0, 0, 100, 0, 0, curRow, 0, expand=False )
        self.statusLabel = self.AddControlToGrid( "StatusLabel", "LabelControl", "", curRow, 1 )
        self.statusLabel.setMinimumWidth( 100 )
        self.EndGrid()

        self.nim_userChooser.currentIndexChanged.connect( self.nim_userChanged )
        self.nim_jobChooser.currentIndexChanged.connect( self.nim_jobChanged )
        self.nim_typeChooser.currentIndexChanged.connect( self.nim_typeChanged )
        self.nim_assetChooser.currentIndexChanged.connect( self.nim_assetChanged )
        self.nim_showChooser.currentIndexChanged.connect( self.nim_showChanged )
        self.nim_shotChooser.currentIndexChanged.connect( self.nim_shotChanged )
        self.nim_taskChooser.currentIndexChanged.connect( self.nim_taskChanged )
        self.nim_elementTypeChooser.currentIndexChanged.connect( self.nim_elementTypeChanged )

        if self.isNimLoaded():
            self.getNimInfo()
        else:
            self.loadStickySettings( self.GetSettingsFilename() )

        if self.config.GetBooleanConfigEntryWithDefault( "AutoConnect", True ):
            self.loginButtonPressed( None )
        self.UpdateEnabledStatus()

    ########################################################################
    ## Utility Functions
    ########################################################################

    def saveStickySettings( self, fileName ):
        if self.loaded or self.pulledFromScene:
            stickySettings = {
                "userID" : self.nim_userID,
                "jobID" : self.nim_jobID,
                "showID" : self.nim_showID,
                "shotID" : self.nim_shotID,
                "assetID" : self.nim_assetID,
                "taskID" : self.nim_taskID,
                "elementTypeID" : self.nim_elementTypeID,
                "itemID" : self.nim_itemID,
                
                "class" : self.nim_class,
                "userName" : self.nim_user,
                "jobName" : self.nim_jobName,
                "showName" : self.nim_showName,
                "shotName" : self.nim_shotName,
                "assetName" : self.nim_assetName,
                "taskName" : self.GetValue( "TaskBox" ),
                "elementTypeChooser" : self.GetValue( "nim_elementTypeChooser" ),
                "renderName" : self.GetValue( "RenderBox" ),
                "description" : self.GetValue( "DescriptionBox" )
            }

            try:
                with open( fileName, "w" ) as settingsFile:
                    settingsFile.write( json.dumps( stickySettings ) )
            except:
                self.logMessage.emit( "Failed to write sticky settings...", False )
                self.logMessage.emit( traceback.format_exc(), False )

    def loadStickySettings( self, fileName ):
        stickySettings = {}
        self.logMessage.emit( "Retrieving sticky settings... ", True )

        try:
            with open( fileName, "r" ) as settingsFile:
                stickySettings = json.loads( settingsFile.read() )
        except:
            pass

        self.logMessage.emit( "done!", False )
        if len( stickySettings ) > 0:
            self.setUIValues( stickySettings )
            if self.Validate( True ):
                self.pulledSettings = True
                self.nim_updateTask()
                self.nim_updateElementTypes()

    def compareNimAndStickySettings( self, stickyFilename, nimDict ):
        stickySettings = {}
        try:
            with open( stickyFilename, "r" ) as settingsFile:
                stickySettings = json.loads( settingsFile.read() )
        except:
            pass

        if not stickySettings.get( "itemID", "" ) == nimDict.get( "itemID", "" ):
            return

        if not stickySettings.get( "jobID", "" ) == nimDict.get( "jobID", "" ):
            return

        if not stickySettings.get( "class", "" ) == nimDict.get( "class", "" ):
            return
        else:
            if nimDict[ "class" ] == "ASSET":
                if not stickySettings.get( "assetID", "" ) == nimDict.get( "assetID", "" ):
                    return
            elif nimDict[ "class" ] == "SHOT":
                if not stickySettings.get( "showID", "" ) == nimDict.get( "showID", "" ):
                    return
                if not stickySettings.get( "shotID", "" ) == nimDict.get( "shotID", "" ):
                    return

        # Nim info matches what's in sticky settings. Means we should load the rest of the sticky settings
        nimDict[ "taskID" ] = stickySettings[ "taskID" ]
        nimDict[ "taskName" ] = stickySettings[ "taskName" ]
        nimDict[ "elementTypeID" ] = stickySettings[ "elementTypeID" ]
        nimDict[ "elementTypeChooser" ] = stickySettings[ "elementTypeChooser" ]
        nimDict[ "renderName" ] = stickySettings[ "renderName" ]
        nimDict[ "description" ] = stickySettings[ "description" ]

    def isNimLoaded( self ):
        return bool( self.nimInfo )

    def getNimInfo( self ):
        nimDict = {
            "userID" : self.nimInfo.get( "user", {} ).get( "ID", "" ),
            "userName" : self.nimInfo.get( "user", {} ).get( "name", "" ),
            "jobID" : self.nimInfo.get( "job", {} ).get( "ID", "" ),
            "jobName" : self.nimInfo.get( "job", {} ).get( "name", "" ),
            "showID" : self.nimInfo.get( "show", {} ).get( "ID", "" ),
            "showName" : self.nimInfo.get( "show", {} ).get( "name", "" ),
            "shotID" : self.nimInfo.get( "shot", {} ).get( "ID", "" ), # Can be "None"...?
            "shotName" : self.nimInfo.get( "shot", {} ).get( "name", "" ),
            "assetID" : self.nimInfo.get( "asset", {} ).get( "ID", "" ),
            "assetName" : self.nimInfo.get( "asset", {} ).get( "name", "" ),

            "class" : self.nimInfo.get( "class", "" ),
            "itemID" : "",

            # Can't be grabbed from the scene, user MUST select
            "taskID" : "",
            "taskName" : "",
            "elementTypeID" : "",
            "elementTypeChooser" : "",
            "renderName" : "",
            "description" : ""
        }

        if nimDict[ "class" ] == "ASSET":
            nimDict[ "itemID" ] = nimDict[ "assetID" ]
        elif nimDict[ "class" ] == "SHOT":
            nimDict[ "itemID" ] = nimDict[ "shotID" ]

        self.compareNimAndStickySettings( self.GetSettingsFilename(), nimDict )
        self.setUIValues( nimDict )
        self.logMessage.emit( "done!", False )
        if self.Validate( True ):
            self.pulledFromScene = True
            self.nim_updateElementTypes()
            self.nim_updateTask()

    def setUIValues( self, nimDict ):
        userID = nimDict.get( "userID", "" )
        userName = nimDict.get( "userName", "" )
        if userName:
            self.nim_userChooser.addItem( userName )
            self.SetValue( "nim_userChooser", userName )
            self.nim_userID = userID

        jobID = nimDict.get( "jobID", "" )
        jobName = nimDict.get( "jobName", "" )
        if jobName:
            self.nim_jobChooser.addItem( jobName )
            self.SetValue( "nim_jobChooser", jobName )
            self.nim_jobID = jobID

        classType = nimDict.get( "class", "" )
        if classType:
            self.SetValue( "nim_typeChooser", classType.title() )
            self.nim_class = classType

        assetID = nimDict.get( "assetID", "" )
        assetName = nimDict.get( "assetName", "" )
        if assetName:
            self.nim_assetChooser.addItem( assetName )
            self.SetValue( "nim_assetChooser", assetName )
            self.nim_assetID = assetID

        showID = nimDict.get( "showID", "" )
        showName = nimDict.get( "showName", "" )
        if showName:
            self.nim_showChooser.addItem( showName )
            self.SetValue( "nim_showChooser", showName )
            self.nim_showID = showID

        shotID = nimDict.get( "shotID", "" )
        shotName = nimDict.get( "shotName", "" )
        if shotName:
            self.nim_shotChooser.addItem( shotName )
            self.SetValue( "nim_shotChooser", shotName )
            self.nim_shotID = shotID

        taskID = nimDict.get( "taskID", "" )
        taskName = nimDict.get( "taskName", "" )
        if taskName:
            self.nim_taskChooser.addItem( taskName )
            self.SetValue( "TaskBox", taskName )
            self.nim_taskID = taskID

        itemID = nimDict.get( "itemID", "" )
        if itemID:
            self.nim_itemID = itemID

        elementTypeID = nimDict.get( "elementTypeID", "" )
        elementTypeChooser = nimDict.get( "elementTypeChooser", "" )
        if elementTypeChooser:
            self.nim_elementTypeChooser.addItem( elementTypeChooser )
            self.SetValue( "nim_elementTypeChooser", elementTypeChooser )
            self.nim_elementTypeID = elementTypeID

        renderName = nimDict.get( "renderName", "" )
        if renderName:
            self.SetValue( "RenderBox", renderName )

        description = nimDict.get( "description", "" )
        if description:
            self.SetValue( "DescriptionBox", description )

    def GetSettingsFilename(self):
        return os.path.join( ClientUtils.GetUsersSettingsDirectory(), str(self.parentAppName) + "NIMSettings.ini" )

    #Updates which controls are enabled based on the UI's current state
    def UpdateEnabledStatus( self ):
        try:
            finishedWorking = not self.workerThread or not self.workerThread.IsAlive
            pulled = ( self.pulledSettings or self.pulledFromScene ) and self.enableUI
            labelEnabled = ( self.loaded or pulled ) and self.enableUI
            boxEnabled = self.loaded and self.enableUI

            self.SetEnabled( "nim_userChooser", finishedWorking and boxEnabled )
            self.SetEnabled( "UserLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "LoginButton", finishedWorking and self.enableUI )
            self.SetEnabled( "JobLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "nim_jobChooser", finishedWorking and boxEnabled )
            self.SetEnabled( "TypeLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "nim_typeChooser", finishedWorking and boxEnabled )

            self.SetEnabled( "nim_assetLabel", finishedWorking and labelEnabled and self.nim_class == "ASSET" )
            self.SetEnabled( "nim_assetChooser", finishedWorking and boxEnabled and self.nim_class == "ASSET" )
            self.SetEnabled( "nim_showLabel", finishedWorking and labelEnabled and self.nim_class == "SHOT" )
            self.SetEnabled( "nim_showChooser", finishedWorking and boxEnabled and self.nim_class == "SHOT" )
            self.SetEnabled( "nim_shotLabel", finishedWorking and labelEnabled and self.nim_class == "SHOT" )
            self.SetEnabled( "nim_shotChooser", finishedWorking and boxEnabled and self.nim_class == "SHOT" )  

            self.SetEnabled( "TaskLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "TaskBox", finishedWorking and ( boxEnabled or pulled ) )
            self.SetEnabled( "nim_elementLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "nim_elementTypeChooser", finishedWorking and ( boxEnabled or pulled ) )
            self.SetEnabled( "RenderLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "RenderBox", finishedWorking and ( boxEnabled or pulled ) )
            self.SetEnabled( "DescriptionLabel", finishedWorking and labelEnabled )
            self.SetEnabled( "DescriptionBox", finishedWorking and ( boxEnabled or pulled ) )
        except:
            self.logMessage.emit( traceback.format_exc() , False )

    @pyqtSlot( str, bool )
    def writeToLogBox( self, message, suppressNewLine=False ):
        try:
            #Make sure it's a python string! (and not a filthy QString)
            message = str( message )
            lines = message.splitlines()

            if not self.logMessages:
                self.logMessages = [""]
            
            for i in range( 0, len(lines) ):
                line = lines[ i ]
                self.logMessages[ -1 ] += line

                #check if we should add a new line or not
                if not suppressNewLine or i < (len( lines ) - 1):
                    self.logMessages.append( "" )

            self.SetItems( "LogBox", tuple( self.logMessages ) )
        except:
            #log box might not be initialized yet, just suppress the exception and wrgftite to trace
            ClientUtils.LogText( traceback.format_exc() )

    # Slot that updates the progress bar & status message
    @pyqtSlot( int, str )
    def UpdateProgressBar( self, progress, statusMessage ):
        self.SetValue( "ProgressBar", progress )
        self.SetValue( "StatusLabel", statusMessage )

    @pyqtSlot()
    def AsyncCallback( self ):
        #General updating stuff that should be done whenever an operation completes
        self.UpdateEnabledStatus()

    ########################################################################
    ## UI Event Handlers
    ########################################################################
    def loginButtonPressed(self, *args):
        #TODO: Check if we're already doing async work?
        self.workerThread = Thread( ThreadStart( self.ConnectToNimMT ) )
        self.workerThread.IsBackground = True

        self.progressThread = Thread( ThreadStart( self.LookBusy ) )
        self.progressThread.IsBackground = True

        self.workerThread.Start()
        self.progressThread.Start()

    def ConnectToNimMT( self ):
        try:
            self.statusMessage = 'Connecting'

            userID = nimAPI.connect( params={'q': 'getUserID', 'u': str(self.nim_user)} )
            if type(userID)==type(list()) and len(userID)==1 :
                currentUserID = userID[0]['ID']
            else:
                currentUserID = 0

            nimUsers = nimAPI.connect( params={'q': 'getUsers' } )
            if type(nimUsers) == type( list() ):
                if len( nimUsers ) == 0:
                    self.nim_users = nimUsers
                elif nimUsers[0].get( "result", True ):
                    self.nim_users = nimUsers
                else:
                    errorMessage = nimUsers[0].get( "error", "" )
                    if errorMessage:
                        self.errorMessage = errorMessage
                    else:
                        self.errorMessage = "Failed to pull user data from NIM"
                    self.logMessage.emit( self.errorMessage, True )

            if not self.loaded:
                userIndex = 0
                userIter = 0
                if self.nim_users:
                    self.nim_userChooser.clear()
                    if len(self.nim_users)>0:
                        for userInfo in self.nim_users:
                            self.nim_usersDict[userInfo['username']] = userInfo['ID']
                        for key, value in sorted(self.nim_usersDict.items(), reverse=False):
                            self.nim_userChooser.addItem(key)
                            if currentUserID == value:
                                self.pref_user = key
                                userIndex = userIter
                            userIter += 1

                        if self.pref_user != '':
                            self.nim_userChooser.setCurrentIndex(userIndex)

                    self.loaded = True
                    self.nim_typeChanged()
        except:
            # Make sure we set this to notify other threads that this failed
            if IsNoneOrWhiteSpace( self.errorMessage ):
                self.errorMessage = "An error occurred while connecting to NIM."

            self.logMessage.emit( "---UNEXPECTED ERROR---", False )
            self.logMessage.emit( str( sys.exc_info()[0] ), False )
            self.logMessage.emit( str( sys.exc_info()[1] ), False )
            self.logMessage.emit( "---END ERROR INFO---", False )

    def LookBusy( self ):
        try:
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
                # No error, rejoice!
                resetProg = 100
                self.progressUpdated.emit( resetProg, "NIM request complete" )
            else:
                # There was an error, display it
                resetProg = 0
                self.progressUpdated.emit( resetProg, "error :(" )
                
                self.logMessage.emit( self.errorMessage, False )
                self.errorMessage = ""

            self.workCompleted.emit()

            # Clear the status label after a few secs
            Thread.Sleep( 2500 )
            try:
                self.progressUpdated.emit( resetProg, "" )
            except:
                pass
        except:
            self.logMessage.emit( traceback.format_exc(), False )

    def nim_userChanged(self):
        '''Action when user is selected'''
        self.nim_user = self.nim_userChooser.currentText()
        if self.nim_user and self.nim_usersDict and self.nim_user in self.nim_usersDict:
            self.nim_userID = self.nim_usersDict[self.nim_user]
            self.nim_updateJob()

    def nim_updateJob(self):
        self.nim_jobs = {}
        self.nim_jobsDict = {}
        
        #  Build dictionary of jobs :
        jobInfo = nimAPI.connect( params={'q': 'getUserJobs', 'u': self.nim_userID} )
        for job in jobInfo :
            self.nim_jobs[str(job['number'])+'_'+str(job['jobname'])]=str(job['ID'])
        
        jobIndex = 0
        jobIter = 0
        self.nim_jobChooser.clear()
        try:
            if len(self.nim_jobs)>0:
                for key, value in sorted(self.nim_jobs.items(), reverse=True):
                    self.nim_jobChooser.addItem(key)
                    if self.nim_jobID == value:
                        self.pref_job = key
                        jobIndex = jobIter
                    jobIter += 1

                if self.pref_job != '':
                    self.nim_jobChooser.setCurrentIndex(jobIndex)
            else:
                self.nim_assetChooser.clear()
                self.nim_showChooser.clear()
                self.nim_shotChooser.clear()
                self.nim_taskChooser.clear()
        except:
            print("Failed to Update Jobs")
            print( traceback.format_exc() )
            self.nim_assetChooser.clear()
            self.nim_showChooser.clear()
            self.nim_shotChooser.clear()
            self.nim_taskChooser.clear()
            
    def nim_jobChanged(self):
        '''Action when job is selected'''
        job = self.nim_jobChooser.currentText()
        try:
            if job:
                self.pref_job = job
                self.nim_jobName = job
                if self.nim_jobs and job in self.nim_jobs:
                    self.nim_jobID = self.nim_jobs[job]
                
                    self.nim_updateAsset()
                    self.nim_updateShow()
                    self.nim_updateElementTypes()
        except:
            print( "Failed to Read Current Job" )
            print( traceback.format_exc() )

    def nim_typeChanged(self):
        nimType = self.nim_typeChooser.currentText()

        if nimType == "Asset":
            self.nim_class = "ASSET"
            self.SetEnabled( "nim_assetLabel", 1)
            self.SetEnabled( "nim_assetChooser", 1)
            self.SetEnabled( "nim_showLabel", 0)
            self.SetEnabled( "nim_showChooser", 0)
            self.SetEnabled( "nim_shotLabel", 0)
            self.SetEnabled( "nim_shotChooser", 0)
            self.nim_assetChanged()
        else:
            self.nim_class = "SHOT"
            self.SetEnabled( "nim_assetLabel", 0)
            self.SetEnabled( "nim_assetChooser", 0)
            self.SetEnabled( "nim_showLabel", 1)
            self.SetEnabled( "nim_showChooser", 1)
            self.SetEnabled( "nim_shotLabel", 1)
            self.SetEnabled( "nim_shotChooser", 1)
            self.nim_shotChanged()

        self.nim_updateTask()

    def nim_updateAsset(self):
        self.nim_assetsDict = {}
        self.nim_assets = nimAPI.connect( params={'q': 'getAssets', 'ID': str(self.nim_jobID)} )

        assetIndex = 0
        assetIter = 0
        self.nim_assetChooser.clear()
        try:
            if len(self.nim_assets)>0:
                for asset in self.nim_assets:
                    self.nim_assetsDict[asset['name']] = asset['ID']
                for key, value in sorted(self.nim_assetsDict.items(), reverse=False):
                    self.nim_assetChooser.addItem(key)
                    if self.nim_assetID == value:
                        self.pref_asset = key
                        assetIndex = assetIter
                    assetIter += 1

                if self.pref_asset != '':
                    self.nim_assetChooser.setCurrentIndex(assetIndex)
            else:
                self.nim_taskChooser.clear()
        except:
            print("Failed to Update Assets")
            print( traceback.format_exc() )
            self.nim_taskChooser.clear()

    def nim_assetChanged(self):
        '''Action when asset is selected'''
        self.nim_assetName = self.nim_assetChooser.currentText()
        if self.nim_assetName and self.nim_assetsDict and self.nim_assetName in self.nim_assetsDict:
            self.nim_assetID = self.nim_assetsDict[self.nim_assetName]
            self.pref_asset = self.nim_assetName

            if self.nim_class == "ASSET":
                self.nim_itemID = self.nim_assetID
                self.nim_updateTask()

    def nim_updateShow(self):
        self.nim_showsDict = {}
        self.nim_shows = nimAPI.connect( params={'q': 'getShows', 'ID': str(self.nim_jobID)} )

        showIndex = 0
        showIter = 0
        self.nim_showChooser.clear()
        try:
            if len(self.nim_shows)>0:
                for show in self.nim_shows:
                    self.nim_showsDict[show['showname']] = show['ID']
                for key, value in sorted(self.nim_showsDict.items(), reverse=False):
                    self.nim_showChooser.addItem(key)
                    if self.nim_showID == value:
                        self.pref_show = key
                        showIndex = showIter
                    showIter += 1

                if self.pref_show != '':
                    self.nim_showChooser.setCurrentIndex(showIndex)
            else:
                self.nim_shotChooser.clear()
                if self.nim_class == "SHOT":
                    self.nim_taskChooser.clear()
        except:
            print("Failed to Update Shows")
            print( traceback.format_exc() )
            self.nim_shotChooser.clear()
            if self.nim_class == "SHOT":
                self.nim_taskChooser.clear()

    def nim_showChanged(self):
        '''Action when show is selected'''
        self.nim_showName = self.nim_showChooser.currentText()
        if self.nim_showName and self.nim_showsDict and self.nim_showName in self.nim_showsDict:
            self.nim_showID = self.nim_showsDict[self.nim_showName]
            self.pref_show = self.nim_showName
            self.nim_updateShot()

    def nim_updateShot(self):
        self.nim_shotsDict = {}
        self.nim_shots = nimAPI.connect( params={'q': 'getShots', 'ID': self.nim_showID} )

        shotIndex = 0
        shotIter = 0
        self.nim_shotChooser.clear()
        try:
            if len(self.nim_shots)>0:
                for shot in self.nim_shots:
                    self.nim_shotsDict[shot['name']] = shot['ID']
                for key, value in sorted(self.nim_shotsDict.items(), reverse=False):
                    self.nim_shotChooser.addItem(key)
                    if self.nim_shotID == value:
                        self.pref_shot = key
                        shotIndex = shotIter
                    shotIter += 1

                if self.pref_shot != '':
                    self.nim_shotChooser.setCurrentIndex(shotIndex)
            else:
                if self.nim_class == "SHOT":
                    self.nim_taskChooser.clear()
        except:
            print("Failed to Update Shots")
            print( traceback.format_exc() )

    def nim_shotChanged(self):
        '''Action when shot is selected'''
        self.nim_shotName = self.nim_shotChooser.currentText()
        if self.nim_shotName and self.nim_shotsDict and self.nim_shotName in self.nim_shotsDict:
            self.nim_shotID = self.nim_shotsDict[self.nim_shotName]
            
            self.pref_shot = self.nim_shotName
            
            if self.nim_class == "SHOT":
                self.nim_itemID = self.nim_shotID
                self.nim_updateTask()

    def nim_updateTask(self):
        self.nim_tasksDict = {}  
        if not self.nim_itemID:
            return
            
        self.nim_tasks = []
        nimTasks = nimAPI.connect( params={'q': 'getTaskInfo', 'class': self.nim_class, 'itemID': self.nim_itemID } )
        if type(nimTasks) == type( list() ):
            if len( nimTasks ) == 0:
                self.nim_tasks = nimTasks
            elif nimTasks[0].get( "result", True ):
                self.nim_tasks = nimTasks
            else:
                errorMessage = nimTasks[0].get( "error", "" )
                if errorMessage:
                    self.errorMessage = errorMessage
                    self.logMessage.emit( errorMessage, False )
                else:
                    self.errorMessage = errorMessage
                    self.logMessage.emit( "Failed to pull task data from NIM", True )

        pref_task = ''
        taskIndex = 0
        taskIter = 0
        oldId = self.nim_taskID
        self.nim_taskChooser.clear()
        self.nim_taskID = oldId
        try:
            if len(self.nim_tasks)>0:
                self.nim_tasksDict['Select...'] = 0
                for task in self.nim_tasks:
                    
                    taskID = task['taskID'] if task['taskID'] else 0
                    taskName = task['taskName'] if task['taskName'] else ''
                    taskDesc = task['taskDesc'] if task['taskDesc'] else ''
                    taskUser = task['username'] if task['username'] else ''
                    task_key = taskID+": "+taskName+" - "+taskUser
                    self.nim_tasksDict[task_key] = taskID
                
                self.nim_taskChooser.addItem("Select...")
                self.nim_taskID = oldId
                for key, value in self.nim_tasksDict.items():
                    if key is not "Select...":
                        self.nim_taskChooser.addItem(key)
                    #Set to passed taskID
                    value = int(value)
                    if self.nim_taskID == value and value > 0:
                        pref_task = key
                        taskIndex = taskIter +1
                    taskIter += 1
                
                self.nim_taskChooser.setCurrentIndex(taskIndex)
        except:
            print( "Failed to Update Tasks" )
            print( traceback.format_exc() )

    def nim_taskChanged( self, *args ):
        taskKey = self.nim_taskChooser.currentText()
        if taskKey == "":
            self.nim_taskID = 0
        else:
            if taskKey and self.nim_tasksDict and taskKey in self.nim_tasksDict:
                self.nim_taskID = int(self.nim_tasksDict[taskKey])

    def nim_updateElementTypes( self ):
        self.nim_elementTypesDict = {}
        self.nim_elementTypes = nimAPI.connect( params={ 'q': 'getElementTypes' }  )
        oldType = self.nim_elementTypeID
        self.nim_elementTypeChooser.clear()
        self.nim_elementTypeID = oldType
        try:
            if( len( self.nim_elementTypes ) > 0 ):
                self.nim_elementTypesDict[""] = 0
                for element in self.nim_elementTypes:
                    self.nim_elementTypesDict[ element['name'] ] = element['ID']

                self.nim_elementTypeChooser.addItem("")
                self.nim_elementTypeID = oldType
                elementTypeIndex = 0
                for counter, (key, value) in enumerate(self.nim_elementTypesDict.items()):
                    if key is not "":
                        self.nim_elementTypeChooser.addItem( key )
                    
                    if self.nim_elementTypeID == value and value > 0:
                        self.pref_elementType = key
                        elementTypeIndex = counter

                if self.pref_elementType != "":
                    self.nim_elementTypeChooser.setCurrentIndex(elementTypeIndex)
        except:
            print( "Failed to Update Elements" )
            print( traceback.format_exc() )

    def nim_elementTypeChanged( self, *args ):
        elementTypeKey = self.nim_elementTypeChooser.currentText()
        if elementTypeKey == "":
            self.nim_elementTypeID = 0
        else:
            if elementTypeKey and self.nim_elementTypesDict and elementTypeKey in self.nim_elementTypesDict:
                self.nim_elementTypeID = self.nim_elementTypesDict[elementTypeKey]

    def Validate( self, loadingPulledValues=False ):
        validationPassed = True
        self.logMessage.emit( "Validating selected values...", True )

        if self.loaded and IsNoneOrWhiteSpace( self.nim_userID ):
            self.logMessage.emit( "Validation failed on User", False )
            validationPassed = False

        if self.loaded and IsNoneOrWhiteSpace( self.nim_jobID ):
            self.logMessage.emit( "Validation failed on Job", False )
            validationPassed = False

        if not loadingPulledValues and ( self.nim_taskID == 0 or self.nim_taskID == None or self.nim_taskID == "" ):
            self.logMessage.emit( "Validation failed on Task", False )
            validationPassed = False

        if self.nim_class == "SHOT":
            if IsNoneOrWhiteSpace( self.nim_showName ):
                self.logMessage.emit( "Validation failed on Show", False )
                validationPassed = False

            if IsNoneOrWhiteSpace( self.nim_shotName ):
                self.logMessage.emit( "Validation failed on Shot", False )
                validationPassed = False

        if self.nim_class == "ASSET":
            if IsNoneOrWhiteSpace( self.nim_assetName ):
                self.logMessage.emit( "Validation failed on Asset", False )
                validationPassed = False
        
        if not validationPassed:
            validationMessage = "You must complete this form in order to create a new NIM Version for this job.\n\nPlease fill in any missing info before proceeding."
            self.ShowMessageBox( validationMessage, "NIM Form Incomplete" )
            return False

        self.logMessage.emit( "done!", False )

        # Don't want to create settings dictionary if we don't have all the info yet
        if not loadingPulledValues:
            self.createSettingsDict()

        return validationPassed

    def createSettingsDict( self ):
        self.settingsDict = {
            "nim_user" : self.nim_user,
            "nim_userID" : self.nim_userID,
            "nim_renderName" : self.GetValue( "RenderBox" ),
            "nim_description" : self.GetValue( "DescriptionBox" ),
            "nim_jobName" : self.nim_jobName,
            
            "nim_jobID" : self.nim_jobID,
            "nim_class" : self.nim_class,
            "nim_taskID" : self.nim_taskID,
            "nim_elementTypeID" : self.nim_elementTypeID
        }

        if self.nim_class == "ASSET":
            self.settingsDict["nim_assetName"] = self.nim_assetName
        else:
            self.settingsDict["nim_showName"] = self.nim_showName
            self.settingsDict["nim_shotName"] = self.nim_shotName

        # Save sticky settings
        self.logMessage.emit( "Saving sticky settings... ", True )
        self.saveStickySettings( self.GetSettingsFilename() )
        self.logMessage.emit( "done!", False )

    def GetSettingsDictionary( self ):
        return self.settingsDict

    def CloseConnection( self, *args ):
        if self.workerThread and self.workerThread.IsAlive:
            self.workerThread.Abort()
        if self.progressThread and self.progressThread.IsAlive:
            self.progressThread.Abort()

        super( NimDialog, self ).accept()

def IsNoneOrWhiteSpace( someString ):
    return someString == None or someString.strip() == ""