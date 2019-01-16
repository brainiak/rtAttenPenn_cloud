import pytest
import os
import threading
import time
import json
import logging
from rtfMRI.fileWatcher import WebSocketFileWatcher
from rtfMRI.WebInterface import Web
from rtfMRI.Errors import RequestError
from rtfMRI.utils import installLoggers


testDir = os.path.dirname(__file__)


@pytest.fixture(scope="module")
def dicomTestFilename():  # type: ignore
    return os.path.join(testDir, 'test_input/001_000001_000001.dcm')


class TestFileWatcher:
    webThread = None
    fileThread = None
    pingCount = 0

    def setup_class(cls):
        installLoggers(logging.DEBUG, logging.DEBUG, filename='logs/tests.log')
        # Start a webInterface thread running
        webKwArgs = {'index': 'rtAtten/html/index.html', 'port': 8921}
        cls.webThread = threading.Thread(name='webThread', target=Web.start, kwargs=webKwArgs)
        cls.webThread.setDaemon(True)
        cls.webThread.start()
        time.sleep(1)

        # Start a fileWatcher thread running
        cls.fileThread = threading.Thread(
            name='fileThread',
            target=WebSocketFileWatcher.runFileWatcher,
            args=('localhost:8921',),
            kwargs={'retryInterval': 0.5, 'allowedDirs':['/tmp', testDir], 'allowedTypes':['.dcm', '.mat']}
        )
        cls.fileThread.setDaemon(True)
        cls.fileThread.start()
        time.sleep(1)

    def teardown_class(cls):
        time.sleep(1)
        pass

    def test_ping(cls):
        print("test_ping")
        global pingCallbackEvent
        # Send a ping request from webInterface to fileWatcher
        assert len(Web.wsDataConns) > 0
        cmd = {'cmd': 'ping'}
        Web.sendDataMessage(cmd, timeout=2)

    def test_validateRequestedFile(cls):
        print("test_validateRequestedFile")
        res = WebSocketFileWatcher.validateRequestedFile('/tmp/data', None)
        assert res is True

        res = WebSocketFileWatcher.validateRequestedFile('/tmp/data', 'file.dcm')
        assert res is True

        res = WebSocketFileWatcher.validateRequestedFile('/tmp/data', 'file.not')
        assert res is False

        res = WebSocketFileWatcher.validateRequestedFile('/sys/data', 'file.dcm')
        assert res is False

        res = WebSocketFileWatcher.validateRequestedFile(None, '/tmp/data/file.dcm')
        assert res is True

        res = WebSocketFileWatcher.validateRequestedFile(None, '/sys/data/file.dcm')
        assert res is False


    def test_getFile(cls, dicomTestFilename):
        print("test_getFile")
        global fileData
        assert len(Web.wsDataConns) > 0
        # Try to initialize file watcher with non-allowed directory
        try:
            Web.initWatch('/', '*', 0)
        except RequestError as error:
            # we expect an error because '/' directory not allowed
            assert True
        else:
            assert False

        # Initialize with allowed directory
        try:
            Web.initWatch(testDir, '*', 0)
        except RequestError as error:
            # we expect an error because '/' directory not allowed
            assert False

        with open(dicomTestFilename, 'rb') as fp:
            data = fp.read()
        webData, err = Web.watchFile(dicomTestFilename, asRawBytes=True)
        assert(data == webData and err is None)
        webData, err = Web.getFile(dicomTestFilename, asRawBytes=True)
        assert(data == webData and err is None)
        webData, err = Web.getNewestFile(dicomTestFilename, asRawBytes=True)
        assert(data == webData and err is None)

        # Try to get a non-allowed file
        webData, err = Web.getFile('/tmp/file.nope')
        assert(err is not None and webData is None)

        # try from a non-allowed directory
        webData, err = Web.getFile('/nope/file.dcm')
        assert(err is not None and webData is None)
