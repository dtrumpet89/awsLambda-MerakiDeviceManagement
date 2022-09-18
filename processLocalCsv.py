import argparse, csv
from mLogger import mLog
from lambda_s3Trigger import lambdaFunction as lfS3
from lambda_sqsTrigger import lambdaFunction as lfSqs

deviceInfo: dict = {}
deviceWan: dict = {}


def parseCsvData(csvDict) -> None:

    for r in csvDict:
        mLog.mLog.debug(r)
        if 'deviceSerial' in r.keys():
            mLog.mLog.debug("Found Serial Number: {}".format(r['deviceSerial']))

            devSerial = None
            devSerial = validateMerakiSerial(r['deviceSerial'])
            if devSerial:

                tmpDevice = lfS3.parseDeviceInfo(r, devSerial)
                if tmpDevice:
                    deviceInfo[devSerial] = tmpDevice

                tmpWanDevice = lfS3.parseDeviceWan(r, devSerial)
                if tmpWanDevice:
                    deviceWan[devSerial] = tmpWanDevice

    lfSqs.deviceInfo = deviceInfo
    lfSqs.deviceWan = deviceWan

    if deviceInfo or deviceWan:
        lfSqs.headers['X-Cisco-Meraki-API-Key'] = apiKey
        lfSqs.processDevices()


def main():

    csvFile = None
    csvContent = None

    parser = argparser.ArgumentParser(description="Process local csv file to update Meraki")

    parser.add_argument(
        "-f", "--csvFile",
        type = str,
        help = "CSV file",
        required = True
    )

    parser.add_argument(
        "-a", "--apiKey",
        type = str,
        help = "API Key",
        required = False
    )

    args = parser.parser_args()

    if args.csvFile:
        csvFile = args.csvFile

    if args.apiKey:
        apiKey = args.apiKey

    try:
        with open(csvFile, 'r') as f:
            csvContent = f.read()
    except e:
        print(e)

    ''' Process content from CSV file '''
    lfS3.parseCsvData(csvContent.splitlines())



if __name__ == '__main__':
    main()
