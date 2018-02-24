###############################################################
## Imports
###############################################################
from System.Diagnostics import *
from System.IO import *
from System import TimeSpan
from System import DateTime

import os
import sys
import traceback
import re

from Deadline.Events import *
from Deadline.Scripting import *

import string
import urllib
import urllib2
import mimetools
import mimetypes

import email.generator as email_gen
import cStringIO

import stat
try: import simplejson as json
except ImportError: import json
from itertools import izip
import datetime

import nim_core.nim_api as nimAPI

#nim_encodeSRGB = None;

##########################################################################################
## This is the function called by Deadline to get an instance of the event listener.
##########################################################################################
def GetDeadlineEventListener():
    return NimEventListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The NIM event listener class.
###############################################################
class NimEventListener (DeadlineEventListener):
    calledFromCreateVersionScript = False
    
    def __init__( self ):
        #self.OnJobSubmittedCallback += self.OnJobSubmitted
        #self.OnJobStartedCallback += self.OnJobStarted
        self.OnJobFinishedCallback += self.OnJobFinished
    
    def Cleanup( self ):
        #del self.OnJobSubmittedCallback
        #del self.OnJobStartedCallback
        del self.OnJobFinishedCallback
    
    def SetCalledFromCreateVersionScript( self ):
        self.Cleanup()
        self.calledFromCreateVersionScript = True
    
    def WriteLog( self, text ):
        if( not self.calledFromCreateVersionScript ):
            self.LogInfo( text )
        else:
            ClientUtils.LogText( text )

    def OnJobSubmitted( self, job ):
        self.WriteLog("NIM - OnJobSubmitted:")

    def OnJobStarted( self, job ):
        self.WriteLog("NIM - OnJobStarted:")

    ## This is called when the job finishes rendering.
    def OnJobFinished( self, job ):
        if self.isNIMJob(job):
            self.ProcessNimJob( job )

    # Determines whether or not this is a NIM Job.
    def isNIMJob( self, job ):
        # If this job has a nimJob then Log to NIM.
        nim_jobName = job.GetJobExtraInfoKeyValue( "nim_jobName" )
        if nim_jobName:
            self.WriteLog( "Found NIM Job: '%s'" % nim_jobName )
            return True

        return False
    
    def ProcessNimJob( self, job ):
        self.WriteLog("NIM --------------------------------------")
        
        pluginConfig = self
        if self.calledFromCreateVersionScript:
            pluginConfig = RepositoryUtils.GetEventPluginConfig( "NIM" )
        
        baseUrl = pluginConfig.GetConfigEntry("NimURL")
        apiKey = pluginConfig.GetConfigEntryWithDefault("NimAPIKey", "" )
       
        if apiKey == "":
            apiKey = None
        
        nim_jobPlugin = job.JobPlugin
        
        if nim_jobPlugin == "DraftPlugin":
            self.WriteLog("CHECK")
            #Add Dailies from Draft
            self.AddNimDailies(baseUrl, job)
        
        else:
            #Log Render to NIM and create thumbnail
            self.WriteLog("Ready to Add Render")
        
            self.AddNimRender(baseUrl, apiKey, job)
            
            convertThumbnail = pluginConfig.GetConfigEntryWithDefault( "EnableThumbnailConversion", "false" ).lower()
            if( convertThumbnail == "true" ):
                thumbnailFrame = pluginConfig.GetConfigEntryWithDefault( "ThumbnailFrame", "" )
                thumbnailFormat = pluginConfig.GetConfigEntryWithDefault( "ConvertedThumbnailFormat", "JPG" ).lower()
                self.updateThumbnail(baseUrl, job, thumbnailFrame, thumbnailFormat)
                
    def AddNimRender( self, baseUrl, apiKey, job ):
    
        tasks = RepositoryUtils.GetJobTasks(job, True)
        jobKey = job.JobId
        jobName = job.JobName
        jobComment = job.JobComment
        jobPlugin = job.JobPlugin
        outputDirectories = job.JobOutputDirectories
        outputFilenames = job.JobOutputFileNames
        
        jobStats = JobUtils.CalculateJobStatistics(job, tasks)
        
        jobStartDate = job.JobStartedDateTime.Date.ToString('yyyy-MM-dd HH:mm:ss')
        jobEndDate = job.JobCompletedDateTime.Date.ToString('yyyy-MM-dd HH:mm:ss')
        
        outputDirs = []
        for outDir in outputDirectories:
            outDir = outDir.replace('\\','/').replace("//","/")
            outputDirs.append(outDir)
        outputDirs = json.dumps(outputDirs)

        outputFiles = []
        for outFile in outputFilenames:
            outFile = outFile.replace('\\','/').replace("//","/")
            outputFiles.append(outFile)
        outputFiles = json.dumps(outputFiles)
        
        jobFrames = job.JobFrames
        frameRangeOverride = job.GetJobExtraInfoKeyValue( "FrameRangeOverride" )
        if FrameUtils.FrameRangeValid( frameRangeOverride ):
            jobFrames = frameRangeOverride
        
        avgTime = int( jobStats.AverageFrameTime.TotalSeconds )
        totalTime = int( jobStats.TotalTaskTime.TotalSeconds )
        
        self.WriteLog('JobKey: %s' % jobKey)
        self.WriteLog('JobName: %s' % jobName)
        self.WriteLog('JobPlugin: %s' % jobPlugin)
        self.WriteLog('JobFrames: %s' % jobFrames)
        self.WriteLog('Output Dirs: %s' % outputDirs)
        self.WriteLog('Output Files: %s' % outputFiles)
        self.WriteLog('Start Date: %s' % jobStartDate)
        self.WriteLog('End Date: %s' % jobEndDate)
        
        jobId = job.GetJobExtraInfoKeyValue( "nim_jobID" )
        nimClass =  job.GetJobExtraInfoKeyValue( "nim_class" )
        taskId =  job.GetJobExtraInfoKeyValue( "nim_taskID" )
        elementTypeID =  job.GetJobExtraInfoKeyValue( "nim_elementTypeID" )
        
        result = nimAPI.add_render( jobID=jobId, itemType=nimClass, taskID=taskId, elementTypeID=elementTypeID,
            renderKey=jobKey, renderName=jobName, renderType=jobPlugin, renderComment=jobComment, outputDirs=outputDirs, outputFiles=outputFiles, 
            start_datetime=jobStartDate, end_datetime=jobEndDate, avgTime=avgTime, totalTime=totalTime, frame=jobFrames,
            nimURL=baseUrl, apiKey=apiKey )
        
        self.WriteLog( str(result) )
        
        if result["success"] == "true":
            #for whatever reason if this is sucessful it returns a dictionary with the fields ID and Success 
            self.WriteLog( 'Succesfully published to NIM.' )
        else:
            # when it fails it instead returns a list that contains a single dictionary with the fields result and error
            raise Exception( "Publishing to nim failed with the error: " + result[0]["error"] )
            
    def AddNimDailies( self, baseUrl, job ):
        pluginConfig = self
        if self.calledFromCreateVersionScript:
            pluginConfig = RepositoryUtils.GetEventPluginConfig( "NIM" )
            
        nim_draftUpload = job.GetJobExtraInfoKeyValue( "DraftUploadToNim" )
        self.WriteLog( "NIM - Draft Upload: %s" % nim_draftUpload )

        nim_jobPlugin = job.JobPlugin
        self.WriteLog( "NIM - Plugin Type: %s" % nim_jobPlugin )
        
        if not nim_draftUpload:
            return
        
        self.WriteLog( "Found Completed NIM Draft Job" )
        
        
        jobKey = job.JobId            
        
        outputDirectories = job.JobOutputDirectories
        outputFilenames = job.JobOutputFileNames
        
        #Iternate through outputFiles and upload to NIM
        if len(outputFilenames) == 0:
            raise Exception( "ERROR: Could not find an output path in Job properties, no movie will be uploaded to Nim." )

        # Just upload the first movie file if there is more than one.
        moviePath = Path.Combine( outputDirectories[0], outputFilenames[0] )
        self.WriteLog("UploadMovie: " + moviePath )

        if not File.Exists( moviePath ):
            raise Exception( "ERROR: movie file is missing: %s" % moviePath )

        if not os.access( moviePath, os.R_OK ):
            raise Exception( "ERROR: movie file is unreadable: %s" % moviePath )
        
        renderKey = job.GetJobExtraInfoKeyValue( "nimSrcJob" )
        taskId = job.GetJobExtraInfoKeyValue( "nim_taskID" ).encode('ascii')
        apiKey = pluginConfig.GetConfigEntryWithDefault("NimAPIKey", "" )
        if apiKey == "":
            apiKey = None
       
        result = nimAPI.upload_dailies( taskID=taskId, renderKey=renderKey, path=moviePath, nimURL=baseUrl, apiKey=apiKey )
        
        if result:
            self.WriteLog( 'Succesfully uploaded dailies.' )
        else:
            # when it fails it instead returns a list that contains a single dictionary with the fields result and error
            raise Exception( "Failed to upload Dailies." ) 
    
    def updateThumbnail( self, baseUrl, job, thumbnailFrame, format ):
        
        if thumbnailFrame == "" or thumbnailFrame == "None:":
            self.WriteLog( "The thumbail frame options has been set to None; skipping thumbnail creation." )
        
        if len(job.JobOutputDirectories) == 0 or len(job.JobOutputFileNames) == 0:
            self.WriteLog( "Deadline is unaware of the output location; skipping thumbnail creation." )
            return        
        
        pluginConfig = self
        if self.calledFromCreateVersionScript:
            pluginConfig = RepositoryUtils.GetEventPluginConfig( "NIM" )
        
        frameList = job.JobFramesList 
        frameRangeOverride = job.GetJobExtraInfoKeyValue( "FrameRangeOverride" )
        if FrameUtils.FrameRangeValid( frameRangeOverride ):
            frameList = FrameUtils.Parse( frameRangeOverride )
        
        # Figure out which frame to upload.
        frameNum = -1
        if len(frameList) > 1:
            if thumbnailFrame == 'First Frame' :
                frameNum = frameList[0]
            elif thumbnailFrame == 'Last Frame' :
                frameNum = frameList[-1]
            elif thumbnailFrame == 'Middle Frame' :
                frameNum = frameList[len(frameList)/2]
            else :
                self.WriteLog ("ERROR: Unknown thumbnail frame option: '" + thumbnailFrame + "'")
                return
        else:
            frameNum = frameList[0]
        
        # Get the output path for the frame.
        outputPath = Path.Combine(job.JobOutputDirectories[0], job.JobOutputFileNames[0]).replace("//","/")
        
        # Pad the frame as required.
        paddingRegex = re.compile("[^\\?#]*([\\?#]+).*")
        m = re.match(paddingRegex,outputPath)
        if( m != None):
            padding = m.group(1)
            frame = StringUtils.ToZeroPaddedString(frameNum,len(padding),False)
            outputPath = outputPath.replace( padding, frame )

        if not File.Exists( outputPath ):
            raise Exception( "ERROR: output file is missing: %s" % outputPath )

        if not os.access( outputPath, os.R_OK ):
            raise Exception( "ERROR: output file is unreadable: %s" % outputPath )
        
        #Try to use Draft to convert the frame to a different format
        format = format.lower()
            
        convertedThumb = self.ConvertThumbnail( outputPath, format )
        if File.Exists( convertedThumb ):
            outputPath = convertedThumb
        else:
            raise Exception( "Error: Could not find converted thumbnail." )
        
        # Upload the thumbnail to NIM.
        jobKey = job.JobId
        apiKey = pluginConfig.GetConfigEntryWithDefault("NimAPIKey", "" )
        if apiKey == "":
            apiKey = None
        self.WriteLog("Nim Thumbnail Upload: " + outputPath )
        
        nimAPI.upload_renderIcon( renderKey=jobKey, img=outputPath, nimURL=baseUrl, apiKey=apiKey )
    
    #Uses Draft to convert an image to a given format, to prepare for uploading
    def ConvertThumbnail( self, pathToFrame, format ):
        self.WriteLog( "Performing thumbnail conversion" )
        #first figure out where the Draft folder is on the repo
        draftRepoPath = RepositoryUtils.GetRepositoryPath( "draft", False )
        
        if SystemUtils.IsRunningOnMac():
            draftRepoPath = Path.Combine( draftRepoPath, "Mac" )
        else:
            if SystemUtils.IsRunningOnLinux():
                draftRepoPath = Path.Combine( draftRepoPath, "Linux" )
            else:
                draftRepoPath = Path.Combine( draftRepoPath, "Windows" )
            
            if SystemUtils.Is64Bit():
                draftRepoPath = Path.Combine( draftRepoPath, "64bit" )
            else:
                draftRepoPath = Path.Combine( draftRepoPath, "32bit" )
        
        #import Draft and do the actual conversion
        if not str(draftRepoPath) in sys.path:
            sys.path.append( draftRepoPath )
        
        try:
            import Draft

            Draft = reload( Draft )			#fix to find proper draft module
            
            self.WriteLog("Successfully imported Draft!")
            self.WriteLog(Draft.__file__)
        except:
            self.WriteLog("Failed to import Draft! Unable To convert file")
            raise        
        
        try:
            originalImage = Draft.Image.ReadFromFile( str(pathToFrame) )
        except:
            self.WriteLog("Failed to read image for conversion")
            raise

        self.WriteLog( "Converting image to type '%s'"  % format )
        tempPath = Path.Combine( ClientUtils.GetDeadlineTempPath(), "%s.%s" % (Path.GetFileNameWithoutExtension(pathToFrame), format) )
            
        try:
            originalImage.WriteToFile( str(tempPath) )
        except:
            self.WriteLog( "Failed to write converted image." )
            raise
        
        try:
            del sys.modules["Draft"]
            del Draft
        except:
            self.WriteLog('Failed to unload the Draft Module')
            
        return tempPath