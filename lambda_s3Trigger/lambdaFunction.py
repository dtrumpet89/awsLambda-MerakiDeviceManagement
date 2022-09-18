import csv, json, re, os
import urllib.parse
import mLogger as mLog
from datetime import datetime
from base64 import b64decode

deviceInfo: dict = {}
deviceWan: dict = {}

deviceInfoCsvFields: list = [ 'deviceSerial', 'deviceName', 'deviceTags', 'deviceNotes', 'deviceAddress', 'deviceLatitude', 'deviceLongitude' ]
deviceWanCsvFields: list = [ 'w1Enabled', 'w1Static', 'w1StaticIp', 'w1Subnet', 'w1Gateway', 'w1Dns', 'w1Vlan', 'w2Enabled', 'w2Static', 'w2StaticIp', 'w2Subnet', 'w2Gateway', 'w2Dns', 'w2Vlan' ]
deviceInfoRestFields: dict = { "serial": None, "name": None, "tags": None, "notes": None, "address": None, "lat": None, "lng": None }
deviceWanRestFields: dict = {
                            "wan1": { "wanEnabled": None, "usingStaticIp": None, "staticIp": None, "staticSubnetMask": None, "staticGatewayIp": None, "staticDns": None, "vlan": None },
                            "wan2": { "wanEnabled": None, "usingStaticIp": None, "staticIp": None, "staticSubnetMask": None, "staticGatewayIp": None, "staticDns": None, "vlan": None }
                            }

''' Check for boolean values '''
def str2bool(v) -> bool:
    if isinstance(v, bool):
        return v

    if v.lower() in ('yes', 'true','y','1'):
        return True
    elif v.lower() in ('no','false','f','n','0'):
        return False
    else:
        return None

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

def cleanDict(d) -> dict:
    for key, value in dict(d).items():

        if key is dict:
            for k, v in d[key]:
                if v is None:
                    del d[key][k]

        if value is None:
            del d[key]

    return d

def validateWanInfo(wan) -> dict:

    if "wanEnabled" in wan.keys():
        boolEnabled = str2bool(wan["wanEnabled"])
        if boolEnabled:
            wan["wanEnabled"] = "enabled"
        elif not boolEnabled:
            wan["wanEnabled"] = "disabled"
        else:
            wan["wanEnabled"] = "not configured"

    else:
        wan["wanEnabled"] = "not configured"

    # Check if port is static or dhcp
    if "usingStaticIp" in wan.keys():
        if len(wan["usingStaticIp"]) > 1:
            wan["usingStaticIp"] = str2bool(wan["usingStaticIp"])
        else:
            wan["usingStaticIp"] = False
    else:
        wan["usingStaticIp"] = False


    if "vlan" in wan.keys():
        if wan['vlan'].isdigit():
            vlan = int(wan['vlan'])

            if vlan > 0 and vlan < 4096:
                wan['vlan'] = vlan
            else:
                del wan['vlan']
        else:
            del wan['vlan']

    if len(wan) >= 1:
        if 'wanEnabled' not in wan.keys():
            wan['wanEnabled'] = "not configured"
        if 'usingStaticIp' not in wan.keys():
            wan['usingStaticIp'] = False

    mLog.mLog.debug(wan)

    return wan


def validateField(fieldName, r) -> str:
    if r.get(fieldName):
        if len(r[fieldName]) >= 1:
            return r[fieldName]
    return None

def parseWanAttributes(dSerial, r):
    dfCount = 0

    dfHalf = int(len(deviceWanCsvFields)/2-1)

    if dfCount <= dfHalf:

        for i in deviceWan[dSerial]["wan1"].keys():
            deviceWan[dSerial]["wan1"][i] = validateField(deviceWanCsvFields[dfCount], r)

            ''' Split DNS addresses into list '''
            if i == "staticDns" and deviceWan[dSerial]["wan1"][i] is not None:
                deviceWan[dSerial]["wan1"][i] = deviceWan[dSerial]["wan1"][i].split(',')

            dfCount += 1
    else:
        for i in deviceWan[dSerial]['wan2'].keys():
            deviceWan[dSerial]['wan2'][i] = validateField(deviceWanCsvFields[dfCount], r)

            ''' Split DNS addresses into list '''
            if i == "staticDns" and deviceWan[dSerial]['wan2'][i] is not None:
                deviceWan[dSerial]['wan2'][i] = deviceWan[dSerial]['wan2'][i].split(',')

            dfCount += 1
    mLog.mLog.debug(deviceWan[dSerial])

def parseDeviceInfo(row, devSerial) -> Dict:

    deviceInfo: dict = {}


    ''' Device Info Fields '''
    deviceInfo[devSerial] = deviceInfoRestFields.copy()
    deviceInfo[devSerial]['serial'] = devSerial

    dfCount: int = 0
    for i in deviceInfo[devSerial]:
        if i == 'serial':
            dfCount += 1
        else:
            deviceInfo[devSerial][i] = validateField(deviceInfoCsvFields[dfCount], row)
            dfCount += 1

    deviceInfo[devSerial] = cleanDict(deviceInfo[devSerial])

    if "tags" in deviceInfo[devSerial].keys():
        deviceInfo[devSerial]['tags'] = deviceInfo[devSerial]['tags'].split(',')

    # Delete if only one field (serial) or no fields exist
    if len(deviceInfo[devSerial]) <= 1:
        del deviceInfo[devSerial]
        mLog.mLog.debug("No Device Info fields to update for serial: {}".format(devSerial))
        return
    else:
        tmpDevice = None
        tmpDevice = {}
        tmpDevice[devSerial] = deviceInfo[devSerial]
        mLog.mLog.debug(tmpDevice[devSerial])
        return tmpDevice

def parseDeviceWan(row, devSerial) -> Dict:

    deviceWan: dict = {}

    ''' Device Wan Fields '''
    deviceWan[devSerial] = deviceWanRestFields.copy()
    deviceWan[devSerial]['wan1'] = deviceWanRestFields['wan1'].copy()
    deviceWan[devSerial]['wan2'] = deviceWanRestFields['wan2'].copy()

    mLog.mLog.debug("Set default WAN Fields")
    parseWanAttributes(devSerial, row)

    deviceWan[devSerial]['wan1'] = cleanDict(deviceWan[devSerial]['wan1'])
    deviceWan[devSerial]['wan2'] = cleanDict(deviceWan[devSerial]['wan2'])

    deviceWan[devSerial] = cleanDict(deviceWan[devSerial])

    if not bool(deviceWan[devSerial]['wan1']):
        del deviceWan[devSerial]['wan1']
    else:
        deviceWan[devSerial]['wan1'] = validateWanInfo(deviceWan[devSerial]['wan1'])

    if not bool(deviceWan[devSerial]['wan2']):
        del deviceWan[devSerial]['wan2']
    else:
        deviceWan[devSerial]['wan2'] = validateWanInfo(deviceWan[devSerial]['wan2'])

    if len(deviceWan[devSerial]) == 0:
        del deviceWan[devSerial]
        mLog.mLog.debug("No Device Wan fields to update for serial: {}".format(devSerial))
        return None
    else:
        tmpWanDevice = None
        tmpWanDevice = {}
        tmpWanDevice[devSerial] = deviceWan[devSerial]

        mLog.mLog.debug(json.dumps(tmpWanDevice))
        return tmpWanDevice


def parseCsvData(csvDict) -> None:

    for r in csvDict:
        mLog.mLog.debug(r)
        if 'deviceSerial' in r.keys():
            mLog.mLog.debug("Found Serial Number: {}".format(r['deviceSerial']))

            devSerial = None
            devSerial = validateMerakiSerial(r['deviceSerial'])
            if devSerial:

                tmpDevice = parseDeviceInfo(r, devSerial)
                if tmpDevice:
                    mLog.mLog.debug("Sending message to SQS")
                    sqs.send_message(QueueUrl=CNF_QUEUE, MessageBody=json.dumps(tmpDevice), MessageGroupId='DeviceWan')

                tmpWanDevice = parseDeviceWan(r, devSerial)
                if tmpWanDevice:
                    mLog.mLog.debug("Sending message to SQS")
                    sqs.send_message(QueueUrl=CNF_QUEUE, MessageBody=json.dumps(tmpWanDevice), MessageGroupId='DeviceWan')

''' Main Lambda Handler Function '''
def lambda_handler(event, context):

    ''' Enviroment Variables '''
    REGION = os.environ.get('AWS_REGION') or 'us-east-1'
    CNF_QUEUE = os.environ.get('CNF_QUEUE')
    CNF_TOPIC = os.environ.get('CNF_TOPIC')

    import boto3
    s3 = boto3.client('s3')
    sqs = boto3.client('sqs', region_name=REGION)

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    try:
        csvFile = s3.get_object(Bucket=bucket, Key=key)
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e

    if csvFile['ContentType'] == 'text/csv':
        csvData = csvFile['Body'].read().decode('utf-8-sig').splitlines()
        if csvData:
            csvRows = csv.DictReader(csvData)
            parseCsvData(csvRows)
        else:
            mLog.mLog.error("Unable to process file contents")
            return 0
    else:
        mLog.mLog.error("File Content-Type is not CSV")
        return 0

    ''' Move CSV to Completed '''
    tStmp = datetime.utcnow().strftime("%Y%m%d_%H%M%S-")
    if '/' in key:
        splitKey = key.split('/')
        newKey = tStmp + splitKey[len(splitKey)-1]
    else:
        newKey = tStmp + key

    copySource = { "Bucket": bucket, "Key": key }
    copyDst = "merakiConfigCompleted/" + newKey
    mLog.mLog.debug(copyDst)

    s3.copy_object(Bucket=bucket, CopySource=copySource, Key=copyDst)
    s3.delete_object(Bucket=bucket, Key=key)

    return 0
