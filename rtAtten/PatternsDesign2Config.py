"""Convert a Matlab patternsDesign file to a config file for rtfMRI"""
import os
import logging
import numpy as np  # type: ignore
from rtfMRI.StructDict import StructDict
from rtfMRI.utils import loadMatFile, findNewestFile
from rtfMRI.Errors import ValidationError


def getLocalPatternsFile(session, subjectDataDir, runId):
    if session.findNewestPatterns:
        # load the newest file patterns
        patternsFilename = findPatternsDesignFile(session, subjectDataDir, runId)
    else:
        idx = getRunIndex(session, runId)
        if idx >= 0 and len(session.patternsDesignFiles) > idx:
            patternsFilename = session.patternsDesignFiles[idx]
            patternsFilename = os.path.join(subjectDataDir, os.path.basename(patternsFilename))
        else:
            # either not enough runs specified or not enough patternsDesignFiles specified
            if idx < 0:
                raise ValidationError("Insufficient runs specified in config file session: "
                                      "run {} idx {}".format(runId, idx))
            else:
                raise ValidationError("Insufficient patternsDesignFiles specified in "
                                      "config file session for run {}".format(runId))
    # load and parse the pattensDesign file
    logging.info("Using Local Patterns file: %s", patternsFilename)
    patterns = loadMatFile(patternsFilename)
    return patterns, patternsFilename


def createRunConfig(session, patterns, runId, scanNum=-1):
    run = StructDict()
    run.runId = runId
    idx = getRunIndex(session, runId)
    if scanNum >= 0:
        run.scanNum = scanNum
    elif session.ScanNums is not None and idx >= 0 and len(session.ScanNums) > idx:
        run.scanNum = session.ScanNums[idx]
    else:
        run.scanNum = -1

    run.disdaqs = int(patterns.disdaqs)
    run.nBlocksPerPhase = int(patterns.nBlocksPerPhase)
    run.TRTime = int(patterns.TR)
    run.nTRs = int(patterns.nTRs)
    run.nTRsFix = int(patterns.nTRsFix)

    run.firstVolPhase1 = int(np.min(np.where(patterns.block.squeeze() == 1)))
    run.lastVolPhase1 = int(np.max(np.where(patterns.block.squeeze() == patterns.nBlocksPerPhase)))
    if run.lastVolPhase1 != patterns.lastVolPhase1-1:
        raise ValidationError("createRunConfig: calulated lastVolPhase1 is same as loaded from"
                              "patternsdesign {} {}".format(run.lastVolPhase1, patterns.lastVolPhase1))
    run.nVolsPhase1 = run.lastVolPhase1 - run.firstVolPhase1 + 1
    run.firstVolPhase2 = int(np.min(np.where(patterns.block.squeeze() == (patterns.nBlocksPerPhase+1))))
    if run.firstVolPhase2 != patterns.firstVolPhase2-1:
        raise ValidationError("createRunConfig: calulated firstVolPhase2 is same as loaded from "
                              "patternsdesign {} {}".format(run.firstVolPhase2, patterns.firstVolPhase2))
    run.lastVolPhase2 = int(np.max(np.where(patterns.type.squeeze() != 0)))
    run.nVolsPhase2 = run.lastVolPhase2 - run.firstVolPhase2 + 1

    sumRegressor = patterns.regressor[0, :] + patterns.regressor[1, :]
    run.firstTestTR = int(np.min(np.where(sumRegressor == 1)))

    run.nVols = patterns.block.shape[1]

    blockGroups = []

    blkGrp1 = createBlockGroupConfig(range(run.firstVolPhase2), patterns)
    blkGrp1.blkGrpId = 1
    blkGrp1.nTRs = run.firstVolPhase2
    blockGroups.append(blkGrp1)

    blkGrp2 = createBlockGroupConfig(range(run.firstVolPhase2, run.nVols), patterns)
    blkGrp2.blkGrpId = 2
    blkGrp2.nTRs = run.nVols - run.firstVolPhase2
    blockGroups.append(blkGrp2)

    run.blockGroups = blockGroups
    return run


def createBlockGroupConfig(tr_range, patterns):
    blkGrp = StructDict()
    blkGrp.blocks = []
    blkGrp.type = 0
    blkGrp.firstVol = tr_range[0]
    block = StructDict()
    blockNum = -1
    for iTR in tr_range:
        if patterns.block[0, iTR] > 0 and patterns.block[0, iTR] != blockNum:
            if blockNum >= 0:
                blkGrp.blocks.append(block)
            blockNum = int(patterns.block[0, iTR])
            block = StructDict()
            block.blockId = blockNum
            block.TRs = []
        tr = StructDict()
        tr.trId = iTR - blkGrp.firstVol
        tr.vol = iTR + 1
        tr.attCateg = int(patterns.attCateg[0, iTR])
        tr.stim = int(patterns.stim[0, iTR])
        tr.type = int(patterns.type[0, iTR])
        if tr.type != 0:
            if blkGrp.type == 0:
                blkGrp.type = tr.type
            if blkGrp.type != tr.type:
                raise ValidationError("createBlockGroupConfig: inconsistent TR types in block group")
        tr.regressor = [int(patterns.regressor[0, iTR]), int(patterns.regressor[1, iTR])]
        block.TRs.append(tr)
    if len(block.TRs) > 0:
        blkGrp.blocks.append(block)
    return blkGrp


def getPatternsFileRegex(session, dataDir, runId, addRunDir=False):
    filePattern = 'patternsdesign_' + str(runId) + '*.mat'
    if addRunDir:
        patternsFilename = os.path.join(dataDir, 'run'+str(runId), filePattern)
    else:
        patternsFilename = os.path.join(dataDir, filePattern)
    return patternsFilename


def findPatternsDesignFile(session, dataDir, runId):
    fullPathRegex = getPatternsFileRegex(session, dataDir, runId, addRunDir=True)
    baseDir, filePattern = os.path.split(fullPathRegex)
    pdesignFile = findNewestFile(baseDir, filePattern)
    if pdesignFile is not None and pdesignFile != '':
        return pdesignFile
    fullPathRegex = getPatternsFileRegex(session, dataDir, runId)
    pdesignFile = findNewestFile('', fullPathRegex)
    if pdesignFile is None or pdesignFile == '':
        raise FileNotFoundError("No files found matching {}".format(fullPathRegex))
    return pdesignFile


def getRunIndex(session, runId):
    if session.Runs is None:
        print("session config has no Runs value defined")
        return -1
    ids = [idx for (idx, run) in enumerate(session.Runs) if run == runId]
    if len(ids) == 0:
        print("Run {} not in Runs List".format(runId))
        return -1
    elif len(ids) > 1:
        print("Run {} declared multiple times in Runs List".format(runId))
        return -1
    idx = ids[0]
    return idx
