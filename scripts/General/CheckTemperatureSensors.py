import threading

from PyQt5.QtCore import *
from PyQt5.QtGui import *

from System import DateTime, Exception

from Deadline.Scripting import *

from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

scriptDialog = None
updateButton = None
sensors = None

def __main__():
    global scriptDialog
    global updateButton
    global sensors
    
    controlNames = []
    powerManagementOptions = RepositoryUtils.GetPowerManagementOptions()
    
    scriptDialog = DeadlineScriptDialog()
    scriptDialog.SetSize( 400, 0 )
    scriptDialog.SetTitle( "Temperature Sensors" )
    
    for group in powerManagementOptions.Groups:
        if len(group.ThermalShutdownOptions.Sensors) > 0:
            
            scriptDialog.AddGrid()
            scriptDialog.AddControlToGrid( group.Name + "Separator", "SeparatorControl", "Group: " + group.Name, 0, 0, colSpan=2 )
            
            row = 1
            for sensor in group.ThermalShutdownOptions.Sensors:
                controlName = group.Name + sensor.Name
                controlNames.append( controlName )
                
                scriptDialog.AddControlToGrid( controlName + "Label", "LabelControl", sensor.Name, row, 0 , "", False )
                scriptDialog.AddControlToGrid( controlName, "ReadOnlyTextControl", "", row, 1 )
                
                row = row + 1
            
            scriptDialog.EndGrid()
            
    scriptDialog.AddGrid()
    
    scriptDialog.AddControlToGrid( "UpdateLabel", "LabelControl", "Update Interval", 0, 0 , "The number of seconds between sensor updates", False )
    scriptDialog.AddRangeControlToGrid( "UpdateBox", "RangeControl", 30, 5, 600, 0, 1, 0, 1 )
                
    updateButton = scriptDialog.AddControlToGrid( "UpdateButton", "ButtonControl", "Start Updating", 0, 2, expand=False )
    updateButton.ValueModified.connect(UpdateButtonPressed)
    
    closeButton = scriptDialog.AddControlToGrid( "CloseButton", "ButtonControl", "Close", 0, 3, expand=False )
    closeButton.ValueModified.connect(CloseButtonPressed)
    scriptDialog.EndGrid()
    
    sensors = Sensors( controlNames )
    sensors.sensorUpdate.connect( SensorUpdated )
    
    scriptDialog.ShowDialog( False )

def CloseButtonPressed():
    global scriptDialog
    global sensors
    
    sensors.Stop()
    scriptDialog.CloseDialog()
    
def UpdateButtonPressed():
    global scriptDialog
    global updateButton
    global sensors
    
    if updateButton.text() == "Start Updating":
        sensors.Start( scriptDialog.GetValue( "UpdateBox" ) * 1000 )
        updateButton.setText( "Stop Updating" )
        scriptDialog.SetEnabled( "UpdateLabel", False )
        scriptDialog.SetEnabled( "UpdateBox", False )
    else:
        sensors.Stop()
        updateButton.setText( "Start Updating" )
        scriptDialog.SetEnabled( "UpdateLabel", True )
        scriptDialog.SetEnabled( "UpdateBox", True )

def SensorUpdated( controlName, text ):
    global scriptDialog
    scriptDialog.SetValue( controlName, text )

class Sensors( QObject ):
    sensorUpdate = pyqtSignal( str, str )
    
    def __init__( self, controlNames ):
        super( Sensors, self ).__init__()
        self.controlNames = controlNames
        self.updateInterval = 30000
        self.isRunning = False
        self.sensorThread = None
        self.sensorTempDict = {}
    
    def Start( self, updateInterval ):
        if not self.isRunning:
            self.updateInterval = updateInterval
            self.isRunning = True
            
            if not self.sensorThread or not self.sensorThread.isAlive():
                self.sensorThread = threading.Thread( target = self.CheckSensors )
                self.sensorThread.start()
        
    def Stop( self ):
        if self.isRunning:
            self.isRunning = False
            
            if self.sensorThread and self.sensorThread.isAlive():
                self.sensorThread.join()
                self.sensorThread = None
        
    def CheckSensors( self ):
        while self.isRunning:
            powerManagementOptions = RepositoryUtils.GetPowerManagementOptions()
            for group in powerManagementOptions.Groups:
                for sensor in group.ThermalShutdownOptions.Sensors:
                    
                    controlName = group.Name + sensor.Name
                    if controlName in self.controlNames:
                        try:
                            temperature = sensor.GetTemperature( sensor.TemperatureUnit ).TemperatureValue
                            
                            temperatureDirection = ""
                            if controlName in self.sensorTempDict:
                                previousTemperature = self.sensorTempDict[controlName]
                                if temperature < previousTemperature:
                                    temperatureDirection = " (decreased from %s)" % previousTemperature
                                elif temperature > previousTemperature:
                                    temperatureDirection = " (increased from %s)" % previousTemperature
                                else:
                                    temperatureDirection = " (steady)"
                            
                            self.sensorTempDict[controlName] = temperature
                            
                            temperatureUnit = ""
                            if sensor.TemperatureUnit == 0:
                                temperatureUnit = "Celcius"
                            elif sensor.TemperatureUnit == 1:
                                temperatureUnit = "Fahrenheit"
                            elif sensor.TemperatureUnit == 2:
                                temperatureUnit = "Kelvin"
                            
                            self.sensorUpdate.emit( controlName, "%s %s%s" % (temperature, temperatureUnit, temperatureDirection) )
                            
                        except Exception as e:
                            self.sensorUpdate.emit( controlName, e.Message )
            
            now = DateTime.Now
            while self.isRunning and DateTime.Now.Subtract( now ).TotalMilliseconds < self.updateInterval:
                SystemUtils.Sleep( 250 )
