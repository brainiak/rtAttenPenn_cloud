'''RtAttenClient - client logic for rtAtten experiment'''
import os
import time
import logging
import numpy as np  # type: ignore
import rtfMRI.utils as utils
from ..RtfMRIClient import RtfMRIClient, validateRunCfg
from ..MsgTypes import MsgEvent
from ..StructDict import StructDict, copy_toplevel
from ..ReadDicom import readDicom, applyMask
from ..utils import dateStr30
from ..Errors import InvocationError, ValidationError
from .PatternsDesign2Config import createRunConfig
from .RtAttenModel import getBlkGrpFilename, getModelFilename, getSubjectDayDir
from watchdog.events import PatternMatchingEventHandler  # type: ignore
from watchdog.observers import Observer  # type: ignore
from queue import Queue


class RtAttenClient(RtfMRIClient):
    def __init__(self):
        super().__init__()
        self.dirs = StructDict()
        self.prevData = None
        self.observer = None
        self.fileNotifyHandler = None
        self.fileNotifyQ = Queue()  # type: None

    def __del__(self):
        if self.observer is not None:
            self.observer.stop()
        super().__del__()

    def initSession(self, cfg):
        if cfg.session.sessionId is None or cfg.session.sessionId == '':
            cfg.session.sessionId = dateStr30(time.localtime())

        # Set Directories
        subjectDayDir = getSubjectDayDir(cfg.session.subjectNum, cfg.session.subjectDay)
        self.dirs.dataDir = os.path.join(cfg.session.dataDir, subjectDayDir)
        self.dirs.imgDir = cfg.session.imgDir
        if not os.path.exists(self.dirs.imgDir):
            os.makedirs(self.dirs.imgDir)
        print("fMRI files being read from: {}".format(self.dirs.imgDir))
        self.initFileNotifier(self.dirs.imgDir, cfg.session.watchFilePattern)

        # Load ROI mask - an array with 1s indicating the voxels of interest
        maskFileName = 'mask_' + str(cfg.session.subjectNum) + '_' + str(cfg.session.subjectDay) + '.mat'
        maskFileName = os.path.join(self.dirs.dataDir, maskFileName)
        temp = utils.loadMatFile(maskFileName)
        roi = temp.mask
        assert type(roi) == np.ndarray
        # find indices of non-zero elements in roi in row-major order but sorted by col-major order
        cfg.session.roiInds = utils.find(roi)
        cfg.session.roiDims = roi.shape
        cfg.session.nVoxels = cfg.session.roiInds.size
        print("Using mask {}".format(maskFileName))

        super().initSession(cfg)

    def doRuns(self):
        # Process each run
        for runId in self.cfg.session.Runs:
            self.runRun(runId)
            self.retrieveRunFiles(runId)

    def runRun(self, runId, scanNum=-1):
        run = createRunConfig(self.cfg.session, runId)
        validateRunCfg(run)
        self.id_fields.runId = run.runId
        if scanNum >= 0:
            run.scanNum = scanNum

        if self.cfg.session.rtData == 1:
            # Check if images already exist and warn and ask to continue
            firstFileName = self.getDicomFileName(run.scanNum, 1)
            if os.path.exists(firstFileName):
                resp = input('Files with this scan number already exist. Do you want to continue? Y/N [N]: ')
                if resp.upper() != 'Y':
                    return
        else:
            idx = runId - 1
            if self.cfg.session.validate:
                run.validationModel = os.path.join(self.dirs.dataDir, self.cfg.session.validationModels[idx])
            if self.cfg.session.replayMatFileMode == 1:
                run.replayFile = os.path.join(self.dirs.dataDir, self.cfg.session.replayMatFiles[idx])

        # Setup output directory and output file
        runDataDir = os.path.join(self.dirs.dataDir, 'run' + str(run.runId))
        if not os.path.exists(runDataDir):
            os.makedirs(runDataDir)
        outputFile = open(os.path.join(runDataDir, 'fileprocessing_py.txt'), 'w+')

        # ** Experimental Parameters ** #
        run.seed = time.time()
        if run.runId > 1:
            run.rtfeedback = 1
        else:
            run.rtfeedback = 0

        runCfg = copy_toplevel(run)
        reply = self.sendCmdExpectSuccess(MsgEvent.StartRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputFile)

        if self.cfg.session.replayMatFileMode == 1:
            # load previous patterns data for this run
            p = utils.loadMatFile(run.replayFile)
            run.replay_data = p.patterns.raw

        # Begin BlockGroups (phases)
        for blockGroup in run.blockGroups:
            self.id_fields.blkGrpId = blockGroup.blkGrpId
            blockGroupCfg = copy_toplevel(blockGroup)
            reply = self.sendCmdExpectSuccess(MsgEvent.StartBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputFile)
            for block in blockGroup.blocks:
                self.id_fields.blockId = block.blockId
                blockCfg = copy_toplevel(block)
                reply = self.sendCmdExpectSuccess(MsgEvent.StartBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputFile)
                for TR in block.TRs:
                    self.id_fields.trId = TR.trId
                    if self.cfg.session.rtData == 1:
                        # Assuming the output file volumes are still 1's based
                        fileNum = TR.vol + run.disdaqs // run.TRTime
                        trVolumeData = self.getNextTRData(run, fileNum)
                        TR.data = applyMask(trVolumeData, self.cfg.session.roiInds)
                    else:
                        # TR.vol is 1's based to match matlab, so we want vol-1 for zero based indexing
                        TR.data = run.replay_data[TR.vol-1]
                    reply = self.sendCmdExpectSuccess(MsgEvent.TRData, TR)
                    outputReplyLines(reply.fields.outputlns, outputFile)
                    outputPredictionFile(reply.fields.predict, runDataDir)
                del self.id_fields.trId
                reply = self.sendCmdExpectSuccess(MsgEvent.EndBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputFile)
            del self.id_fields.blockId
            reply = self.sendCmdExpectSuccess(MsgEvent.EndBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputFile)
            # self.retrieveBlkGrp(self.id_fields.sessionId, self.id_fields.runId, self.id_fields.blkGrpId)
        del self.id_fields.blkGrpId
        # Train the model for this Run
        trainCfg = StructDict()
        if run.runId == 1:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 1}, {'run': 1, 'phase': 2}]
        elif run.runId == 2:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 2}, {'run': 2, 'phase': 1}]
        else:
            trainCfg.blkGrpRefs = [{'run': run.runId-1, 'phase': 1}, {'run': run.runId, 'phase': 1}]
        reply = self.sendCmdExpectSuccess(MsgEvent.TrainModel, trainCfg)
        outputReplyLines(reply.fields.outputlns, outputFile)
        reply = self.sendCmdExpectSuccess(MsgEvent.EndRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputFile)
        del self.id_fields.runId

    def retrieveRunFiles(self, runId):
        blkGrp1_filename = getBlkGrpFilename(self.id_fields.sessionId, runId, 1)
        self.retrieveFile(blkGrp1_filename)
        blkGrp2_filename = getBlkGrpFilename(self.id_fields.sessionId, runId, 2)
        self.retrieveFile(blkGrp2_filename)
        model_filename = getModelFilename(self.id_fields.sessionId, runId)
        self.retrieveFile(model_filename)

    def retrieveFile(self, filename):
        print("Retrieving data for {}... ".format(filename), end='')
        fileInfo = StructDict()
        fileInfo.subjectNum = self.id_fields.subjectNum
        fileInfo.subjectDay = self.id_fields.subjectDay
        fileInfo.filename = filename
        stime = time.time()
        reply = self.sendCmdExpectSuccess(MsgEvent.RetrieveData, fileInfo)
        print("took {} secs".format(time.time() - stime))
        writeFile(os.path.join(self.dirs.dataDir, filename), reply.data)

    def getNextTRData(self, run, fileNum):
        specificFileName = self.getDicomFileName(run.scanNum, fileNum)
        fileExists = os.path.exists(specificFileName)
        if not fileExists and self.observer is None:
            raise FileNotFoundError("No fileNotifier and dicom file not found %s" % (specificFileName))
        while not fileExists:
            # look for file creation event
            event, ts = self.fileNotifyQ.get()
            if event.src_path == specificFileName:
                fileExists = True
        # wait for the full file to be written, wait at most 200 ms
        fileSize = 0
        totalWait = 0.0
        waitIncrement = 0.01
        while fileSize < self.cfg.session.minExpectedDicomSize and totalWait < 0.2:
            fileSize = os.path.getsize(specificFileName)
            time.sleep(waitIncrement)
            totalWait += waitIncrement
        trVol, _ = readDicom(specificFileName, self.cfg.session.sliceDim)
        return trVol

    def getDicomFileName(self, scanNum, fileNum):
        if scanNum < 0:
            raise ValidationError("ScanNumber not supplied of invalid {}".format(scanNum))
        scanNumStr = str(scanNum).zfill(2)
        fileNumStr = str(fileNum).zfill(3)
        if self.cfg.session.dicomNamePattern is None:
            raise InvocationError("Missing config settings dicomNamePattern")
        fileName = self.cfg.session.dicomNamePattern.format(scanNumStr, fileNumStr)
        fullFileName = os.path.join(self.dirs.imgDir, fileName)
        return fullFileName

    def initFileNotifier(self, imgDir, filePattern):
        if self.observer is not None:
            self.observer.stop()
        self.observer = Observer()
        if filePattern is None or filePattern == '':
            filePattern = '*'
        self.fileNotifyHandler = FileNotifyHandler(self.fileNotifyQ, [filePattern])
        self.observer.schedule(self.fileNotifyHandler, imgDir, recursive=False)
        self.observer.start()


class FileNotifyHandler(PatternMatchingEventHandler):  # type: ignore
    def __init__(self, q, patterns):
        super().__init__(patterns=patterns)
        self.q = q

    def on_created(self, event):
        self.q.put((event, time.time()))


def outputReplyLines(lines, filehandle):
    if lines is not None:
        for line in lines:
            print(line)
            filehandle.write(line + '\n')


def outputPredictionFile(predict, runDataDir):
    if predict is None or predict.vol is None:
        return
    filename = os.path.join(runDataDir, 'vol_' + str(predict.vol) + '_py')
    with open(filename, 'w+') as volFile:
        volFile.write(str(predict.catsep))


def writeFile(filename, data):
    with open(filename, 'wb') as fh:
        bytesWritten = fh.write(data)
        if bytesWritten != len(data):
            raise InterruptedError("Write file %s wrote %d of %d bytes" % (filename, bytesWritten, len(data)))