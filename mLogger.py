import logging

logFile = "meraki.log"

mLog = logging.getLogger(__name__)
mLog.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

fh = logging.FileHandler(logFile)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
mLog.addHandler(fh)

''' Create StreamHandler to output to console '''
ch = logging.StreamHandler()

ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
mLog.addHandler(ch)
