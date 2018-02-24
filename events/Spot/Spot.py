###############################################################
## Imports
###############################################################
import boto3
import json
import os
import requests
import datetime
import dateutil
import ast
from botocore.exceptions import ClientError
from random import randint
from time import sleep
from sys import platform

from Deadline.Events import *
from Deadline.Scripting import *

##############################################################################################
## This is the function called by Deadline to get an instance of the Spot event listener.
##############################################################################################
def GetDeadlineEventListener():
    return SpotEventListener()

def CleanupDeadlineEventListener( eventListener ):
    eventListener.Cleanup()

###############################################################
## The Spot event listener class.
###############################################################
class SpotEventListener( DeadlineEventListener ):
    def __init__( self ):
        self.OnHouseCleaningCallback += self.OnHouseCleaning
        self.OnSlaveStartedCallback += self.OnSlaveStarted
        self.OnSlaveInfoUpdatedCallback += self.OnSlaveInfoUpdated

    def Cleanup( self ):
        del self.OnHouseCleaningCallback
        del self.OnSlaveStartedCallback
        del self.OnSlaveInfoUpdatedCallback

    def OnHouseCleaning( self ):
        try:
            self.LogInfo( "Spot Plugin - On House Cleaning Started" )
            #Do some cleanup if enabled
            deleteTerminatedSlaves = self.GetBooleanConfigEntryWithDefault( "DeleteTerminatedSlaves", False )

            if deleteTerminatedSlaves:
                slaveNames = RepositoryUtils.GetSlaveNames( True )
                
                for slave in slaveNames:
                    slaveSettings = RepositoryUtils.GetSlaveSettings( slave, True )
                    
                    if slaveSettings.GetSlaveExtraInfoKeyValue( "SpotTerminatedSlave" ) == "True":
                        RepositoryUtils.DeleteSlave( slave )

            #Connect to EC2
            ec2 = self.GetEc2()

            requestInfo = {}
            if self.GetMetaDataEntry( "Requests" ) is not None:
                requestInfo = json.loads( self.GetMetaDataEntry( "Requests" ) )

            config = self.GetConfigEntryWithDefault( "Config", "{}" )

            config = ''.join( config.split(';') )
            configs = json.loads( config )

            self.LogInfo( json.dumps(requestInfo) )

            #Get all Limits 
            limitGroups = RepositoryUtils.GetLimitGroups( True )

            availableStubs = {}
            #Count available stubs for each limit group
            for limitGroup in limitGroups:
                #If the limit is unlimited, then set to special value
                if limitGroup.UnlimitedLimit:
                    availableStubs[ limitGroup.Name ] = -1
                #if there's a whitelist, none of our Slaves will be in it so they won't get limits
                elif limitGroup.WhitelistFlag and len( limitGroup.Properties.ListedSlaves ) > 0:
                    availableStubs[ limitGroup.Name ] = 0
                #otherwise add the available limits and overage together. (Unlimited Overage goes here. It sets the overage to a really high number)
                else:
                    availableStubs[ limitGroup.Name ] = (limitGroup.Limit - limitGroup.InUse) + (limitGroup.Overage - limitGroup.InOverage)

            self.LogInfo( "Available Stubs: " + str( availableStubs) )

            #Determine available Capacity for SFRs that already exist.
            availableCapacity = {}
            for group in configs.keys():
                availableCapacity[group] = configs[group]["TargetCapacity"] 

            self.LogInfo( "Available Capacity: " + str( availableCapacity) )
            #Determine work to be done.
            queuedTasksByGroup = {}
            jobs = RepositoryUtils.GetJobsInState( "Active" )

            for job in sorted( jobs, key=lambda x: x.JobPriority, reverse=True ):
                
                #ignore groups that aren't in our available capacity.
                if job.Group in availableCapacity.keys():
                    tasks = job.JobQueuedTasks
                    
                    for limit in job.JobLimitGroups:
                        if availableStubs[ limit ] != -1: #if not unlimited
                                tasks = min( tasks, availableStubs[ limit ] )

                    #apply hard cap.
                    tasks = min( tasks, availableCapacity[job.Group] )

                    if job.Group in queuedTasksByGroup.keys():
                        queuedTasksByGroup[job.Group] += tasks
                    else:
                        queuedTasksByGroup[job.Group] = tasks
                    
                    #subtract some capacity
                    availableCapacity[job.Group] -= tasks
                    
                    #subtract stubs taken
                    for limit in job.JobLimitGroups:
                        if availableStubs[ limit ] != -1:
                            availableStubs[ limit ] -= tasks

            self.LogInfo( "Queued Tasks by Group: " + str(queuedTasksByGroup) )
            self.LogInfo( "Available Stubs: " + str(availableStubs) )
                
            #Go through all of the groups.
            for group in queuedTasksByGroup.keys():
                #Check if there's a mapping for this group.
                if group in configs.keys():
                    target = min( queuedTasksByGroup[group], configs[group]["TargetCapacity"] )
                    #Check if there's a request for this group.
                    if group in requestInfo.keys():

                        #Check if this request is valid.
                        if requestInfo[group] != None:
                            try:
                                request = ec2.describe_spot_fleet_requests(SpotFleetRequestIds= [requestInfo[group]])
                                self.LogInfo( "Found Request: '" + requestInfo[group] + "' for group '" + group + "'." )
                                
                                #Check if the request can be modified.
                                if request['SpotFleetRequestConfigs'][0]['SpotFleetRequestState'] in ['submitted', 'active', 'modifying']: 
                                    #modify the request or cancel it if the target is 0.
                                    if target > 0:
                                        #No need to modify the TargetCapacity if it's already equal to target.
                                        if target != request['SpotFleetRequestConfigs'][0]['SpotFleetRequestConfig']['TargetCapacity']:
                                            try:
                                                ec2.modify_spot_fleet_request( SpotFleetRequestId=requestInfo[group], TargetCapacity= target )
                                                self.LogInfo( "Set TargetCapacity of request '" + requestInfo[group] + "' to: " + str(target) + "." )
                                            except ClientError as e:
                                                self.LogWarning( str(e) )
                                    else:
                                        ec2.cancel_spot_fleet_requests( SpotFleetRequestIds=[requestInfo[group]], TerminateInstances=False )
                                        self.LogInfo( "Cancelled Request: '" + requestInfo[group] + "'." )
                                        self.MarkRequestAsInactive( requestInfo[group] )
                                        requestInfo[group] = None

                                    #Terminate instances that are rendering if we have more instances than the hard cap.
                                    if self.GetBooleanConfigEntryWithDefault( "StrictHardCap", False ):
                                        activeInstances = ec2.describe_spot_fleet_instances( SpotFleetRequestId=requestInfo[group] )
                                        activeInstanceIds = []
                                        
                                        for instance in activeInstances["ActiveInstances"]:
                                            activeInstanceIds.append(instance["InstanceId"])
                                        activeInstanceIds.sort()

                                        instancesToTerminate = []
                                        for i in range( len( activeInstanceIds ) - configs[group]["TargetCapacity"] ):
                                            instanceId = activeInstanceIds[i]
                                            self.LogInfo( "Terminating instance '" + instanceId + "'.")
                                            instancesToTerminate.append( instanceId )

                                        if len(instancesToTerminate) > 0:
                                            ec2.terminate_instances( InstanceIds=instancesToTerminate )
                                else:
                                    #If we can't modify the current request then make a new one.
                                    self.LogInfo( "Request: '" + requestInfo[group] + "' was not in a modifiable state. Creating new request." )
                                    self.MarkRequestAsInactive( requestInfo[group] )
                                    requestInfo[group] = None
                                    
                                    if configs[group] != None and target > 0:
                                        requestInfo[group] = self.CreateNewRequest( configs[group], target, group )
                                        self.LogInfo( "Created Request: '" + requestInfo[group] + "' for group: '" + group + "' with target of " + str(target) + "." )

                            except ClientError as e:
                                errorCode = e.response['Error']['Code']
                                self.LogInfo( str(e) )

                                if errorCode == "InvalidSpotFleetRequestId.NotFound":
                                    #Request not found. Create one.
                                    if configs[group] != None and target > 0:
                                        requestInfo[group] = self.CreateNewRequest( configs[group], target, group )
                                        self.LogInfo( "Created Request: '" + requestInfo[group] + "' for group: '" + group + "' with target of " + str(target) + "." )
                            except Exception as e:
                                self.LogWarning( str(e) )

                        else:
                            #Request is blank. Create one.
                            if configs[group] != None and target > 0:
                                requestInfo[group] = self.CreateNewRequest( configs[group], target, group )
                                self.LogInfo( "Created Request: '" + requestInfo[group] + "' for group: '" + group + "' with target of " + str(target) + "." )
                    else:
                        #No previous request. Create one.
                        if configs[group] != None and target > 0:
                            requestInfo[group] = self.CreateNewRequest( configs[group], target, group )
                            self.LogInfo( "Created Request: '" + requestInfo[group] + "' for group: '" + group + "' with target of " + str(target) + "." )
            
            groupNames = RepositoryUtils.GetGroupNames()
            #Cancel requests for groups that don't appear in queuedTasksByGroup.keys().
            for group in requestInfo.keys():
                if group not in queuedTasksByGroup.keys():
                    if requestInfo[group] is not None:
                        ec2.cancel_spot_fleet_requests( SpotFleetRequestIds=[requestInfo[group]], TerminateInstances=False )
                        self.LogInfo( "Cancelled Request: '" + requestInfo[group] + "'." )
                        
                        self.MarkRequestAsInactive( requestInfo[group] )
                        requestInfo[group] = None
                    #Check if that Group is still a group. If not, remove it from requestInfo.
                    if group not in groupNames:
                        del requestInfo[group]

            #Save our request information to the event's metadata dictionary.
            if( self.GetMetaDataEntry( "Requests" ) is not None ):
                self.UpdateMetaDataEntry( "Requests", json.dumps( requestInfo ) )
            else:
                self.AddMetaDataEntry( "Requests", json.dumps( requestInfo ) )

            self.CheckInactiveList()

        except Exception as e:
            self.LogWarning( str(e) )

    def CreateNewRequest( self, config, tasks, group ):
        config['TargetCapacity'] = tasks
        config['ExcessCapacityTerminationPolicy'] = 'noTermination'
        if "Pools" in config.keys():
            del config["Pools"]
        launchSpecs = []

        for launchSpec in config['LaunchSpecifications']:
            if 'TagSpecifications' in launchSpec.keys():
                tags = launchSpec['TagSpecifications']
                instanceTagSpecFound = False
                #Find the 'instance' tag if it exists.
                for tag in tags:
                    if tag['ResourceType'] == "instance":
                        tag['Tags'].append( { "Key": "DeadlineGroup", "Value": group } )
                        instanceTagSpecFound = True
                        break
                
                if not instanceTagSpecFound:
                    tags.append( { "ResourceType": "instance", "Tags": [ { "Key": "DeadlineGroup", "Value": group } ] } )

                launchSpec['TagSpecifications'] = tags
            else:
                launchSpec['TagSpecifications'] = [ { "ResourceType": "instance", "Tags": [ { "Key": "DeadlineGroup", "Value": group } ] } ]
            launchSpecs.append(launchSpec)

        config['LaunchSpecifications'] = launchSpecs

        ec2 = self.GetEc2()
        return ec2.request_spot_fleet( SpotFleetRequestConfig=config )['SpotFleetRequestId']

    def OnSlaveStarted( self, slaveName ):
        self.LogInfo( "Spot Plugin - On Slave Started" )
        #Check if the instance has meta data. If it does that means it's an AWS instance and we can proceed.
        try:
            #Query the AWS meta-data address for the instance id. If this doesn't exist then we aren't an AWS instance and can stop here.
            response = requests.get( r"http://169.254.169.254/latest/meta-data/instance-id" )
        except Exception as e:
            return

        instanceId = response.text

        fleetID = self.GetFleetID( instanceId )

        #If we didn't find a fleetID then we aren't a Spot Fleet instance.
        if fleetID == None:
            return

        spotConfigMetaData = RepositoryUtils.GetEventPluginConfigMetaDataDictionary( "Spot" )

        #Get the requests mappings from the event plugin metadata.
        requestInfo = {}
        if spotConfigMetaData[ "Requests" ] is not None:
            requestInfo = json.loads( spotConfigMetaData[ "Requests" ] )

        #Find the group that is associated with request ID.
        group = None 
        for groupName, request in requestInfo.iteritems():
            if request == fleetID:
                group = groupName

        if group != None:
            self.LogInfo( "On Slave Started: Adding the Slave, '" + slaveName + "' to group '" + group + "'." )

            #Get the Slave settings and set the group.
            slaveSettings = RepositoryUtils.GetSlaveSettings( slaveName, False )
            slaveSettings.SetSlaveGroups( [group] )

            self.LogInfo( "Slave " + slaveName + " added to Group " + group + "." )

            config = self.GetConfigEntryWithDefault( "Config", "{}" )

            config = ''.join(config.split(';'))
            configs = json.loads( config )
            if "Pools" in configs[group].keys():
                slaveSettings.SetSlavePools(configs[group]["Pools"])
                self.LogInfo("Adding the Slave, '" + slaveName + "' to pools '" + configs[group]["Pools"] + "'.")

            RepositoryUtils.SaveSlaveSettings( slaveSettings )

            self.AddMetaDataEntry( instanceId, "" )
        else: 
            self.LogWarning( "The Slave '" + slaveName + "' was not created by the Spot plugin. If applicable, check SFR 'IAM instance profile' has correct IAM permissions." )

    def OnSlaveInfoUpdated( self, slaveName, slaveInfo ):
        try:
            self.LogInfo( "Spot Plugin - On Slave Info Updated" )
            instanceID = None

            #Check if the Slave has meta data. If it does that means it's an AWS instance and we can proceed.
            try:
                #Query the AWS meta-data address for the instance id. If this doesn't exist then we aren't an AWS instance and can stop here.
                response = requests.get( r"http://169.254.169.254/latest/meta-data/instance-id" )
                
            except Exception as e:
                return
            instanceID = response.text

            data = self.GetMetaDataEntry( instanceID )

            now = datetime.datetime.now()
            slaveSettings = RepositoryUtils.GetSlaveSettings( slaveName, False )

            #If there is data for this Slave already, then we already know it's Spot Event Plugin created.
            if data is None or len( slaveSettings.Groups ) == 0:
                #Check if the instance is using the DeadlineGroup tag. If it is, it was created by the Spot plugin and we can proceed.
                fleetID = None
                group = None
                foundFleetID = False
                fleetID = self.GetFleetID( instanceID )

                if fleetID is None:
                    return

                spotConfigMetaData = RepositoryUtils.GetEventPluginConfigMetaDataDictionary( "Spot" )
                #Get the requests mappings from the event plugin metadata.
                requestInfo = {}
                if spotConfigMetaData[ "Requests" ] is not None:
                    requestInfo = json.loads( spotConfigMetaData[ "Requests" ] )

                for groupName, request in requestInfo.iteritems():
                    if request == fleetID:
                        foundFleetID = True
                        group = groupName

                #If the request isn't active, it could be in the inactive list.
                if group == None:
                    inactiveList = self.GetMetaDataEntry("Inactive")
                    if inactiveList is not None:
                        for request in ast.literal_eval(inactiveList):
                            if request == fleetID:
                                self.LogInfo( "Adding data entry for " + instanceID )
                                self.AddMetaDataEntry( instanceID, str(now) ) 
                                foundFleetID = True
                                break
                #We haven't found a tag for a fleet id and DeadlineGroup so this isn't a spot fleet instance we created so we should stop.
                if not foundFleetID:
                    return

                if fleetID != None and group != None:
                    #Get the requests mappings from the event plugin metadata.
                    requestInfo = {}
                    spotConfigMetaData = RepositoryUtils.GetEventPluginConfigMetaDataDictionary( "Spot" )

                    if spotConfigMetaData[ "Requests" ] is not None:
                        requestInfo = json.loads( spotConfigMetaData[ "Requests" ] )

                    self.LogInfo( "Adding the Slave, '" + slaveName + "' to group '" + group + "'." )

                    #Get the slave settings and set the group
                    slaveSettings = RepositoryUtils.GetSlaveSettings( slaveName, False )
                    slaveSettings.SetSlaveGroups( [group] )

                    config = self.GetConfigEntryWithDefault( "Config", "{}" )

                    config = ''.join( config.split(';') )
                    configs = json.loads( config )
                    self.LogInfo( "Info Updated: Config: "+ str(configs[group]) )
                    if "Pools" in configs[group].keys():
                        slaveSettings.SetSlavePools( configs[group]["Pools"] )
                        self.LogInfo( "Adding the Slave, '" + slaveName + "' to pools '" + configs[group]["Pools"] + "'." )

                    RepositoryUtils.SaveSlaveSettings( slaveSettings )

            #Check if the Slave is rendering.
            if slaveInfo.SlaveStatus == 1:
                #If rendering, set the entry for the Slave to be an empty string.
                if data is not None:
                    self.UpdateMetaDataEntry( instanceID, "" )
                else:
                    self.AddMetaDataEntry( instanceID, "" )

                    self.LogInfo( instanceID + " is rendering." )
            else:
                if data is not None:
                    if data != "": 
                        self.LogInfo( str( now - dateutil.parser.parse(data) ) )

                        if now - dateutil.parser.parse(data) > datetime.timedelta(minutes=self.GetIntegerConfigEntry( "IdleShutdown" )):
                            self.LogInfo( "I'm supposed to shutdown." )
                            self.DeleteMetaDataEntry( instanceID )

                            #Tag Slave extra info key as a terminated Slave so house cleaning can delete
                            deleteTerminatedSlaves = self.GetBooleanConfigEntryWithDefault( "DeleteTerminatedSlaves", False )
                            
                            if deleteTerminatedSlaves:
                                slaveSettings = RepositoryUtils.GetSlaveSettings( slaveName, False )
                                
                                slaveDict = slaveSettings.SlaveExtraInfoDictionary
                                
                                if slaveDict.ContainsKey( "SpotTerminatedSlave" ):
                                    slaveDict.Remove( "SpotTerminatedSlave" )
                                
                                slaveDict.Add( "SpotTerminatedSlave", "True" )

                                RepositoryUtils.SaveSlaveSettings( slaveSettings )

                            #Send command to terminate VM
                            ec2 = self.GetEc2()
                            ec2.terminate_instances(InstanceIds=[response.text])
                    else:
                        self.LogInfo( "Updating data entry for " + instanceID )
                        self.UpdateMetaDataEntry( instanceID, str(now) )
                else:
                    self.LogInfo( "Adding data entry for " + instanceID )
                    self.AddMetaDataEntry( instanceID, str(now) ) 

            if slaveInfo.SlaveState == "Offline":
                self.DeleteMetaDataEntry( instanceID )

        except ClientError as e:
            self.LogWarning( str(e) )
            errorCode = e.response['Error']['Code']
            if errorCode == "Client.RequestLimitExceeded":
                self.LogInfo( str(e) )
                interval = randint(20, 60)
                self.LogInfo( "Sleeping for: " + str(interval) )
                sleep(interval)

                instanceID = requests.get( r"http://169.254.169.254/latest/meta-data/instance-id" ).text

                if self.GetMetaDataEntry( instanceID ) is not None:
                    self.UpdateMetaDataEntry( instanceID, "" )

        except Exception as e:
            self.LogWarning( str(e) )

    def GetEc2( self ):
        #Connect to EC2.
        accessID = self.GetConfigEntryWithDefault( "AccessID", "" )

        if len(accessID) <= 0:
            self.LogWarning( "Please enter an AccessID for the Spot Instance Event Plugin." )
            return

        secretKey = self.GetConfigEntryWithDefault( "SecretKey", "" )

        if len(secretKey) <= 0:
            self.LogWarning( "Please enter a Secret Key for the Spot Instance Event Plugin." )
            return

        region = self.GetConfigEntryWithDefault( "Region", "" )

        if len(region) <= 0:
            self.LogWarning( "No AWS Region has been specified for the Spot Instance Event Plugin." )
            return

        ec2 = boto3.client( 'ec2', region_name=region, aws_access_key_id=accessID, aws_secret_access_key=secretKey )

        return ec2

    def GetFleetID( self, instanceID ):
        ec2 = self.GetEc2()
        fleetRequests = ec2.describe_spot_fleet_requests()
        fleetID = None
        found = False

        for request in fleetRequests['SpotFleetRequestConfigs']:
            for instance in ec2.describe_spot_fleet_instances(SpotFleetRequestId=request['SpotFleetRequestId'])['ActiveInstances']:
                if instanceID == instance['InstanceId']:
                    fleetID = request['SpotFleetRequestId']
                    found = True
                    break
            if found:
                break

        return fleetID

    def MarkRequestAsInactive( self, requestID ):
        #Move request to the inactive list.
        self.LogInfo( "Adding " + requestID + " to the inactive list." )
        inactiveList = self.GetMetaDataEntry( "Inactive" )
        if( inactiveList is not None):
            inactiveList = ast.literal_eval(inactiveList)
            self.LogInfo( "Current inactive list: " + str(inactiveList) )
            inactiveList.append(requestID)
            self.UpdateMetaDataEntry( "Inactive", str(inactiveList) )
        else:
            self.LogInfo( "No current inactive list." )
            inactiveList = [requestID]
            self.AddMetaDataEntry( "Inactive", str(inactiveList) )

    def CheckInactiveList( self ):
        self.LogInfo( "Checking Inactive List" )
        ec2 = self.GetEc2()
        inactiveList = self.GetMetaDataEntry( "Inactive" )
        newInactiveList = []

        if inactiveList is not None:
            inactiveList = ast.literal_eval(inactiveList)
            for request in inactiveList:
                try:
                    if len(ec2.describe_spot_fleet_instances( SpotFleetRequestId=request)['ActiveInstances'] ) > 0:
                        newInactiveList.append(request)
                    else:
                        self.LogInfo( str(request) + " has no more active instances and can be removed from the Inactive List." )
                except:
                    self.LogInfo( str(request) + " no longer exists. Removing from the Inactive List." )
            #Only save the new inactive list if it's different from the current list.
            if len(set(inactiveList) - set(newInactiveList)) > 0:
                self.LogInfo( "Saving new in active list: " + str(newInactiveList) )
                self.UpdateMetaDataEntry( "Inactive", str(newInactiveList) )
