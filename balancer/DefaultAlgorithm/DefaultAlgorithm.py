from Deadline.Balancer import *
from Deadline.Scripting import *

import traceback
import math

def GetBalancerPluginWrapper():
    return DefaultBalancerPlugin()

def CleanupBalancerPlugin( balancerPlugin ):
    balancerPlugin.CleanUp()
    
class DefaultBalancerPlugin(BalancerPluginWrapper):
    def __init__( self ):
        self.BalancerAlgorithmCallback += self.BalancerAlgorithm
        
    def CleanUp(self):
        del self.BalancerAlgorithmCallback
        
    def BalancerAlgorithm(self, stateStruct):
        self.verboseLogging = self.GetBooleanConfigEntryWithDefault( "Verbose", True )

        self.CreateBalancerStateStruct(stateStruct)
        self.ComputeDemand()
        self.DetermineResources()
        self.ComputeTargets()
        return self.PopulateTargets()
        
        
    def CreateBalancerStateStruct(self, stateStruct):
        try:
            if self.verboseLogging:
                ClientUtils.LogText("Creating Balancer State Struct")

            #-------------#
            # == STAGE 0 ==  Prepare some data structures.
            self.stateStruct = stateStruct
           
            # Make a Dictionary from the CloudRegions array with CloudRegionStruct.ID as the key and CloudRegionStruct as the value.
            self.cloudRegionsDict = dict( [item.ID , item]  for item in self.stateStruct.CloudRegions )            
                
            # Make a Dictionary from the Slaves array with SlaveStruct.Name as the key and SlaveStruct as the value.
            self.slaveDict = dict([item.Name, item] for item in self.stateStruct.Slaves )
            
            # Make a Dictionary from the Jobs array with JobStruct.ID as the key and JobStruct as the value.
            self.jobsDict = dict([item.ID, item] for item in self.stateStruct.Jobs)
            
            # Make a Dictionary from the Groups array with GroupStruct.Name as the key and GroupStruct as the value.
            self.groupsDict = dict([item.Name, item] for item in self.stateStruct.Groups)
            
            # Make a Dictionary from the Limits array with the LimitStruct.Name as the key and LimitStruct as the value.
            self.limitsDict = dict([item.Name, item] for item in self.stateStruct.Limits )
                
            # Make a Dictionary to hold the targets.  < string regionID, < string groupID, int numberOfInstances> >
            self.targetsDict = {}

            for cloudRegionStruct in self.stateStruct.CloudRegions:
                groupRegionTargetDict = {}
                for groupRegionStruct in cloudRegionStruct.EnabledGroups:
                    groupRegionTargetDict[groupRegionStruct.Name] = 0
                    
                self.targetsDict[cloudRegionStruct.ID] = groupRegionTargetDict
        except:
            ClientUtils.LogText(traceback.format_exc())
            
    def ComputeDemand(self):
        try:
            if self.verboseLogging:
                ClientUtils.LogText("Computing Demand")

            #-------------#
            # == STAGE 1 ==  Compute the demand for each Group.
            
            # A list of the job IDs for candidate jobs.
            groupDemandDict = {}
            self.jobUnallocatedTasksDict = {}

            for jobStruct in self.stateStruct.Jobs:

                # Are the assets for this job ready on any associated region?  If not discard it.
                if jobStruct.AssetReadyRegions.Length == 0:
                    continue
                    
                # Accumulate the group demand values for this job by iterating over the job's tasks.
                if not jobStruct.Group in groupDemandDict:
                    groupDemandDict[jobStruct.Group] = {"TaskCount":0, "Weight":0}
                    
                jobEligibleTasks = 0
                areAllRegularTasksComplete = True
                postJobTaskExists = False
                preJobTaskExists = False
                preJobTaskStatus = None


                preJobTaskMode = self.GetConfigEntryWithDefault( "PreJobTaskMode", "Conservative" )

                for taskStruct in jobStruct.Tasks:
                    if not taskStruct.IsPostJobTask and not taskStruct.IsPreJobTask:
                        # Any Queued = 2 tasks are eligible. Any tasks being rendered (Rendering = 4) by cloud slaves are also eligble
                        #   (since we back out exisiting cloud activity in finding targets).
                        if taskStruct.Status == 2 or (taskStruct.Status == 4 and taskStruct.CloudSlave):
                            jobEligibleTasks+=1

                        #If there are any not completed regular tasks the mark areAllRegularTasksComplete as false. We don't include the post job task.
                        if taskStruct.Status != 5:
                            areAllRegularTasksComplete = False

                    elif taskStruct.IsPreJobTask:
                        preJobTaskExists = True
                        preJobTaskStatus = taskStruct.Status

                        #if the pre job task isn't complete then we consider all regular task to not be complete. 
                        if preJobTaskStatus != 5:
                            areAllRegularTasksComplete = False

                    elif taskStruct.IsPostJobTask and taskStruct.Status == 2:
                        postJobTaskExists = True

                if preJobTaskExists:

                    if preJobTaskMode == "Conservative":
                        #If there's a queued pre job task then there's only 1 task to work on. 
                        if preJobTaskStatus == 2:
                            jobEligibleTasks = 1    
                        
                    elif preJobTaskMode == "Normal":
                        if preJobTaskStatus == 2:
                            jobEligibleTasks += 1

                    elif preJobTaskMode == "Ignore":
                        pass
                    #if the pre job task isn't complete then there are no tasks to work on.
                    if preJobTaskStatus != 2 and preJobTaskStatus != 5:
                        jobEligibleTasks = 0


                if areAllRegularTasksComplete and postJobTaskExists:
                    jobEligibleTasks += 1

                jobEligibleTasks = math.ceil( float(jobEligibleTasks) / jobStruct.ConcurrentTasks)
                        
                # Add the demand contribution from this job to the groupDemand.
                groupDemand = groupDemandDict[jobStruct.Group]
                
                groupDemand["TaskCount"] += jobEligibleTasks
                groupDemand["Weight"] += jobEligibleTasks * jobStruct.Priority

                if self.verboseLogging:
                    ClientUtils.LogText("Group (%s): TaskCount: (%s) Weight: (%s)" % (jobStruct.Group, groupDemand["TaskCount"], groupDemand["Weight"]))
                
                # Assign the updated values back to the group.
                groupDemandDict[jobStruct.Group] = groupDemand
                
                # Record the number of eligible tasks for this job.
                self.jobUnallocatedTasksDict[jobStruct.ID] = jobEligibleTasks
                
            self.groupDemandList = [] 
            for key, value in groupDemandDict.iteritems():
                self.groupDemandList.append([key, value])
                
            self.groupDemandList = sorted(self.groupDemandList, key=lambda x: x[1]["Weight"],  reverse=True) #// Note, order reversed to get a decending sort.
        except:
            ClientUtils.LogText(traceback.format_exc())
            

    def DetermineResources(self):
        try:
            if self.verboseLogging:
                ClientUtils.LogText("Determining the Available Resources")

            #-------------#
            # == STAGE 2 ==  Determine the available resources.
            
            # -- 2.A -- Limit Resources --
            self.limitStubsDict = {}
            
            for limitStruct in self.stateStruct.Limits:
                #first value is the number of limits, second value is if the limit is unlimited
                self.limitStubsDict[limitStruct.Name] = [max(0, (limitStruct.Limit - limitStruct.NonCloudStubHolders.Length)), limitStruct.UnlimitedLimit]
            
            # -- 2.B -- Cloud Region Resources --
            self.regionBudgetDict = {}
            
            for cloudRegionStruct in self.stateStruct.CloudRegions:
                self.regionBudgetDict[cloudRegionStruct.ID] = cloudRegionStruct.Budget
        except:
            ClientUtils.LogText(traceback.format_exc())
            
    def ComputeTargets(self):
        try:
            if self.verboseLogging:
                ClientUtils.LogText("Computing Targets")

            #-------------#
            # == STAGE 3 ==  Compute Region Group targets by depleting the resources.
            
            if len(self.groupDemandList) > 0:
                spaceAvailable = True
            else:
                spaceAvailable = False
            
            while spaceAvailable:
                spaceAvailable = False         
                jobAvailable = False
                #reorder the groupDemandList so the highest priority group is at the top
                self.groupDemandList = sorted(self.groupDemandList, key=lambda x: x[1]["Weight"],  reverse=True)
                
                groupName = self.groupDemandList[0][0]

                #Process the Jobs in this group in Priority decending order (pre-sorted in stateStruct).
                for jobID in self.groupsDict[groupName].JobsIDs:
                    #Test the job against each region that has enabled this group in region-preference order (pre-sorted in StateStruct).
                    for regionID in self.groupsDict[groupName].EnabledRegions:
                        # Skip this region if all the job's tasks have been (theoretically) allocated.
                        if self.jobUnallocatedTasksDict[jobID] == 0:
                            continue
                            
                        # Skip this region if the job's associated group cost exceeds the remaining budget for this region.
                        groupCost = next( item for item in self.cloudRegionsDict[regionID].EnabledGroups if item.Name == groupName).Cost
                        if self.regionBudgetDict[regionID] < groupCost:
                            continue
                            
                        # Skip this region if the job's assets are not ready in this region.  (Jobs with no assets will list all enabled regions).
                        if not regionID in self.jobsDict[jobID].AssetReadyRegions:
                            continue

                        limitExhausted = False
                        for limitID in self.jobsDict[jobID].Limits:
                            if self.limitStubsDict[limitID][1] == False:
                                if self.limitStubsDict[limitID][0] == 0:
                                    limitExhausted = True
                                    break

                        if limitExhausted:
                            continue

                        jobAvailable = True
                        #--------
                        # This job has viability, so deduct resources and add to group count for this region.

                        # Deduct allocations from the Region's budget.
                        self.regionBudgetDict[regionID] = self.regionBudgetDict[regionID] - (groupCost)
                        
                        # Deduct stubs from the Limits used by this job.
                        for limitID in self.jobsDict[jobID].Limits:
                            if self.limitStubsDict[limitID][1] == False:
                                self.limitStubsDict[limitID][0] = self.limitStubsDict[limitID][0] - 1
                        
                        # Deduct from the unallocated tasks for this job.
                        self.jobUnallocatedTasksDict[jobID] = self.jobUnallocatedTasksDict[jobID] - 1
                        
                        # Add this job's allocations to the count for this group in this region.
                        groupAllocation = self.targetsDict[regionID][groupName]
                        groupAllocation = groupAllocation + 1
                        self.targetsDict[regionID][groupName] = groupAllocation
                        
                        
                        #Recalculate group Weight                        
                        num = self.jobsDict[jobID].Priority * self.groupDemandList[0][1]["TaskCount"]
                        dem = self.targetsDict[regionID][groupName] + 1
                        
                        self.groupDemandList[0][1]["Weight"] = num/dem                        
                        
                for region in self.cloudRegionsDict:
                    for groups in self.cloudRegionsDict[region].EnabledGroups:                               
                        if self.regionBudgetDict[self.cloudRegionsDict[region].ID] >= groups.Cost and jobAvailable:
                            spaceAvailable = True
                            break     
         
        except:
            ClientUtils.LogText(traceback.format_exc())
            
            
    def PopulateTargets(self):
        try:
            if self.verboseLogging:
                ClientUtils.LogText("Populating Targets")

            #-------------#
            # == STAGE 4 ==  Populate targets.
            
            cloudRegionTargetStructList = []

            for rvPair in self.targetsDict:
                regionID = rvPair
                groupTargetDict = self.targetsDict[rvPair]
                
                groupTargetStructList = []
                
                for gvPair in groupTargetDict:
                    groupName = gvPair
                    
                    groupTargetStruct = GroupTargetStruct(groupName, self.targetsDict[regionID][groupName])

                    if self.verboseLogging:
                        ClientUtils.LogText("Group: %s Target: %s" % (groupName, self.targetsDict[regionID][groupName]))
                    
                    groupTargetStructList.append(groupTargetStruct)
                    
                cloudRegionTargetStruct = CloudRegionTargetStruct()
                cloudRegionTargetStruct.RegionName = regionID
                cloudRegionTargetStruct.GroupTargets = groupTargetStructList
                
                cloudRegionTargetStructList.append(cloudRegionTargetStruct)
            
            targetStruct = BalancerTargetStruct()
            targetStruct.ErrorEncountered = False
            targetStruct.ErrorMessage = ""
            targetStruct.Message = "Algorithm completed successfully."
            targetStruct.CloudRegionTargets = cloudRegionTargetStructList
                
            return targetStruct
        except:
            ClientUtils.LogText(traceback.format_exc())
