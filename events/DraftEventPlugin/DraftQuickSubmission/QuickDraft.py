from __future__ import print_function
import os
import sys
import subprocess

from DraftParamParser import *

def GetDeadlineCommand():
    deadlineBin = ""
    try:
        deadlineBin = os.environ['DEADLINE_PATH']
    except KeyError:
        #if the error is a key error it means that DEADLINE_PATH is not set. however Deadline command may be in the PATH or on OSX it could be in the file /Users/Shared/Thinkbox/DEADLINE_PATH
        pass
        
    # On OSX, we look for the DEADLINE_PATH file if the environment variable does not exist.
    if deadlineBin == "" and  os.path.exists( "/Users/Shared/Thinkbox/DEADLINE_PATH" ):
        with open( "/Users/Shared/Thinkbox/DEADLINE_PATH" ) as f:
            deadlineBin = f.read().strip()

    deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")
    
    return deadlineCommand

def GetRepositoryPath(subdir = None):
    deadlineCommand = GetDeadlineCommand()
    
    startupinfo = None

    args = [deadlineCommand, "-GetRepositoryPath "]   
    if subdir != None and subdir != "":
        args.append(subdir)
    
    # Specifying PIPE for all handles to workaround a Python bug on Windows. The unused handles are then closed immediatley afterwards.
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)

    proc.stdin.close()
    proc.stderr.close()

    output = proc.stdout.read()

    path = output.decode("utf_8")
    path = path.replace("\r","").replace("\n","").replace("\\","/")

    return path

path = GetRepositoryPath( "events/DraftEventPlugin/DraftQuickSubmission" )

if path != "":
    # Add the path to the system path
    if path not in sys.path :
        print( "Appending \"%s\" to system path to import Quick Draft scripts" % path )
        sys.path.append( path ) 
    else:
        print( "\"%s\" is already in the system path" % path )

    params = ParseCommandLine_TypeAgnostic( sys.argv )

    try:
        quickType = params['quickType']
    except:
        raise Exception( "Error: No Quick Draft type was specified." )

    if quickType == "createImages":
        from DraftCreateImages import CreateImages 
        CreateImages( params )
    elif quickType == "createMovie":
        from DraftCreateMovie import CreateMovie 
        CreateMovie( params )
    elif quickType == "concatenateMovies":
        from DraftConcatenateMovies import ConcatenateMovies 
        ConcatenateMovies( params )
    else:
        raise Exception( "Error: Unrecognised Quick Draft type: " + quickType + "." )
        
else:
    print( "The Quick Draft scripts could not be found in the Deadline Repository. Please make sure that the Deadline Client has been installed on this machine, that the Deadline Client bin folder is set in the DEADLINE_PATH environment variable, and that the Deadline Client has been configured to point to a valid Repository." ) 
