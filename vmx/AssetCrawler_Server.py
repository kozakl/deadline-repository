#!/usr/bin/python

from __future__ import print_function
import os
import socket
import sys
import signal

from datetime import datetime, timedelta
from time import sleep

HOST = None #interface-agnostic local host
PORT = 53544 #port to listen on
BUFFER_SIZE = 1024 #receive buffer size 

GLOBAL_CHECK_INTERVAL = 1 #Global cooldown on asset checks
CHECK_MINUTES = 5 #How often we re-check individual assets
DELETE_DAYS = 2 #How long we wait before paging out assets from the cache

sockets = [] #keep a list of open sockets (will be one per interface)
trackedAssets = {} #dictionary of Assets, where the Key is the asset path, and the value is a TrackedAsset (see below)

exit = False #used to gracefully terminate the server

last_global_check = datetime.now()

#Simple class to track asset-related things. This could really just be a tuple, but decided to make a class to keep things readable
class TrackedAsset( object ):
	def __init__( self, assetPath, currentlyPresent ):
		print( "Now tracking asset '%s'" % assetPath )
		dtNow = datetime.now()
		self.assetPath = assetPath #path to the asset
		self.available = currentlyPresent #last known availability of the asset
		
		self.lastRequestTime = dtNow #last time we were queried for the status of this asset (assume 'now')
		self.lastCheckTime = dtNow #last time we checked on the asset's existence (assume 'now')

#Goes through cached assets, updating their status if necessary
def CheckAssets():
	global CHECK_MINUTES
	global DELETE_DAYS
	global trackedAssets
	
	#Only do asset checks every few minutes
	currTime = datetime.now()
	
	deleteList = []
	#Check if any of the missing assets are there now
	for assetPath in trackedAssets:
		currentAsset = trackedAssets[ assetPath ]
		
		#If this asset hasn't been requested in a while, delete it from the cache
		requestDelta = currTime - currentAsset.lastRequestTime
		if requestDelta > timedelta( days=DELETE_DAYS ):
			print( "Asset '%s' hasn't been requested in >%d days, removing it from internal cache." % (assetPath, DELETE_DAYS) )
			deleteList.append( assetPath ) #need to delete later so we don't modify the dict during iteration
		else:
			#If we haven't checked its status in a while, update our cache's status
			checkDelta = currTime - currentAsset.lastCheckTime
			if checkDelta > timedelta( minutes=CHECK_MINUTES ):
				print( "Re-checking asset '%s'" % assetPath )
				oldVal = currentAsset.available
				currentAsset.available = os.path.isfile( assetPath )
				
				if oldVal != currentAsset.available:
					print( "Asset '%s' is %s present." % (assetPath, "no longer" if oldVal else "now" ) )
					
				currentAsset.lastCheckTime = currTime
	
	#delete any old assets from the cache
	for oldAsset in deleteList:
		del trackedAssets[ oldAsset ]

#Creates and opens the sockets on which we'll be listening
def OpenSockets():
	global HOST
	global PORT
	global sockets
	
	#go through all our address resolutions, regardless of interface (ie, IPv4 vs IPv6)
	for res in socket.getaddrinfo( HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE ):
		af, socktype, proto, canonname, sa = res
		
		print( af, socktype, proto, canonname, sa )
		
		sock = None
		
		try:
			sock = socket.socket( af, socktype, proto )
		except socket.error as msg:
			print( "Failed to create socket for %s, because:" % (sa, ) )
			print( str( msg ) )
			continue
		
		#set to non-blocking for now, since we possibly are binding to multiple addresses
		sock.setblocking( 0 )
		
		try:
			sock.bind( sa )
			sock.listen( 1 )
		except socket.error as msg:
			print( "Failed to bind on %s, because:" % (sa, ) )
			print( str( msg ) )
			sock.close()
			continue
		
		#keep track of all sockets we're listening on
		sockets.append( sock )

#Handles a client request and responds appropriately
def HandleConnection( conn, addr ):
	global BUFFER_SIZE
	global trackedAssets
	
	print( "Client connected:", addr )
	
	#switch this socket to blocking, since we don't need non-blocking here
	conn.setblocking( 1 )
	
	fileList = []
	
	#Keep receiving till client shuts down sending (ie, calls 'shutdown( SHUT_WR )')
	while True:
		data = conn.recv( BUFFER_SIZE )
		
		if not data:
			break
			
		tokens = data.split( '\n' )
		
		#If we already read in some stuff, this is just a continuation of it
		if len( fileList ) > 0:
			fileList[-1] += tokens[0] #the last recv buffer would have cut off the last entry, append the rest here
			fileList.extend( tokens[1:] )
		else:
			fileList = tokens
	
	print( "Received %d file names:" % len( fileList ) )

	#Checks the file list to see what we have
	filesPresent = True
	for file in fileList:
		file = file.strip()
		if len( file ) == 0: #skip empty lines
			continue
		
		print( "Checking status of '%s'..." % file )
		
		#check our in-memory cache first
		if file in trackedAssets:
			print( "In the cache" )
			asset = trackedAssets[ file ]
			dtNow = datetime.now()
			#if it wasn't here last time, check again
			if not asset.available:
				asset.available = os.path.isfile( file )
				asset.lastCheckTime = dtNow
			
			filesPresent &= asset.available
			trackedAssets[ file ].lastRequestTime = dtNow #update LRT so we don't page this entry out for another few days
		else:
			print( "Not in the cache" )
			available = os.path.isfile( file )
			trackedAssets[ file ] = TrackedAsset( file, available )
			filesPresent &= available
		
		#if we are missing an asset, we don't really need to check the rest
		if not filesPresent:
			print( "Required file '%s' is missing!" % file )
			break
	
	#Returns 'True' or 'False'
	print( "Replying with: " + str( filesPresent ) )
	conn.sendall( str( filesPresent ) )
	
	print( "Closing connection with client" )
	conn.shutdown( socket.SHUT_WR )
	conn.close()

#This is our main listening loop
def MainLoop():
	global sockets
	global exit
	global last_global_check
	
	#Open sockets for listening
	OpenSockets()

	if len( sockets ) == 0:
		print( "Could not open any sockets on port %d." % PORT )
		sys.exit( 1 )

	#Successfully listening on our port; we're good to go!
	print( "Listening on port " + str(PORT) )

	try:
		#Main loop
		while not exit:
			conn = None
			try:
				addr = None
				
				#Go through all our sockets until we find a connection to accept
				work_count = len (sockets)
				for sock in sockets:
					try:
						conn, addr = sock.accept()
					except socket.error as msg:
						conn = None
						addr = None
						work_count -= 1
						if work_count == 0:
							# Sleep if no sockets had any work
							sleep(0.5)

						continue
						
					break
				
				#Check if we found a connection or not
				if conn != None:
					#Handle the client connection
					HandleConnection( conn, addr )
				else:
					#Find out how long it's been since we did an asset check
					dtNow = datetime.now()
					checkDelta = dtNow - last_global_check
					
					if checkDelta > timedelta( minutes=GLOBAL_CHECK_INTERVAL ):
						#get an update on our cached assets
						last_global_check = dtNow
						CheckAssets()
				
			except socket.error as msg:
				#client probably just died, print out the error and keep going
				print( str( msg ) )
	finally:
		#Close our sockets if they're still open
		print( "Closing open sockets." )
		for sock in sockets:
			sock.close()

#Handles signals to exit gracefully
def SignalHandler( signum, frame ):
	global exit
	print( "Caught signal: ", signum )
	exit = True

try:
	#handle signals so we can exit gracefully on Unix systems (doesn't work on Windows, but whatever)
	signal.signal( signal.SIGINT, SignalHandler )
	signal.signal( signal.SIGTERM, SignalHandler )
	signal.signal( signal.SIGHUP, SignalHandler )
	signal.signal( signal.SIGKILL, SignalHandler )
except:
	pass

#Start our main server loop
MainLoop()

print( "Server exiting." )
