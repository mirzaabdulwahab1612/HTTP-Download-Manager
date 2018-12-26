from socket import *
import sys
import select
import math
import string
import threading
import argparse
import os.path
import time

#Argument parsing
parser = argparse.ArgumentParser(description = 'Get file from the web')
parser.add_argument('-n' , '--nthreads', type = int, required=True , help='Number of threads for the connection')
parser.add_argument('-i' , '--interval', type = float, required=True , help='Time interval of metric reporting')
parser.add_argument('-c' , '--tlp' ,type = str, required=True , help='TCP or UDP')
parser.add_argument('-f' , '--sourceaddress',type = str, required=True , help='File location on the web')
parser.add_argument('-o' , '--destinationaddress',type = str, required=True , help='File destination address')
parser.add_argument('-r' , '--resume' , action='store_true' , help='Resume download' )
args = parser.parse_args()

#default http header size for most servers
buff_size = 8192
#http port number
portNumber=80
#metric file keeping length of content downloaded and the time in which downloaded
metric = []
#array for bytes per thread
currentdataperthread = []

#geting file type from the header
def getFileType(fields):
	if('content-type' not in fields):
		ftype = 'txt'
		return ftype
	else:
		#Getting content type format
		ftype = fields['content-type']
		ftype = ftype
		ftype = ftype.split('/')[1]
		ftype = ftype.split(';')[0]
		if(ftype == 'plain'):
			ftype = 'txt'
		return ftype

#Converts file name to a valid file name.
def format_filename(s):
	valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
	filename = ''.join(c for c in s if c in valid_chars)
	filename = filename.replace(' ','_') # I don't like spaces in filenames.
	filename = filename.split('.')[0]
	return filename

#Splitting URL into the host name, resource address, File name
def urlFields(url):
	#removing protocol from the address
	if('https' in url):
		print("HTTPS")
		url = url.replace('https://' , '')
	elif('http' in url):
		print("HTTP")
		url = url.replace('http://' , '')
	#Getting host, address, and file name
	url = url.split("/")
	host = url[0]
	faddress = ''
	for i in range(1,len(url)):
		faddress += '/' + url[i]
	fname = url[len(url)-1]
	fname = format_filename(fname)
	return host , faddress , fname

#Converts the response header message into a dictionary of header fields, splits status and the content from the HEADER response.
def getHeaderFeildsAndContent(data):
	temp = data.split(b'\r\n\r\n')
	header = temp[0]
	content = temp[1]
	header = header.decode('utf-8')
	if(header == ''):
		print("File Not Found")
		exit(0)
	header = header.split('\r\n')
	status = header[0]
	header = header[1:]
	# header = header
	fields = dict()
	for i in range(len(header)):
		temp = header[i].split(':')
		fields[temp[0].lower()] = temp[1].lower()

	return status ,fields , content

#check whether the requsted can be handled using threaded request
def checkThreadRequest(fields):
	#can be done over multiple threads
	if('content-length' in fields.keys() and 'accept-ranges' in fields.keys() and fields['accept-ranges'] != 'none'):
		return 1
	#can not be done over multiple threads
	else:
		return 2
	
	return 0

#processing request for each thread
def processRequest(numberofthreads, dest, logFile , fileaddress ,resume):
	global  metric , currentdataperthread
	#metric array
	metric = [None] * numberofthreads

	#saving number of threads info
	with open(dest + logFile + "_ThreadInfo" , "wb") as myFile:
		myFile.write(bytes([numberofthreads]))
	myFile.close()

	#creating threads and dividing the content over the multiple threads
	bytesperthread = math.ceil(int(fields['content-length']) / numberofthreads)
	print("Creating threads")
	threads = [None]*numberofthreads
	sockets = [None]*numberofthreads
	#for checking if all the threads have fetched their required data
	dataperthread = [None]*numberofthreads
	metric = [None] * numberofthreads
	#current thread data length used for metric presentation
	currentdataperthread = [None] * numberofthreads
	check = 0
	filecontent = b''
	for i in range(numberofthreads):
		threadLog = (dest + str(i) + '_' + logFile.split('.')[0] + '_Thread')
		begin = i * bytesperthread
		end = (begin + bytesperthread - 1)
		if(i == numberofthreads - 1):
			end=int(fields['content-length']) - 1
		filemode = "wb"
		#data per thread to check if the file should be created or not
		dataperthread[i] = end - begin + 1
		#checking if resume is true, resuming file.
		if(resume):
			filemode = "ab"
			begin += (os.stat(threadLog).st_size)
			if(begin - 1 == end):
				print("Thread complete")
				threads[i] = threading.Thread()
			else:
				print("Thread:" , i , " Range: " , begin  ,"-" , end)
				sockets[i] = socket(AF_INET,SOCK_STREAM)
				threads[i] = myThread(i ,host, faddress , begin , end , sockets[i] , threadLog)
		else:
			print("Thread:" , i , " Range: " , begin  ,"-" , end)
			sockets[i] = socket(AF_INET,SOCK_STREAM)
			threads[i] = myThread(i ,host, faddress , begin , end , sockets[i] , threadLog)
			open(threadLog , filemode)
		#current data assigned to the thread
		currentdataperthread[i] = end - begin + 1

	#starting threads all at once	
	for thread in threads:
		thread.start()

	#creating metric thread
	metricsThreadTotal = threading.Thread(target=totalReport, args=(args.interval,), daemon=True)
	metricsThreadTotal.start()

	#waiting for the threads to end
	for thread in threads:
		thread.join()

	#checnking if all the threads are available
	for i in range(numberofthreads):
		threadLog = (dest + str(i) + '_' + logFile.split('.')[0] + '_Thread')
		if(os.stat(threadLog).st_size == dataperthread[i]):
			check+=1

	#creting the final by merging all the thread files and removing the temperary files.
	if(check == numberofthreads):
		finalFile = open(fileaddress , 'ab')
		for i in range(numberofthreads):
			threadLog = (dest + str(i) + '_' + logFile.split('.')[0] + '_Thread')
			with open(threadLog, "rb") as myFile:
				finalFile.write(myFile.read())
			myFile.close()
			os.remove(threadLog)
		os.remove(dest + logFile + "_ThreadInfo")
		print("File complete!")
	else:
		print("File incomplete, please resume.")
	
#thread class for handling the request
class myThread (threading.Thread):
	def __init__(self, tid,host, faddress, begin, end, clientSocket, threadLog):
		threading.Thread.__init__(self)
		self.tid = tid
		self.host = host
		self.faddress = faddress
		self.begin = begin
		self.end = end
		self.clientSocket = clientSocket
		self.threadLog = threadLog
	def run(self):
		send_request(self.tid ,self.host, self.faddress, self.begin, self.end, self.clientSocket, self.threadLog)

#Getting data for each thread
def send_request(tid ,host, faddress, begin, end, clientSocket, threadLog):
	# print("Connecting to host: " , host , portNumber)
	global numberofthreads, metric
	# print("This is number of threads: " , numberofthreads)
	if tid != (numberofthreads - 1):
		rangeBytes = 'bytes={}-{}'.format(begin,end)
	else:
		rangeBytes = 'bytes={}-'.format(begin)

	#connecting to the server, and sending the HTTP GET request.
	clientSocket.connect((host , portNumber))
	clientSocket.sendall(b'GET %b HTTP/1.1\r\nHOST: %b \r\nRange: %b \r\n\r\n'  %(bytes(faddress , 'utf-8'), bytes(host , 'utf-8'), bytes(rangeBytes, 'utf-8')))
	print("request sent for thread: ", tid , '\n')
	
	startTime = time.clock()
	data = clientSocket.recv(buff_size)
	endTime = time.clock()
	#splitting the first response into header fields, data, and status
	status , fields , threadcontent = getHeaderFeildsAndContent(data)
	metric[tid] = [(endTime - startTime) , len(threadcontent)]
	#opening current thread log for inserting data
	with open(threadLog , "ab") as myFile:
		myFile.write(threadcontent)
	myFile.close()
	#checking if the address is valid
	if(status == 'HTTP/1.1 200 OK' or status == 'HTTP/1.1 206 Partial Content'):
		#getting content length from the header & the type of file for each thread
		contentLength = int(fields['content-length'])
		#getting data, till the data is equal to the content length or there is no more data. A 15 second safety timeout is added for delays.
		while select.select([clientSocket], [], [], 15)[0]:
			startTime = time.clock()
			data = clientSocket.recv(buff_size)
			if not data: break
			#appending the content to aach thread log file.
			with open(threadLog, "ab") as myFile:
				myFile.write(data)
			myFile.close()
			#storing time and length of content downloaded.
			endTime = time.clock()
			metric[tid][0] += (endTime - startTime)
			metric[tid][1] += len(data)
			#ending the loop when complete data is received.
			if(int(contentLength) == int(os.stat(threadLog).st_size)): break	
	else:
		print("Status: " , status)	
	#closing socket.
	clientSocket.close()

#Metric reporting
def totalReport(sleepTime):
	# Prints the total download and speed
	global metric, numberofthreads, currentdataperthread
	#the total data that is to be downloaded
	absoluteData = 0
	for datalength in currentdataperthread:
		absoluteData+=datalength
	absoluteData = absoluteData / 1024
	#for the thread to keep on working untill the main thread finishes.
	while True:
		totalTime = 0.0
		totalData = 0
		for threadNumber in range(numberofthreads):
			if(metric[threadNumber] != None):
				dtime = metric[threadNumber][0]
				data = metric[threadNumber][1] / 1024
				totalTime += dtime
				totalData += data
				if(dtime != 0.0):
					speed = data / dtime
				else:
					totalData+=data
					speed = 0
				#if threads data is complete
				if(metric[threadNumber][1] != currentdataperthread[threadNumber]):
					str = "Connection {}: {}/{}, download speed: {} kb/s" \
					.format(threadNumber, data, currentdataperthread[threadNumber] / 1024, speed)
					print(str,'\n')
				else:
					str = "Connection {}: , Completed" \
					.format(threadNumber)
					print(str,'\n')
		#if all the data is complete
		if(totalTime != 0.0 and totalData != absoluteData):
			str = "Total: {}/{}, download speed: {} kb/s" \
			.format(totalData, absoluteData, totalData / totalTime)
			print(str,'\n')
			print("Next iterval\n")
		else:
			print("Download Completed.")
		#putting the thread to sleep for the time interval
		time.sleep(sleepTime)

#main()
if __name__ == '__main__':
	#getting url and splitting it into separate fields
	url = args.sourceaddress
	host , faddress , fname = urlFields(url)
	print("Host: " , host , " Address: " , faddress , " Name: " , fname)
	#converting fname to valid file name
	fname = format_filename(fname)
	#getting destination address from the arguments
	dest = args.destinationaddress
	if(dest == '.'):
		dest = ''

	#connection to get HEADER of requested page to check whether the page is correct and what kind of request can be handled.
	s = socket(AF_INET, SOCK_STREAM)
	s.connect((host , portNumber))
	#sending header request
	s.sendall(b'HEAD %b HTTP/1.1\r\nHOST: %b \r\n\r\n'  %(bytes(faddress , 'utf-8') , bytes(host , 'utf-8')))
	print("Request Sent \n")
	data = s.recv(buff_size)
	status ,fields , content = getHeaderFeildsAndContent(data)
	ftype = getFileType(fields)
	#Creating file address
	fileaddress = dest + fname + '.' + ftype
	logFile = fname

	#proceeding only if the address is a valid http address
	print("HEADER: " , status)
	if(status == 'HTTP/1.1 200 OK' or status == 'HTTP/1.1 206 Partial Content'):
		print("Valid Request")

		#If resume is called, checking if the file exists and continuing from the part left.
		if(args.resume):
			print("Checking resume")
			if(os.path.isfile(fileaddress)):
				print("File exists")
				print("Number of bytes: " , os.stat(fileaddress).st_size)
				if(int(os.stat(fileaddress).st_size) == int(fields['content-length'])):
					print("Files is complete.")
					exit(0)
				else:
					#getting number of threads from the thread info file.
					print('Resuming Download')
					with open(dest + logFile + "_ThreadInfo" , "rb") as myFile:
						numberofthreads = int.from_bytes(myFile.read(), byteorder='little')
					myFile.close()
					print(numberofthreads)
					processRequest(numberofthreads, dest ,logFile, fileaddress, True)
					exit(0)

			else:
				print("File doesn't exist")

		#if file doesnt exist
		for field in fields.keys():
			print(field, " : " , fields[field])
		print("\n\n")
		numberofthreads = args.nthreads
		typeofrequest = checkThreadRequest(fields)

 		#checking if the request can be handled over multiple connections or not.
		if(typeofrequest == 1):
			open(fileaddress , 'wb')
			print('request will be handled over multiple connections')
			processRequest(numberofthreads, dest, logFile , fileaddress, False)
		elif(typeofrequest == 2):
			open(fileaddress , 'wb')
			numberofthreads = 1
			print('request will be handled over a Single connection')
			processRequest(numberofthreads, dest, logFile, fileaddress, False)
		else:
			print("Invalid Request")

	else:
		print("Invalid Request")

