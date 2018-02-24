
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
import os
import subprocess
import tempfile
import traceback
import shlex
import collections

##############################################################################################
## This is the function called by Deadline to get an instance of the Draft event listener.
##############################################################################################
def GetDeadlineEventListener():
    return DraftEventListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The Draft event listener class.
###############################################################
class DraftEventListener (DeadlineEventListener):
    def __init__( self ):
        self.OnJobFinishedCallback += self.OnJobFinished
        
        #member variables
        self.OutputPathCollection = {}
        self.DraftSuffixDict = {}
    
    def Cleanup( self ):
        del self.OnJobFinishedCallback

    #Utility function that creates a Deadline Job based on given parameters
    #def CreateDraftJob( self, draftScript, job, jobTag, outputIndex=0, outFileNameOverride=None, draftArgs=[], shotgunMode=None, quickDraftFormat=None, ftrackMode=None ):
    def CreateDraftJob( self, draftScript, job, jobTag, outputIndex=0, outFileNameOverride=None, draftArgs=None, mode=None, quickDraftFormat=None, dependencies=None ):
        
        if draftArgs is None:
            draftArgs = []
        
        #Grab the draf-related job settings
        outputFilenames = job.JobOutputFileNames

        if len( outputFilenames ) == 0:
            raise Exception( "ERROR: Could not find a full output path in Job properties; No Draft job will be created." )
        elif len( outputFilenames ) <= outputIndex:
            raise Exception( "ERROR: Output Index out of range for given Job; No Draft job will be created." )

        outputDirectories = job.JobOutputDirectories

        jobOutputFile = outputFilenames[outputIndex]
        jobOutputDir = outputDirectories[outputIndex]
        
        inputFrameList = ""
        frames = []
        frameRangeOverride = job.GetJobExtraInfoKeyValue( "FrameRangeOverride" )
        if not frameRangeOverride == "":
            inputFrameList = frameRangeOverride
            frames = FrameUtils.Parse( inputFrameList )
        else:
            #Grab the Frame Offset (if applicable)
            frameOffset = 0
            strFrameOffset = job.GetJobExtraInfoKeyValue( "OutputFrameOffset{0}".format( outputIndex ) )
            if strFrameOffset:
                try:
                    frameOffset = int( strFrameOffset )
                except:
                    pass

            #calculate our frame list
            if frameOffset != 0:
                ClientUtils.LogText( "Applying Frame Offset of %s to Frame List..." % frameOffset )

            for frame in job.Frames:
                frames.append( frame + frameOffset )

            inputFrameList = FrameUtils.ToFrameString( frames )

        #Grab the submission-related plugin settings
        relativeFolder = self.GetConfigEntryWithDefault( "OutputFolder", "Draft" )
        draftGroup = self.GetConfigEntryWithDefault( "DraftGroup", "" ).strip()
        draftPool = self.GetConfigEntryWithDefault( "DraftPool", "" ).strip()
        draftLimit = self.GetConfigEntryWithDefault( "DraftLimit", "" ).strip()
        draftPriorityOffset = self.GetIntegerConfigEntryWithDefault( "PriorityOffset", 0 )

        if not draftGroup:
            draftGroup = job.Group

        if not draftPool:
            draftPool = job.Pool

        #TODO: Handle custom max priority?
        draftPriority = max(0, min(100, job.Priority + draftPriorityOffset))

        draftOutputFolder = Path.Combine( jobOutputDir, relativeFolder )
        draftOutputFolder = RepositoryUtils.CheckPathMapping( draftOutputFolder, True )
        draftOutputFolder = PathUtils.ToPlatformIndependentPath( draftOutputFolder )

        if not Directory.Exists( draftOutputFolder ):
            ClientUtils.LogText( "Creating output directory '%s'..." % draftOutputFolder )
            Directory.CreateDirectory( draftOutputFolder )
        
        #Check if we have a name override or a Quick Draft job, else pull from Job
        if outFileNameOverride:
            draftOutputFile = outFileNameOverride
        elif quickDraftFormat:
            jobOutputFile = re.sub( "\?", "#", Path.GetFileName( jobOutputFile ) )
            draftOutputFile = Path.GetFileNameWithoutExtension( jobOutputFile )
            if( quickDraftFormat["isMovie"] ):
                draftOutputFile = draftOutputFile.replace( "#", "" ).rstrip( "_-. " )
            draftOutputFile += "." + quickDraftFormat["extension"]
        else:
            jobOutputFile = re.sub( "\?", "#", Path.GetFileName( jobOutputFile ) )
            draftOutputFile = Path.GetFileNameWithoutExtension( jobOutputFile ).replace( "#", "" ).rstrip( "_-. " )
            draftOutputFile += ".mov"
        
        if quickDraftFormat:
            distributedEncoding = quickDraftFormat["isMovie"] and quickDraftFormat["isDistributed"]
        else:
            distributedEncoding = False

        #Handle draft output files that will override each other
        #For example: If there are two Draft jobs being created, one from input /path/myfile.png, and one from /path/myfile.jpg, the draft outputs will both be named /path/myfile.mov, and will overwrite each other.
        #We are appending a _2, _3, etc. to the end of the filenames in these cases. This isn't a pretty solution, but it's functional. We may want to rethink this in the future.
        addSuffix = False
        draftSuffixCount = 0
        filePathKey = os.path.abspath(draftOutputFolder)+"/"+draftOutputFile
        
        if filePathKey in self.OutputPathCollection:
            addSuffix = True
            #Get the suffix value for the current output file            
            draftSuffixCount =  int(self.DraftSuffixDict[filePathKey])+1

            if not distributedEncoding:
                #Increment the suffix value for the fileName e.g from 'lol_2.mov' to 'lol_3.mov'
                self.DraftSuffixDict[filePathKey] = int(self.DraftSuffixDict[filePathKey])+1
               
        else:
            if not distributedEncoding:
                self.OutputPathCollection[filePathKey] = 1 
                self.DraftSuffixDict[filePathKey] = 1
        
        draftOutput = Path.Combine( draftOutputFolder, draftOutputFile )
        #Add suffix to draft output to prevent files overriding each other
        if (addSuffix and draftSuffixCount > 1) and (not outFileNameOverride):
            draftOutput = os.path.splitext(draftOutput)[0]+"_"+ str(draftSuffixCount)+os.path.splitext(draftOutput)[1]

        #Add "_movie_chunk_" to filename in the case of distributed encoding
        if distributedEncoding:
            draftOutput = os.path.splitext(draftOutput)[0]+"_movie_chunk_"+os.path.splitext(draftOutput)[1]

        deadlineTemp = ClientUtils.GetDeadlineTempPath()
        
        jobInfoFile = ""
        pluginInfoFile = ""
        with tempfile.NamedTemporaryFile( mode="w", dir=deadlineTemp, delete=False ) as fileHandle:
            jobInfoFile = fileHandle.name 
            fileHandle.write( "Plugin=DraftPlugin\n" )
            fileHandle.write( "Name={0} [{1}]\n".format( job.Name, jobTag ) )
            fileHandle.write( "BatchName={0}\n".format( job.BatchName ) )
            fileHandle.write( "Comment=Job Created by Draft Event Plugin\n" )
            fileHandle.write( "Department={0}\n".format( job.Department ) )
            fileHandle.write( "UserName={0}\n".format( job.UserName ) )
            fileHandle.write( "Pool={0}\n".format( draftPool ) )
            fileHandle.write( "Group={0}\n".format( draftGroup ) )
            fileHandle.write( "Priority={0}\n".format( draftPriority) )
            fileHandle.write( "OnJobComplete=%s\n" % job.JobOnJobComplete )

            if draftLimit:
                fileHandle.write( "LimitGroups={0}\n".format( draftLimit ) )

            fileHandle.write( "OutputFilename0={0}\n".format( draftOutput ) )

            fileHandle.write( "Frames={0}\n".format( inputFrameList ) )
            
            if quickDraftFormat and quickDraftFormat["isDistributed"]:
                fileHandle.write( "ChunkSize={0}\n".format( quickDraftFormat["chunkSize"] ) )
                fileHandle.write( "MachineLimit={0}\n".format( quickDraftFormat["machineLimit"] ) )
            else:
                fileHandle.write( "ChunkSize=1000000\n" )
            
            if dependencies:
                fileHandle.write( "JobDependencies=%s\n" % dependencies )
            
            if mode:
                self.LogInfo( "MODE: " + mode )
                
                modeParts = mode.split( '|' )
                if len(modeParts) == 2:
                    modeType = modeParts[0]
                    
                    if modeType == "Shotgun":
                        shotgunMode = modeParts[1]
                    
                        #Get the shotgun ID from the job
                        shotgunID = job.GetJobExtraInfoKeyValue( "VersionId" )
                        if ( shotgunID == "" ):
                            ClientUtils.LogText( "WARNING: Could not find an associated Shotgun Version ID.  The Draft output will not be uploaded to Shotgun." )
                        else:
                            #Pull any SG info from the other job
                            fileHandle.write( "ExtraInfo0={0}\n".format( job.ExtraInfo0 ) )
                            fileHandle.write( "ExtraInfo1={0}\n".format( job.ExtraInfo1 ) )
                            fileHandle.write( "ExtraInfo2={0}\n".format( job.ExtraInfo2 ) )
                            fileHandle.write( "ExtraInfo3={0}\n".format( job.ExtraInfo3 ) )
                            fileHandle.write( "ExtraInfo4={0}\n".format( job.ExtraInfo4 ) )
                            fileHandle.write( "ExtraInfo5={0}\n".format( job.ExtraInfo5 ) )

                            #Only bother with the necessary KVPs
                            fileHandle.write( "ExtraInfoKeyValue0=VersionId={0}\n".format( shotgunID ) )
                            fileHandle.write( "ExtraInfoKeyValue1=TaskId={0}\n".format( job.GetJobExtraInfoKeyValue( 'TaskId' ) ) )
                            fileHandle.write( "ExtraInfoKeyValue2=Mode={0}\n".format( shotgunMode ) )
                    
                    elif modeType == "ftrack":
                        ftrackMode = modeParts[1]
                        
                        #Get the ftrack ID from the job
                        ftrackID = job.GetJobExtraInfoKeyValue( "FT_ProjectId" )
                        
                        if ( ftrackID == "" ):
                            ClientUtils.LogText( "WARNING: Could not find an associated ProjectID Version ID.  The Draft output will not be uploaded to FTrack." )
                        else:
                            #Pull any FT info from the other job
                            fileHandle.write( "ExtraInfo0={0}\n".format( job.ExtraInfo0 ) )
                            fileHandle.write( "ExtraInfo1={0}\n".format( job.ExtraInfo1 ) )
                            fileHandle.write( "ExtraInfo2={0}\n".format( job.ExtraInfo2 ) )
                            fileHandle.write( "ExtraInfo3={0}\n".format( job.ExtraInfo3 ) )
                            fileHandle.write( "ExtraInfo4={0}\n".format( job.ExtraInfo4 ) )
                            fileHandle.write( "ExtraInfo5={0}\n".format( job.ExtraInfo5 ) )

                            #Only bother with the necessary KVPs
                            fileHandle.write( "ExtraInfoKeyValue0=FT_ProjectId={0}\n".format( ftrackID ) )
                            fileHandle.write( "ExtraInfoKeyValue1=FT_ProjectName={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_ProjectName" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue2=FT_AssetId={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_AssetId" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue3=FT_AssetName={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_AssetName" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue4=FT_TaskId={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_TaskId" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue5=FT_TaskName={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_TaskName" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue6=FT_Description={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_Description" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue7=FT_Username={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_Username" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue8=FT_VersionId={0}\n".format( job.GetJobExtraInfoKeyValue( "FT_VersionId" ) ) )
                            fileHandle.write( "ExtraInfoKeyValue9=FT_DraftUploadMovie=True\n" )
                    
                    elif modeType == "NIM":
                        nimMode = modeParts[1]
                        
                        #Get the ftrack ID from the job
                        nimID = job.GetJobExtraInfoKeyValue( "nim_jobID" )
                        
                        if ( nimID == "" ):
                            ClientUtils.LogText( "WARNING: Could not find an associated NIM job ID.  The Draft output will not be uploaded to NIM." )
                        else:
                            #Pull any NIM info from the other job
                            fileHandle.write( "ExtraInfo0={0}\n".format( job.ExtraInfo0 ) )
                            fileHandle.write( "ExtraInfo1={0}\n".format( job.ExtraInfo1 ) )
                            fileHandle.write( "ExtraInfo2={0}\n".format( job.ExtraInfo2 ) )
                            fileHandle.write( "ExtraInfo3={0}\n".format( job.ExtraInfo3 ) )
                            fileHandle.write( "ExtraInfo4={0}\n".format( job.ExtraInfo4 ) )
                            fileHandle.write( "ExtraInfo5={0}\n".format( job.ExtraInfo5 ) )

                            #Only bother with the necessary KVPs
                            fileHandle.write( "ExtraInfoKeyValue0=DraftUploadToNim=True\n" )
                            fileHandle.write( "ExtraInfoKeyValue1=nim_jobName=%s\n" % job.GetJobExtraInfoKeyValue( "nim_jobName" ) )
                            fileHandle.write( "ExtraInfoKeyValue2=nim_jobID=%s\n" % nimID )
                            fileHandle.write( "ExtraInfoKeyValue3=nim_taskID=%s\n" % job.GetJobExtraInfoKeyValue( "nim_taskID" ) )
                            #fileHandle.write( "ExtraInfoKeyValue4=DraftNimEncodeSRGB=%s\n" % StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "DraftNimEncodeSRGB" ), False ) )
                            fileHandle.write( "ExtraInfoKeyValue4=DraftNimEncodeSRGB=%s\n" % False )
                            fileHandle.write( "ExtraInfoKeyValue5=nimSrcJob=%s\n" % job.JobId )

        #Build the Draft plugin info file
        with tempfile.NamedTemporaryFile( mode="w", dir=deadlineTemp, delete=False ) as fileHandle:
            pluginInfoFile = fileHandle.name 
            #build up the script arguments
            scriptArgs = draftArgs

            scriptArgs.append( 'frameList=%s ' % inputFrameList )
            scriptArgs.append( 'startFrame=%s ' % frames[0] )
            scriptArgs.append( 'endFrame=%s ' % frames[-1] )
            
            scriptArgs.append( 'inFile="%s" ' % Path.Combine( jobOutputDir, jobOutputFile  ) )
            scriptArgs.append( 'outFile="%s" ' % draftOutput )
            scriptArgs.append( 'outFolder="%s" ' % Path.GetDirectoryName( draftOutput ) )

            scriptArgs.append( 'deadlineJobID=%s ' % job.JobId )

            
            for i, scriptArg in enumerate( scriptArgs ):
                fileHandle.write( "ScriptArg%d=%s\n" % ( i, scriptArg ) )

        ClientUtils.LogText( "Submitting {0} Job to Deadline...".format( jobTag ) )
        output = self.CallDeadlineCommand( [jobInfoFile, pluginInfoFile, draftScript])
        ClientUtils.LogText( output )

        jobId = ""
        resultArray = output.split()
        for line in resultArray:
            if line.startswith("JobID="):
                jobId = line.replace("JobID=","")
                break
        return jobId
     
    ## This is called when the job finishes rendering.
    def OnJobFinished( self, job ):
        # Reset those in case the script was not reloaded
        self.OutputPathCollection = {}
        self.DraftSuffixDict = {}
        
        try:

            # if job.BatchName == "":
            #     #TODO: Should we actually do this? seems a bit jarring if the artist is actively watching their job
            #     ClientUtils.LogText( "Adding original Job to Batch '{0}'".format( job.Name ) )
            #     job.BatchName = job.Name
            #     RepositoryUtils.SaveJob( job )
            
            #Check if we need to generate movies to upload to Shotgun
            createShotgunMovie = job.GetJobExtraInfoKeyValueWithDefault( "Draft_CreateSGMovie", "false" ).lower() != "false"
            if createShotgunMovie:
                #create a Draft job that will create and upload a SG quicktime
                draftScript = RepositoryUtils.GetRepositoryFilePath( "events/DraftEventPlugin/DraftQuickSubmission/DraftCreateSimpleMovie.py", True )
                self.CreateDraftJob( draftScript, job, "Shotgun H264 Movie Creation", outFileNameOverride="shotgun_h264.mov", mode="Shotgun|UploadMovie" )

            #Check if we need to generate a filmstrip to upload to Shotgun
            createShotgunFilmstrip = job.GetJobExtraInfoKeyValueWithDefault( "Draft_CreateSGFilmstrip", "false" ).lower() != "false"
            if createShotgunFilmstrip:
                #create a Draft job that will create and upload a SG filmstrip
                draftScript = RepositoryUtils.GetRepositoryFilePath( "events/DraftEventPlugin/DraftQuickSubmission/DraftCreateFilmstrip.py", True )
                self.CreateDraftJob( draftScript, job, "Shotgun Filmstrip Creation", outFileNameOverride="shotgun_filmstrip.png", mode="Shotgun|UploadFilmstrip" )
            
            createFTrackMovie = job.GetJobExtraInfoKeyValueWithDefault( "Draft_CreateFTMovie", "false" ).lower() != "false"
            if createFTrackMovie:
                draftScript = RepositoryUtils.GetRepositoryFilePath( "events/DraftEventPlugin/DraftQuickSubmission/DraftCreateSimpleMovie.py", True )
                self.CreateDraftJob( draftScript, job, "FTrack H264 Movie Creation", outFileNameOverride="ftrack_h264.mov", mode="ftrack|UploadMovie" )
            
            createNimMovie = job.GetJobExtraInfoKeyValueWithDefault( "Draft_CreateNimMovie", "false" ).lower() != "false"
            if createNimMovie:
                draftScript = RepositoryUtils.GetRepositoryFilePath( "events/DraftEventPlugin/DraftQuickSubmission/DraftCreateSimpleMovie.py", True )
                
                # For NIM, create a movie for each output.
                outputCount = len(job.JobOutputFileNames)
                for i in range( 0, outputCount ):
                    jobOutputFile = job.JobOutputFileNames[i]
                    jobOutputFile = re.sub( "\?", "#", Path.GetFileName( jobOutputFile ) )
                    draftOutputFile = Path.GetFileNameWithoutExtension( jobOutputFile )
                    draftOutputFile = draftOutputFile.replace( "#", "" ).rstrip( "_-. " )
                    draftOutputFile = "nim_" + draftOutputFile + "_h264.mov"
                    
                    self.CreateDraftJob( draftScript, job, "NIM H264 Movie Creation", outFileNameOverride=draftOutputFile, outputIndex=i, mode="NIM|UploadMovie" )
            
            # If this job has Quick Draft selected, submit a Draft job per output
            submitQuickDraft = ( job.GetJobExtraInfoKeyValueWithDefault( "SubmitQuickDraft", "false" ).lower() != "false" )
            if submitQuickDraft:
                draftQuickScript = RepositoryUtils.GetRepositoryFilePath( "events/DraftEventPlugin/DraftQuickSubmission/QuickDraft.py", True )

                #Get all the other Quick Draft-related KVPs from the Job
                extension = job.GetJobExtraInfoKeyValue( "DraftExtension" )
                isMovie = ( job.GetJobExtraInfoKeyValue( "DraftType" ) == "movie" )
                format = {'extension' : extension, 'isMovie' : isMovie}
                resolution = job.GetJobExtraInfoKeyValue( "DraftResolution" )
                codec = job.GetJobExtraInfoKeyValue( "DraftCodec" )
                quality = job.GetJobExtraInfoKeyValueWithDefault( "DraftQuality", "None" )
                frameRate = job.GetJobExtraInfoKeyValue( "DraftFrameRate" )
                colorSpaceIn = job.GetJobExtraInfoKeyValueWithDefault( "DraftColorSpaceIn", "None" )
                colorSpaceOut = job.GetJobExtraInfoKeyValueWithDefault( "DraftColorSpaceOut", "None" )
                annotationsString = job.GetJobExtraInfoKeyValueWithDefault( "DraftAnnotationsString", "None" )
                annotationsFramePaddingSize = job.GetJobExtraInfoKeyValueWithDefault( "DraftAnnotationsFramePaddingSize", "None" )
                
                uploadToShotgun = (not createShotgunMovie) and StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "DraftUploadToShotgun" ), False )
                uploadToFTrack = (not createFTrackMovie) and StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "FT_DraftUploadMovie" ), False )
                uploadToNim = (not createNimMovie) and StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "DraftUploadToNim" ), False )
                
                distributedJobEnabled = self.GetBooleanConfigEntryWithDefault( "EnableDistributedJob", False )
                chunkSize = self.GetIntegerConfigEntryWithDefault( "ChunkSize", 200 )
                threshold = int( 5 * chunkSize )
                isDistributed = distributedJobEnabled and len( job.Frames ) >= threshold
                
                format['isDistributed'] = isDistributed
                
                if isDistributed:
                    format['chunkSize'] = chunkSize
                    format['machineLimit'] = self.GetIntegerConfigEntryWithDefault( "MachineLimit", 5 )
                
                outputCount = len(job.JobOutputFileNames)
                for i in range( 0, outputCount ):
                    scriptArgs = []
                    scriptArgs.append( 'resolution="%s" ' % resolution )
                    scriptArgs.append( 'codec="%s" ' % codec )
                    scriptArgs.append( 'quality="%s" ' % quality )
                    scriptArgs.append( 'colorSpaceIn="%s" ' % colorSpaceIn )
                    scriptArgs.append( 'colorSpaceOut="%s" ' % colorSpaceOut )
                    scriptArgs.append( 'annotationsString="%s" ' % annotationsString )
                    scriptArgs.append( 'annotationsFramePaddingSize="%s" ' % annotationsFramePaddingSize )
                    scriptArgs.append( 'isDistributed="%s" ' % isDistributed )

                    if isMovie:
                        scriptArgs.append( 'frameRate="%s" ' % frameRate )
                        scriptArgs.append( 'quickType="createMovie" ' )
                    else:
                        scriptArgs.append( 'quickType="createImages" ' )

                    mode = None
                    if isMovie:
                        # For NIM, create a movie for each output. Otherwise, only do it for the first output.
                        if uploadToNim:
                            mode = "NIM|UploadMovie"
                        elif i == 0:
                            if uploadToShotgun:
                                mode = "Shotgun|UploadMovie"
                            elif uploadToFTrack:
                                mode = "ftrack|UploadMovie"
                    
                    ClientUtils.LogText( "====Submitting Job for Output {0} of {1}====".format( i + 1, outputCount ) )
                    
                    if isDistributed and isMovie:
                        jobId = self.CreateDraftJob( draftQuickScript, job, "Quick Draft", outputIndex=i, draftArgs=scriptArgs, mode=mode, quickDraftFormat=format )
                        format['isDistributed'] = False
                        self.CreateDraftJob( draftQuickScript, job, "Quick Draft", outputIndex=i, draftArgs=['quickType="concatenateMovies" '], mode=mode, quickDraftFormat=format, dependencies=jobId )
                        format['isDistributed'] = isDistributed
                    else:
                        self.CreateDraftJob( draftQuickScript, job, "Quick Draft", outputIndex=i, draftArgs=scriptArgs, mode=mode, quickDraftFormat=format )
            
            # If this job has a DraftTemplate, submit a Draft job per output
            draftTemplate = job.GetJobExtraInfoKeyValue( "DraftTemplate" )
            draftTemplate = RepositoryUtils.CheckPathMapping( draftTemplate, True )

            if draftTemplate != "":
                ClientUtils.LogText( "Found Draft Template: '%s'" % draftTemplate )

                #Get all the other Draft-related KVPs from the Job
                username = job.GetJobExtraInfoKeyValue( "DraftUsername" )
                entity = job.GetJobExtraInfoKeyValue( "DraftEntity" )
                version = job.GetJobExtraInfoKeyValue( "DraftVersion" )
                width = job.GetJobExtraInfoKeyValue( "DraftFrameWidth" )
                height = job.GetJobExtraInfoKeyValue( "DraftFrameHeight" )
                extraArgs = job.GetJobExtraInfoKeyValue( "DraftExtraArgs" )
                
                uploadToShotgun = (not createShotgunMovie) and StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "DraftUploadToShotgun" ), False )
                uploadToFTrack = (not createFTrackMovie) and StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "FT_DraftUploadMovie" ), False )
                uploadToNim = (not createNimMovie) and StringUtils.ParseBooleanWithDefault( job.GetJobExtraInfoKeyValue( "DraftUploadToNim" ), False )

                outputCount = len( job.JobOutputFileNames )
                for i in range( 0, outputCount ):
                    scriptArgs = []
                    scriptArgs.append( 'username="%s" ' % username )
                    scriptArgs.append( 'entity="%s" ' % entity )
                    scriptArgs.append( 'version="%s" ' % version )
                    
                    if width != "":
                        scriptArgs.append( 'width=%s ' % width )
                    
                    if height != "":
                        scriptArgs.append( 'height=%s ' % height )

                    regexStr = r"(\S*)\s*=\s*(\S*)"
                    replStr = r"\1=\2"
                    extraArgs = re.sub( regexStr, replStr, extraArgs )

                    tokens = shlex.split( extraArgs )
                    for token in tokens:
                        scriptArgs.append( token )
                    
                    # For NIM, create a movie for each output. Otherwise, only do it for the first output.
                    mode = None
                    if uploadToNim:
                        mode = "NIM|UploadMovie"
                    elif i == 0:
                        if uploadToShotgun:
                            mode = "Shotgun|UploadMovie"
                        elif uploadToFTrack:
                            mode = "ftrack|UploadMovie"

                    ClientUtils.LogText( "====Submitting Job for Output {0} of {1}====".format( i + 1, outputCount ) )
                    self.CreateDraftJob( draftTemplate, job, "Draft Template", outputIndex=i, draftArgs=scriptArgs, mode=mode )

        except:
            ClientUtils.LogText( traceback.format_exc() )

    def CallDeadlineCommand( self, arguments ):
        deadlineBin = ClientUtils.GetBinDirectory()
        
        deadlineCommand = ""
        if os.name == 'nt':
            deadlineCommand = Path.Combine(deadlineBin, "deadlinecommandbg.exe")
        else:
            deadlineCommand = Path.Combine(deadlineBin, "deadlinecommandbg")
        
        arguments.insert(0, deadlineCommand)
        proc = subprocess.Popen(arguments, cwd=deadlineBin)
        proc.wait()
        
        outputPath = Path.Combine( ClientUtils.GetDeadlineTempPath(), "dsubmitoutput.txt" )
        output = File.ReadAllText(outputPath)
        
        return output
