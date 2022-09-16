import csv, json, re, os, requests
import urllib.parse
import mLogger as mLog
from base64 import b64decode
from datetime import datetime

import boto3


REGION = os.environ.get('AWS_REGION') or 'us-east-1'

sqs = boto3.client("sqs", region_name=REGION)

merakiUrl = "https://api.meraki.com/api/v1/devices/"

headers = {
            'X-Cisco-Meraki-API-Key': '',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

deviceInfo: dict = {}
deviceWan: dict = {}

''' Retrieve Encrypted API key and decrypt '''
def getApiKey():
    ENCRYPTED = os.environ['MERAKI_API_KEY']
    # Decrypt code should run once and variables stored outside of the function
    # handler so that these are decrypted once per container
    DECRYPTED = boto3.client('kms').decrypt(
        CiphertextBlob=b64decode(ENCRYPTED),
        EncryptionContext={'LambdaFunctionName': os.environ['AWS_LAMBDA_FUNCTION_NAME']}
    )['Plaintext'].decode('utf-8')

    return DECRYPTED

''' Validate Meraki Serial number '''
def validateMerakiSerial(devSerial) -> str:
    regMerakiSerial = re.compile(r'(\w\w\w\w-){2}(\w\w\w\w)')
    matSerial = regMerakiSerial.search(devSerial)

    # Check if Serial was found
    if not matSerial == None:
        return matSerial.group().upper()
    else:
        print("No valid Meraki serial found")
        return ""

''' Meraki Update Functions '''
def processRequest(url, payload=None):

    requestsMade = 0

    try:
        if payload:
            r = requests.request('PUT', url, data=payload, headers=headers)
        else:
            r = requests.request('GET', url, headers=headers)

        requestsMade += 1

        if r.status_code == 200:
            if 'Content-Type' in r.headers:
                if 'json' in r.headers['Content-Type']:
                    return r.json()

        if r.status_code == 401:
            mLog.mLog.error("API Key not valid")
            mLog.mLog.error("Please ensure orginization API is enabled")
            SystemExit

        ''' Process request after received wait time has elapsed '''
        if r.status_code == 429:
            mLog.mLog.warn("Recieved Rate Limit")

            if "Retry-After" in r.headers:
                waitTime = int(r.headers["Retry-After"]) + 2
                mLog.mLog.warn("Waiting {} seconds to retry".format(waitTime))
                time.sleep(waitTime)

                if requestsMade < 4:
                    processRequest(url, payload=payload)
                else:
                    mLog.mLog.error("Giving up. Number of requests exceeded {} tries".format(requestsMade))
    except Exception as e:
        print(e)

def compareDevices(deviceSerial, currentDevice, uDev) -> dict:

    if uDev is None:
        return None

    d = {}
    d = uDev.copy()
    for k, v in uDev.items():
        if k in currentDevice:
            if v == currentDevice[k] and k != 'serial':
                del d[k]

    returnValue = 3

    if 'wan1' in d.keys():
        if len(d['wan1']) < 2:
            mLog.mLog.info(infoMsg)
            returnValue -= 1
    else:
        returnValue -= 1

    if 'wan2' in d.keys():
        if len(d['wan2']) < 2:
            mLog.mLog.info(infoMsg)
            returnValue -= 1
    else:
        returnValue -= 1

    if len(d) < 2:

        returnValue -= 1

    if returnValue:
        return d
    else:
        mLog.mLog.info(("{}: No attributes to update".format(deviceSerial)))
        return None

# Update Meraki Device
def updateDevice(url, device) -> None:

    payload = json.dumps(device, indent = 4)

    updatedDevice = processRequest(url=url, payload=payload)


def processDevices() -> None:

    ''' Process Device Info '''
    if deviceInfo:
        for d in deviceInfo:
            url = merakiUrl + d
            currentDeviceSettings = processRequest(url)
            mLog.mLog.debug(currentDeviceSettings)
            deviceInfo[d] = compareDevices(d, currentDeviceSettings, deviceInfo[d])
            if deviceInfo[d] is not None:
                mLog.mLog.info("{}: Updating".format(d))
                updateDevice(url, deviceInfo[d])

    ''' Process Device Wan Info '''
    if deviceWan:
        for w in deviceWan:
            url = merakiUrl + w + "/managementInterface"
            currentDeviceWanSettings = processRequest(url)
            mLog.mLog.debug(currentDeviceWanSettings)
            deviceWan[w] = compareDevices(w, currentDeviceWanSettings, deviceWan[w])
            if deviceWan[w] is not None:
                mLog.mLog.info("{}: Updating".format(w))
                updateDevice(url, deviceWan[w])

''' Main Lambda Handler Function '''
def lambda_handler(event, context):

    for message in event['Records']:

        message_body = json.loads(message["body"])
        mLog.mLog.debug("Processing message: {}".format(message_body))

        if message['attributes']['MessageGroupId'] == "DeviceInfo":
            for i in message_body:
                mLog.mLog.debug(message_body[i])
                deviceInfo[i] = message_body[i]

        if message['attributes']['MessageGroupId'] == "DeviceWan":
            for i in message_body:
                mLog.mLog.debug(message_body[i])
                deviceWan[i] = message_body[i]

    ''' Process Devices '''
    if len(deviceInfo) > 0 or len(deviceWan) > 0:
        mLog.mLog.debug("Processing Devices")

        headers['X-Cisco-Meraki-API-Key'] = getApiKey()

        if headers['X-Cisco-Meraki-API-Key']:
            mLog.mLog.debug("Retrieved API Key")
            processDevices()
    else:
        mLog.mLog.warn("Nothing to process")


    return 0
