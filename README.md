# HTTP-Download-Manager
A multi connection HTTP download manager with resume.

Arguments:

python client.py  --h

usage: client.py [-h] -n NTHREADS -i INTERVAL -c TLP -f SOURCEADDRESS -o
                 DESTINATIONADDRESS [-r]
                 
  -h, --help            show this help message and exit
  
  -n NTHREADS, --nthreads NTHREADS
                        Number of threads for the connection
                        
  -i INTERVAL, --interval INTERVAL
                        Time interval of metric reporting
                        
  -c TLP, --tlp TLP     TCP or UDP
  
  -f SOURCEADDRESS, --sourceaddress SOURCEADDRESS
                        File location on the web
                        
  -o DESTINATIONADDRESS, --destinationaddress DESTINATIONADDRESS
                        File destination address
                        
  -r, --resume          Resume download
  
