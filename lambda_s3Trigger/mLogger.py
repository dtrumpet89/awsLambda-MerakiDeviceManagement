import logging
import os

mLog = logging.getLogger(__name__)
mLog.setLevel(logging.DEBUG)


if "LEVEL" in os.environ:
    if os.environ['LEVEL'] == 'INFO':
        mLog.setLevel(logging.INFO)
