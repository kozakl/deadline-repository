#Python.NET

###############################################################
## Imports
###############################################################
from System.Diagnostics import *
from System.IO import *
from System import TimeSpan

from Deadline.Events import *
from Deadline.Scripting import *

import re
import sys
import traceback
import os

# Add the events folder to the PYTHONPATH so that we can import ShotgunUtils.
shotgunUtilsPath = Path.Combine( RepositoryUtils.GetEventsDirectory(), "Shotgun" )
if not shotgunUtilsPath in sys.path:
    sys.path.append( shotgunUtilsPath )

verboseLogging = False

#################################################################################################
## This is the function called by Deadline to get an instance of the Shotgun event listener.
#################################################################################################
def GetDeadlineEventListener():
    return ShotgunEventListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The Shotgun event listener class.
###############################################################
class ShotgunEventListener( DeadlineEventListener ):
    ## Python.NET scripts need to use event handlers to "override" functionality. So setup
    ## the relevant event listeners in the constructor.
    def __init__( self ):
        self.OnJobSubmittedCallback += self.OnJobSubmitted
        self.OnJobStartedCallback += self.OnJobStarted
        self.OnJobFinishedCallback += self.OnJobFinished
        self.OnJobRequeuedCallback += self.OnJobRequeued
        self.OnJobFailedCallback += self.OnJobFailed
    
    def Cleanup( self ):
        del self.OnJobSubmittedCallback
        del self.OnJobStartedCallback
        del self.OnJobFinishedCallback
        del self.OnJobRequeuedCallback
        del self.OnJobFailedCallback
    
    def ConfigureShotgun( self ):
        shotgunPath = RepositoryUtils.GetAPISyncFolder()

        if not os.path.exists( shotgunPath ):
            self.LogInfo( "ERROR: Could not find Shotgun API at expected location '%s'" % shotgunPath )
            return ""
        
        self.LogInfo( "Importing Shotgun API from '%s'..." % shotgunPath )
        if not shotgunPath in sys.path:
            sys.path.append( shotgunPath )
            
        try:
            #do a test import
            import shotgun_api3.shotgun
            return shotgunPath
        except:
            self.LogInfo( "An error occurred while trying to connect to Shotgun:" )
            self.LogInfo( traceback.format_exc() )
            
        return ""
    
    def CreateShotgunVersion( self, job, shotgunPath ):
        global verboseLogging
        
        # Only connect to Shotgun if this job contains the necessary info.
        if job.JobExtraInfo5 != "" and job.GetJobExtraInfoKeyValue( "TaskId" ) != "":
            verboseLogging = (self.GetConfigEntryWithDefault( "VerboseLogging", "False" ).strip().upper() != "FALSE")
            
            try:
                # Pull the necessary Shotgun info from the job.
                userName = job.JobExtraInfo5
                taskId = int(job.GetJobExtraInfoKeyValue( "TaskId" ))
                projectId = int(job.GetJobExtraInfoKeyValue( "ProjectId" ))
                entityId = int(job.GetJobExtraInfoKeyValue( "EntityId" ))
                entityType = job.GetJobExtraInfoKeyValue( "EntityType" )
                version = re.sub( '(?i)\$\{jobid\}', job.JobId, job.JobExtraInfo3 ) #swap out the placeholder for the job ID
                version = re.sub( '(?i)\$\{jobname\}', job.JobName, version ) #swap out the placeholder for the job Name
                description = " (" + job.JobId + ")"
                if job.JobExtraInfo4 != "":
                    description = re.sub( '(?i)\$\{jobid\}', job.JobId, job.JobExtraInfo4 ) #swap out the placeholder for the job ID
                
                frames = job.JobFramesList
                
                frameRangeOverride = job.GetJobExtraInfoKeyValue( "FrameRangeOverride" )
                if not frameRangeOverride == "" and FrameUtils.FrameRangeValid( frameRangeOverride ):
                    frameString = frameRangeOverride
                    inputFrameList = frameRangeOverride
                    frames = FrameUtils.Parse( inputFrameList )
                
                frameCount = len(frames)
                
                frames = FrameUtils.ToFrameString( frames )
                
                outputPath = ""
                if len( job.JobOutputDirectories ) > 0:
                    if len( job.JobOutputFileNames ) > 0:
                        outputPath = Path.Combine( job.JobOutputDirectories[0], job.JobOutputFileNames[0] )
                    else:
                        outputPath = job.JobOutputDirectories[0]
                
                # Use ShotgunUtils to replace padding in output path.
                import ShotgunUtils
                framePaddingCharacter = self.GetConfigEntryWithDefault( "FramePaddingCharacter", "#" )
                outputPath = ShotgunUtils.ReplacePadding( outputPath, framePaddingCharacter)
                
                self.LogInfo( "Output path: " + outputPath )
            except:
                if verboseLogging:
                    raise
                else:
                    self.LogInfo( "An error occurred while retrieving Shotgun info from the submitted Job. No Version has been created." )
                    self.LogInfo( traceback.format_exc() )
                    return None
            
            versionId = None
            try:
                # Use ShotgunUtils to add a new version to Shotgun.
                import ShotgunUtils
                newVersion = ShotgunUtils.AddNewVersion( userName, taskId, projectId, entityId, entityType, version, description, frames, frameCount, outputPath, shotgunPath, job.JobId )
                versionId = newVersion['id']
                self.LogInfo( "Created new version in Shotgun with ID " + str(versionId) + ": " + version )
                
                # Save the version ID with the job for future events.
                job.SetJobExtraInfoKeyValue( "VersionId", str(versionId) )
                RepositoryUtils.SaveJob( job )
            except:
                if verboseLogging:
                    raise
                else:
                    self.LogInfo( "An error occurred while attempting to add a new Version to Shotgun. No Version has been created." )
                    self.LogInfo( traceback.format_exc() )
                    return None
            
            return versionId
    
    #Uses Draft to convert an image to a given format, to prepare for uploading
    def ConvertThumbnail( self, pathToFrame, format ):
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
        self.LogInfo( "Appending '%s' to Python search path" % draftRepoPath )
        if not draftRepoPath in sys.path:
            sys.path.append( draftRepoPath )
        self.LogInfo( "Importing Draft to perform Thumbnail conversion..."  )
        import Draft
        self.LogInfo( "Reading in image '%s'..."  % pathToFrame )
        originalImage = Draft.Image.ReadFromFile( str(pathToFrame) )
        self.LogInfo( "Converting image to type '%s'..."  % format )
        tempPath = Path.Combine( ClientUtils.GetDeadlineTempPath(), "%s.%s" % (Path.GetFileNameWithoutExtension(pathToFrame), format) )
        self.LogInfo( "Writing converted image to temp path '%s'..."  % tempPath )
        originalImage.WriteToFile( str(tempPath) )
        self.LogInfo( "Done!" )
        
        return tempPath
    
    ## This is called when the job is submitted to Deadline.
    def OnJobSubmitted( self, job ):
        global verboseLogging
        
        # Only do stuff if this job is tied to Shotgun
        if job.JobExtraInfo5 != "" and job.GetJobExtraInfoKeyValue( "TaskId" ) != "":
            if job.GetJobExtraInfoKeyValue( "Mode" ) == "":
                createOnSubmission = (self.GetConfigEntryWithDefault( "CreateVersionOnSubmission", "True" ).strip().upper() != "FALSE")
                if createOnSubmission:
                    shotgunPath = self.ConfigureShotgun()
                    if shotgunPath != "":
                        versionId = self.CreateShotgunVersion( job, shotgunPath )
                        
                        try:
                            # Update the version status in Shotgun.
                            if versionId:
                                statusCode = self.GetConfigEntryWithDefault( "VersionEntityStatusQueued", "" )
                                if statusCode.strip() != "":
                                    import ShotgunUtils
                                    ShotgunUtils.UpdateVersion( versionId, statusCode, shotgunPath )
                        except:
                            if verboseLogging:
                                raise
                            else:
                                self.LogInfo( "An error occurred while attempting to update the Shotgun Version's status.  The Version has been created, but may have the wrong status." )
                                self.LogInfo( traceback.format_exc() )
                                return
    
    ## This is called when the job finishes rendering.
    def OnJobFinished( self, job ):
        #make sure we have the latest job info
        job = RepositoryUtils.GetJob( job.ID, True )

        # Only do stuff if this job is tied to Shotgun
        if job.JobExtraInfo5 != "" and job.GetJobExtraInfoKeyValue( "TaskId" ) != "":
            self.LogInfo( "Found Shotgun Version info")
            shotgunMode = job.GetJobExtraInfoKeyValue( "Mode" )
            
            if shotgunMode == "":
                self.LogInfo( "Event Plugin Mode: UploadThumbnail" )
            else:
                self.LogInfo( "Event Plugin Mode: {0}".format( shotgunMode ) )

            shotgunPath = self.ConfigureShotgun()
            if shotgunPath != "":
                import ShotgunUtils

                if shotgunMode == "":
                    versionId = job.GetJobExtraInfoKeyValue( "VersionId" )
                    
                    if versionId == "":
                        #Create the shotgun version if it hasn't been created yet
                        versionId = self.CreateShotgunVersion( job, shotgunPath )
                    
                    #self.LogInfo( "Path to Shotgun: '%s'" % shotgunPath )
                    
                    # If this job has a Shotgun version, then update Shotgun.
                    if versionId:
                        statusCode = self.GetConfigEntryWithDefault( "VersionEntityStatusFinished", "" )
                        if statusCode.strip() != "":
                            ShotgunUtils.UpdateVersion( int(versionId), statusCode, shotgunPath )
                        
                        # CODE TO GET TOTAL AND AVERAGE TASK RENDER TIMES
                        avgTime = None
                        totalTime = None
                        
                        # format is 00d 00h 00m 00s
                        timePattern = ".*?=(?P<days>\d\d)d\s*(?P<hours>\d\d)h\s*(?P<minutes>\d\d)m\s*(?P<seconds>\d\d)s"
                        
                        tempStr = ClientUtils.ExecuteCommandAndGetOutput( ("GetJobTaskTotalTime", job.JobId) ).strip( "\r\n" )
                        timeParts = re.match( timePattern, tempStr )			
                        if ( timeParts != None ):
                            #Converts the days, hours, mins into seconds:
                            #((days * 24h + hours) * 60m + minutes) * 60s + seconds
                            totalTime = ( ( int(timeParts.group('days')) * 24 + int(timeParts.group('hours')) ) * 60 + int(timeParts.group('minutes')) ) * 60 + int(timeParts.group('seconds'))
                        
                        tempStr = ClientUtils.ExecuteCommandAndGetOutput( ("GetJobTaskAverageTime", job.JobId) ).strip( "\r\n" )				
                        timeParts = re.match( timePattern, tempStr)
                        if ( timeParts != None ):
                            avgTime = ( ( int(timeParts.group('days')) * 24 + int(timeParts.group('hours')) ) * 60 + int(timeParts.group('minutes')) ) * 60 + int(timeParts.group('seconds'))
                            
                        #Upload times to shotgun
                        if ( avgTime != None or totalTime != None ):
                            ShotgunUtils.UpdateRenderTimeForVersion( int(versionId), avgTime, totalTime, shotgunPath )
                        
                        # Upload a thumbnail if necessary.
                        thumbnailFrame = self.GetConfigEntryWithDefault( "ThumbnailFrame", "" )
                        if thumbnailFrame != "" and thumbnailFrame != "None" and len(job.JobOutputDirectories) > 0 and len(job.JobOutputFileNames) > 0:
                            frameList = job.JobFramesList 
                            frameRangeOverride = job.GetJobExtraInfoKeyValue( "FrameRangeOverride" )
                            if not frameRangeOverride == "" and FrameUtils.FrameRangeValid( frameRangeOverride ):
                                inputFrameList = frameRangeOverride
                                frameList = FrameUtils.Parse( inputFrameList )
                            
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
                                    self.LogInfo("ERROR: Unknown thumbnail frame option: '" + thumbnailFrame + "'")
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
                            
                            outputPath = RepositoryUtils.CheckPathMapping( outputPath, True )
                            outputPath = PathUtils.ToPlatformIndependentPath( outputPath )

                            if not File.Exists( outputPath ):
                                raise Exception( "ERROR: file is missing: %s" % outputPath )
                            
                            if not os.access( outputPath, os.R_OK ):
                                raise Exception( "ERROR: file is unreadable: %s" % outputPath )
                            
                            #Try to use Draft to convert the frame to a different format
                            if( self.GetConfigEntryWithDefault( "EnableThumbnailConversion", "false" ).lower() == "true" ):
                                format = self.GetConfigEntryWithDefault( "ConvertedThumbnailFormat", "JPEG" ).lower()
                                
                                try:
                                    convertedThumb = self.ConvertThumbnail( outputPath, format )
                                    if File.Exists( convertedThumb ):
                                        outputPath = convertedThumb
                                    else:
                                        self.LogInfo( "WARNING: Could not find converted thumbnail; uploading original instead." )
                                except:
                                    self.LogInfo( "WARNING: Failed to convert frame using Draft; uploading original instead." )
                                    self.LogInfo( traceback.format_exc() )
                            
                            # Upload the thumbnail to Shotgun.
                            self.LogInfo("ShotgunThumbnailUpload: " + outputPath + " (" + str(versionId) + ")" )
                            ShotgunUtils.UploadThumbnailToVersion( int(versionId), outputPath, shotgunPath )
                        else:
                            self.LogInfo( "Deadline is unaware of the output location; skipping thumbnail creation." )
                            
                elif shotgunMode == "UploadMovie":
                    
                    versionId = job.GetJobExtraInfoKeyValue( "VersionId" )
                    if versionId != "":
                        outputDirectories = job.JobOutputDirectories
                        outputFilenames = job.JobOutputFileNames

                        if len(outputFilenames) == 0:
                            raise Exception( "ERROR: Could not find an output path in Job properties, no movie will be uploaded to Shotgun." )
                        
                        # Just upload the first movie file if there is more than one.
                        moviePath = Path.Combine( outputDirectories[0], outputFilenames[0] )
                        moviePath = RepositoryUtils.CheckPathMapping( moviePath, True )
                        moviePath = PathUtils.ToPlatformIndependentPath( moviePath )

                        if not File.Exists( moviePath ):
                            raise Exception( "ERROR: movie file is missing: %s" % moviePath )
                        
                        if not os.access( moviePath, os.R_OK ):
                            raise Exception( "ERROR: movie file is unreadable: %s" % moviePath )
                        
                        self.LogInfo("UploadMovieToVersion: " + moviePath + " (" + str(versionId) + ")" )
                        ShotgunUtils.UploadMovieToVersion( int(versionId), moviePath, shotgunPath )

                elif shotgunMode == "UploadFilmstrip":

                    versionId = job.GetJobExtraInfoKeyValue( "VersionId" )

                    if versionId:
                        outputDirectories = job.JobOutputDirectories
                        outputFilenames = job.JobOutputFileNames

                        if len( outputFilenames ) == 0:
                            raise Exception( "ERROR: Could not find an output path in Job properties, filmstrip will not be uploaded to Shotgun." )

                        # Just upload the first movie file if there is more than one.
                        filmstripPath = Path.Combine( outputDirectories[0], outputFilenames[0] )
                        filmstripPath = RepositoryUtils.CheckPathMapping( filmstripPath, True )
                        filmstripPath = PathUtils.ToPlatformIndependentPath( filmstripPath )

                        if not File.Exists( filmstripPath ):
                            raise Exception( "ERROR: film strip file is missing: %s" % filmstripPath )
                        
                        if not os.access( filmstripPath, os.R_OK ):
                            raise Exception( "ERROR: film strip file is unreadable: %s" % filmstripPath )

                        self.LogInfo( "UploadFilmStripToVersion: '{0}' ({1})".format( filmstripPath, versionId ) )
                        ShotgunUtils.UploadFilmstripToVersion( versionId, filmstripPath, shotgunPath )
    
    ## This is called when the job starts rendering.
    def OnJobStarted( self, job ):
        #make sure we have the latest job info
        job = RepositoryUtils.GetJob( job.ID, True )

        # Only do stuff if this job is tied to Shotgun
        if job.JobExtraInfo5 != "" and job.GetJobExtraInfoKeyValue( "TaskId" ) != "":
            if job.GetJobExtraInfoKeyValue( "Mode" ) == "":
                # If this job has a Shotgun version, then update Shotgun.
                versionId = job.GetJobExtraInfoKeyValue( "VersionId" )
                if versionId != "":
                    statusCode = self.GetConfigEntryWithDefault( "VersionEntityStatusStarted", "" )
                    if statusCode.strip() != "":
                        shotgunPath = self.ConfigureShotgun()
                        if shotgunPath != "":
                            import ShotgunUtils
                            ShotgunUtils.UpdateVersion( int(versionId), statusCode, shotgunPath )
    
    ## This is called when the job is requeued.
    def OnJobRequeued( self, job ):
        #make sure we have the latest job info
        job = RepositoryUtils.GetJob( job.ID, True )

        # Only do stuff if this job is tied to Shotgun
        if job.JobExtraInfo5 != "" and job.GetJobExtraInfoKeyValue( "TaskId" ) != "":
            if job.GetJobExtraInfoKeyValue( "Mode" ) == "":
                # If this job has a Shotgun version, then update Shotgun.
                versionId = job.GetJobExtraInfoKeyValue( "VersionId" )
                if versionId != "":
                    statusCode = self.GetConfigEntryWithDefault( "VersionEntityStatusQueued", "" )
                    if statusCode.strip() != "":
                        shotgunPath = self.ConfigureShotgun()
                        if shotgunPath != "":
                            import ShotgunUtils
                            ShotgunUtils.UpdateVersion( int(versionId), statusCode, shotgunPath )

    ## This is called when the job fails.
    def OnJobFailed( self, job ):
        #make sure we have the latest job info
        job = RepositoryUtils.GetJob( job.ID, True )
        
        # Only do stuff if this job is tied to Shotgun
        if job.JobExtraInfo5 != "" and job.GetJobExtraInfoKeyValue( "TaskId" ) != "":
            if job.GetJobExtraInfoKeyValue( "Mode" ) == "":
                # If this job has a Shotgun version, then update Shotgun.
                versionId = job.GetJobExtraInfoKeyValue( "VersionId" )
                if versionId != "":
                    statusCode = self.GetConfigEntryWithDefault( "VersionEntityStatusFailed", "" )
                    if statusCode.strip() != "":
                        shotgunPath = self.ConfigureShotgun()
                        if shotgunPath != "":
                            import ShotgunUtils
                            ShotgunUtils.UpdateVersion( int(versionId), statusCode, shotgunPath )
