
# IntesisHome Inegration with  Domoticz
#
# Author: CV8R
#
"""
<plugin key="BasePlug" name="IntesisBox WMP-1 Protocol" author="CV8R" version="0.0.9" >
	<description>
		<h2>IntesisBox WMP-1</h2><br/>
		<ul style="list-style-type:square">
			<li>IntesisBox WMP-1 interface for air conditioners into IP based control systems</li>
		</ul>
		<ul style="list-style-type:square">
		<h3>Configuration</h3><br/>
			<li>IP Address and Port number default 3310 </li>
		</ul>
	</description>
	<params>
		<param field="Address" label="IP Address" width="200px" required="true" default=""/>
		<param field="Port" label="Port" width="30px" required="true" default="3310"/>
		<param field="Mode1" label="Debug" width="75px">
			<options>
				<option label="True" value="Debug"/>
				<option label="False" value="Normal"  default="true" />
			</options>
		</param>
	</params>
</plugin>
"""
from typing import List


# Global var definitions
InitHeartbeatCount = 0
unitmode = "N/A"
oustandingPings = -1
lastHeartbeat = 0


# Limits as Global vars
minTempLimit = 180
maxTempLimit = 280

import Domoticz
import base64
import datetime
import re

class BasePlugin:
	enabled = True
	powerOn = 0
	runCounter = 0


	WMPConn = None
	oustandingPings = 0
	lastHeartbeat = datetime.datetime.now()

	def __init__(self):
		#self.var = 123
		return

	def onStart(self):
		Domoticz.Log("onStart called")

		Domoticz.Heartbeat(20) # Set heartbeat interval slower than default

		if Parameters["Mode1"] == "Debug":
			Domoticz.Debugging(1)

		if (len(Devices) == 0):
			Domoticz.Device(Name="Power", Unit=1, Image=16, TypeName="Switch", Used=1).Create()
			Domoticz.Device(Name="Ambient Temp", Unit=2, TypeName="Temperature", Used=1).Create()

			Options = {"LevelActions" : "|||||",
						"LevelNames" : "|Auto|Heat|Dry|Cool|Fan",
						"LevelOffHidden" : "true",
						"SelectorStyle" : "0"}
			
			Domoticz.Device(Name="Mode", Unit=3, TypeName="Selector Switch", Image=16, Options=Options, Used=1).Create()
			
			Options = {"LevelActions" : "||||",
						"LevelNames" : "|Auto|L1|L2|L3",
						"LevelOffHidden" : "true",
						"SelectorStyle" : "0"}

			Domoticz.Device(Name="Fan Speed", Unit=4, TypeName="Selector Switch", Image=7, Options=Options, Used=1).Create()

			Domoticz.Device(Name="Set Temp", Unit=5, Type=242, Subtype=1, Image=16, Used=1).Create()

			Domoticz.Device(Name="Error LED", Unit=6,  Image=13, TypeName="Switch", Used=1).Create()
			Domoticz.Device(Name="Error Text", Unit=7, TypeName="Text", Used=1).Create()

			Domoticz.Log("Device created.")

		DumpConfigToLog()

	def onStop(self):
		Domoticz.Log("onStop called")

	def onConnect(self, Connection, Status, Description):
		Domoticz.Log("onConnect called")
		global ConnectState
		Domoticz.Log("Connecting")
		if (Connection == self.WMPConn):
			if (Status == 0):
				Domoticz.Log("Connected successfully to: " + Connection.Address + ":" + Connection.Port)
				self.WMPConn.Send('ID\n') # Get ID at startup
		else:
			if (Description.find("Only one usage of each socket address") > 0):
				Domoticz.Log(Connection.Address + ":" + Connection.Port + " is busy, waiting.")
			else:
				Domoticz.Log("Failed to connect (" + str(Status) + ") to: " + Connection.Address + ":" + Connection.Port + " with error: " + Description)
			self.WMPConn = None

	def onMessage(self, Connection, Data):
		Domoticz.Debug("onMessage called")
		global unitmode
		global oustandingPings
		global lastHeartbeat
		global minTempLimit
		global maxTempLimit

		strData = Data.decode("utf-8", "ignore")
		Domoticz.Debug("onMessage called with Data: '" + str(strData) + "'")
		#msgDataListRaw = re.split(r':+|,', strData)  # type: List[str]
		msgDataListRaw = re.split(r':+|,+|\[+|\]', strData)  # split string to list of strings
		msgDataList = list(filter(None, msgDataListRaw)) # Remove consecutive delimiters note: filter does not return a list, use list to turn into list
		# Dump stripped messages in to Domoticz Log
		count = 0
		for msgData in msgDataList:
			Domoticz.Debug("Stripped Message[" + str(count) + "] = " + msgData ) # Log the messages incoming and their stripped count
			count = count + 1

		Domoticz.Debug("Resetting Ping to 0")
		oustandingPings = 0  # Reset ping counter onmessage for making sure connection is up in Heartbeat

		# Is it a status update

		if (msgDataList[0] == 'ACK'):
			Domoticz.Debug("Message Acknowledged with response: " + msgDataList[0])
		elif (msgDataList[0] == 'ERR'):
			Domoticz.Error("WMP Message ########## SENDING MESSAGE ERROR ########## with response: " + msgDataList[0])
			Devices[6].Update(nValue=1, sValue="100") # Set the Error LED switch to ON to flag for a send error
		elif (msgDataList[0] == 'LIMITS'): #Get the limits from the AC unit
			DataValues = '|'.join(msgDataList[2:])
			if (msgDataList[1] == 'ONOFF'): #Get the ONOFF limits from the AC unit
				Domoticz.Log("ONOFF Limits from unit: " + DataValues)
			elif (msgDataList[1] == 'MODE'): #Get the MODE limits from the AC unit
				Domoticz.Log("MODE Limits from unit: " + DataValues)
			elif (msgDataList[1] == 'FANSP'): #Get the FANSP limits from the AC unit
				Domoticz.Log("FANSP Limits from unit: " + DataValues)
			elif (msgDataList[1] == 'VANEUD'): #Get the VANEUD limits from the AC unit
				Domoticz.Log("VANEUD Limits from unit: " + DataValues)
			elif (msgDataList[1] == 'VANELR'): #Get the VANELR limits from the AC unit
				Domoticz.Log("VANELR Limits from unit: " + DataValues)
			elif (msgDataList[1] == 'SETPTEMP'): #Get the SETPTEMP temp limits from the AC unit
				Domoticz.Debug("SETPTEMP Temp limit values from unit: " + DataValues)
				minTempLimit = int(msgDataList[2])
				maxTempLimit = int(msgDataList[3])
				Domoticz.Status("Min Temp Limit: " + str(minTempLimit) + " Max Temp Limit: " + str(maxTempLimit))
		if (msgDataList[0] == 'CHN'):
			Domoticz.Debug("Status Update - Unit: " + msgDataList[1] + " Function: " + msgDataList[2] + " Value = " + msgDataList[3])
			# Update the status to Domoticz
			if (msgDataList[2] == 'ONOFF'):
				if (msgDataList[3] == 'ON'):
					Domoticz.Status("Update status to On")
					Devices[1].Update(nValue=1, sValue="100") # AC Power
				elif (msgDataList[3] == 'OFF'):
					Domoticz.Status("Update status to Off")
					Devices[1].Update(nValue=0, sValue="0")
			elif (msgDataList[2] == 'AMBTEMP'):
				ambtemp = str(float(msgDataList[3])/10)
				Domoticz.Log("Ambient temp")
				Domoticz.Debug("Current ambient temp: " + ambtemp + " Degrees")
				Devices[2].Update(nValue=0, sValue=ambtemp)
				#Domoticz.Debug("Resetting Ping to 0") # using AMBTEMP
				#oustandingPings = 0 # Reset ping counter for making sure connection is up in Heartbeat
			elif (msgDataList[2] == 'SETPTEMP'):
				settemp = str(int(msgDataList[3])/10)
				if (unitmode != 'FAN'):
					Domoticz.Status("Set temp is set to: " + settemp + " Degrees")
					Devices[5].Update(nValue=1, sValue=settemp) # Update the temp display in the set temp device
				else:
					Domoticz.Debug("FAN MODE setting temp to not display")
					Devices[5].Update(nValue=1, sValue="22")  # N/A to have a temp displayed
			elif (msgDataList[2] == 'MODE'):
				unitmode = msgDataList[3]
				if (unitmode == "AUTO"):
					Domoticz.Status("Mode to: " + unitmode)
					Devices[3].Update(nValue=1, sValue="10") # Auto
				elif (unitmode == "HEAT"):
					Domoticz.Status("Mode to: " + unitmode)
					Devices[3].Update(nValue=1, sValue="20") # Heat
				elif (unitmode == "DRY"):
					Domoticz.Status("Mode to: " + unitmode)
					Devices[3].Update(nValue=1, sValue="30") # Dry
				elif (unitmode == "COOL"):
					Domoticz.Status("Mode to: " + unitmode)
					Devices[3].Update(nValue=1, sValue="40") # Cool
				elif (unitmode == "FAN"):
					Domoticz.Status("Mode to: " + unitmode)
					Devices[3].Update(nValue=1, sValue="50") # Fan
				Devices[3].Refresh()
			elif (msgDataList[2] == 'FANSP'):
				fspeed = msgDataList[3]
				if (fspeed == "AUTO"):
					Domoticz.Status("Fan Speed to: " + fspeed)
					Devices[4].Update(nValue=1, sValue="10") # Fan Auto
				elif (fspeed == "1"):
					Domoticz.Status("Fan Speed to: " + fspeed)
					Devices[4].Update(nValue=1, sValue="20") # Fan Level 1
				elif (fspeed == "2"):
					Domoticz.Status("Fan Speed to: " + fspeed)
					Devices[4].Update(nValue=1, sValue="30") # Fan Level 2
				elif (fspeed == "3"):
					Domoticz.Status("Fan Speed to: " + fspeed)
					Devices[4].Update(nValue=1, sValue="40") # Fan Level 3
				Devices[4].Refresh()
			elif (msgDataList[2] == 'VANEUD'):
				vaneud = msgDataList[3]
				Domoticz.Status("Vane Up/Down: " + vaneud)
			elif (msgDataList[2] == 'VANELR'):
				vanelr = msgDataList[3]
				Domoticz.Status("Vane Left/Right: " + vanelr)
			elif (msgDataList[2] == 'ERRSTATUS'):
				errorstatus = msgDataList[3]
				if (errorstatus != "OK"):
					Domoticz.Status("Error Status: " + errorstatus)
					Devices[6].Update(nValue=1, sValue="100")  # Set the Error LED switch to ON to flag for an ERROR
				elif (errorstatus == "OK"):
					Domoticz.Status("Error Status: " + errorstatus)
					Devices[6].Update(nValue=0, sValue="0")  # Set the Error LED switch to OFF to clear ERROR
			elif (msgDataList[2] == 'ERRCODE'):
				errorcode = msgDataList[3]
				Domoticz.Status("Error Code: " + errorcode)
				Devices[7].Update(nValue=1, sValue=errorcode)  # Set error text
			else:
				Domoticz.Error("Unrecognised status command")

	def onCommand(self, Unit, Command, Level, Hue):
		Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

		if (Unit == 1):
			if (Command == "On"):
				Domoticz.Status("Sending Power ON")
				self.powerOn = 1
				self.WMPConn.Send('SET,1:ONOFF,ON\n')
			elif(Command == "Off"):
				Domoticz.Status("Sending Power OFF")
				self.powerOn = 0
				self.WMPConn.Send('SET,1:ONOFF,OFF\n')
		elif (Unit == 3):
			if (Command == "Set Level"):
				Domoticz.Debug("Sending Mode")
				if (str(Level) == '10'):
					Domoticz.Status("Sending Mode Auto")
					self.WMPConn.Send('SET,1:MODE,auto\n')
				elif (str(Level) == '20'):
					Domoticz.Status("Sending Mode Heat")
					self.WMPConn.Send('SET,1:MODE,heat\n')
				elif (str(Level) == '30'):
					Domoticz.Status("Sending Mode Dry")
					self.WMPConn.Send('SET,1:MODE,dry\n')
				elif (str(Level) == '40'):
					Domoticz.Status("Sending Mode Cool")
					self.WMPConn.Send('SET,1:MODE,cool\n')
				elif (str(Level) == '50'):
					Domoticz.Status("Sending Mode Fan")
					self.WMPConn.Send('SET,1:MODE,fan\n')
			self.WMPConn.Send('LIMITS:SETPTEMP\n') # Check temp limits again when changing modes
		elif (Unit == 4):
			if (Command == "Set Level"):
				Domoticz.Debug("Sending Fan Speed")
				if (str(Level) == '10'):
					Domoticz.Status("Sending Fan Speed Auto")
					self.WMPConn.Send('SET,1:FANSP,AUTO\n')
				elif (str(Level) == '20'):
					Domoticz.Status("Sending Fan Speed Level 1")
					self.WMPConn.Send('SET,1:FANSP,1\n')
				elif (str(Level) == '30'):
					Domoticz.Status("Sending Fan Speed Level 2")
					self.WMPConn.Send('SET,1:FANSP,2\n')
				elif (str(Level) == '40'):
					Domoticz.Status("Sending Fan Speed Level 3")
					self.WMPConn.Send('SET,1:FANSP,3\n')
		elif (Unit == 5):
			if (Command == "Set Level"):
				settemp = Level
				Domoticz.Debug("String of Set Temp raw value = " + str(Level))
				settemp = round((int((float(settemp) * 10)))/5)*5 #includes complex rounding to nearest 5
				Domoticz.Debug("Set Temp converted value = " + str(settemp))
				if settemp < minTempLimit: #Adjusting for minLimit of unit
					Domoticz.Status("Set temp point less than min limit setting to min value = " + str(minTempLimit / 10) + " Degrees")
					settemp = minTempLimit #Send the minimum of unit
				if settemp > maxTempLimit: #Adjusting for minLimit of unit
					Domoticz.Status("Set temp point greater than max limit setting to max value = " + str(maxTempLimit / 10) + " Degrees")
					settemp = maxTempLimit
			Domoticz.Status("Setting Temp to: " + str(settemp / 10) + " Degrees")
			Domoticz.Debug("Sending Set Temp to: " + str(settemp))
			self.WMPConn.Send('SET,1:SETPTEMP,' + str(settemp) + '\n')
		elif (Unit == 6):
			if (Command == "Off"):
					Domoticz.Log("User cleared the ERROR Status LED")
					Devices[6].Update(nValue=0, sValue="0")  # Set the Error LED switch to Off
		else:
			Domoticz.Error("No command available to send")

	def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
		Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

	def onDisconnect(self, Connection):
		Domoticz.Log("onDisconnect called")
		self.WMPConn = None

	def onHeartbeat(self):
		global InitHeartbeatCount  # Counter for first heartbeats
		global oustandingPings # Counter for the Pings for check alive using AMBTEMP
		global lastHeartbeat
		Domoticz.Debug("onHeartbeat called")
		Domoticz.Debug("onHeartbeat called, last response seen " + str(oustandingPings) + " heartbeats ago.")
		Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount))
		lastHeartbeat = datetime.datetime.now()
		if (self.WMPConn == None):
			Domoticz.Log("Connect to WMP")
			InitHeartbeatCount = 0  # reset heartbeat count
			oustandingPings = -1 # reset ping count
			self.handleConnect()
		else:
			if (self.WMPConn.Name == "WMP_Connection") and (self.WMPConn.Connected()):
				oustandingPings = oustandingPings + 1  # Increment Ping Counter, reset at AMPTEMP Status
				if InitHeartbeatCount <= 6:
					InitHeartbeatCount = InitHeartbeatCount + 1
					Domoticz.Debug("Heartbeat Init Count Incremented now = " + str(InitHeartbeatCount))
					if InitHeartbeatCount == 1: #Need to delay these inital messages or some are missed
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting ONOFF")
						self.WMPConn.Send('GET,1:ONOFF\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting MODE")
						self.WMPConn.Send('GET,1:MODE\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting SETPTEMP")
						self.WMPConn.Send('GET,1:SETPTEMP\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting FANSP")
						self.WMPConn.Send('GET,1:FANSP\n')
					if InitHeartbeatCount == 3:
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting VANEUD")
						self.WMPConn.Send('GET,1:VANEUD\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting VANELR")
						self.WMPConn.Send('GET,1:VANELR\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting ERRSTATUS")
						self.WMPConn.Send('GET,1:ERRSTATUS\n')
					if InitHeartbeatCount == 4:
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting ERRCODE")
						self.WMPConn.Send('GET,1:ERRCODE\n')
					if InitHeartbeatCount == 5:
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting LIMITS ONOFF")
						self.WMPConn.Send('LIMITS:ONOFF\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting LIMITS MODE")
						self.WMPConn.Send('LIMITS:MODE\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting LIMITS FANSP")
						self.WMPConn.Send('LIMITS:FANSP\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting LIMITS VANEUD")
						self.WMPConn.Send('LIMITS:VANEUD\n')
					if InitHeartbeatCount == 6:
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting LIMITS VANELR")
						self.WMPConn.Send('LIMITS:VANELR\n')
						Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount) + " Getting LIMITS SETPTEMP")
						self.WMPConn.Send('LIMITS:SETPTEMP\n')
						Domoticz.Heartbeat(20)  # Extending heartbeat at last Limit
				if InitHeartbeatCount == 7:  # when count gets to this number and is connected, it will not increment and commence AMBTEMP Heartbeats
					Domoticz.Debug("Getting Ambient Temp")
					self.WMPConn.Send('GET,1:AMBTEMP\n')  # Get AMBTEMP at Heartbeat to confirm connected
			if (oustandingPings == 3):
				Domoticz.Log(self.WMPConn.Name + " has not responded to 3 heartbeats terminating connection.")
				if (self.WMPConn.Connected()):
					self.WMPConn.Disconnect()
					Domoticz.Debug("Heartbeat Init Count = " + str(InitHeartbeatCount))
				self.WMPConn = None


	def handleConnect(self):
		self.WMPConn = None
		Domoticz.Debug("Settings shorter heartbeat to speed up initialisation")
		Domoticz.Heartbeat(5)  # Setting the inital hearbeat timeout used for delaying startup messages - extended in onHeartbeat after counter reached
		self.WMPConn = Domoticz.Connection(Name="WMP_Connection", Transport="TCP/IP", Protocol="Line", Address=Parameters["Address"], Port=Parameters["Port"])
		self.WMPConn.Connect()


global _plugin
_plugin = BasePlugin()

def onStart():
	global _plugin
	_plugin.onStart()

def onStop():
	global _plugin
	_plugin.onStop()

def onConnect(Connection, Status, Description):
	global _plugin
	_plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
	global _plugin
	_plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
	global _plugin
	_plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
	global _plugin
	_plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
	global _plugin
	_plugin.onDisconnect(Connection)

def onHeartbeat():
	global _plugin
	_plugin.onHeartbeat()

	# Generic helper functions
def DumpConfigToLog():
	for x in Parameters:
		if Parameters[x] != "":
			Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
	Domoticz.Debug("Device count: " + str(len(Devices)))
	for x in Devices:
		Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
		Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
		Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
		Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
		Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
		Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
	return
