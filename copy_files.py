import os
import time
import shutil
from rtfMRI.RtfMRIClient import loadConfigFile, validateRunCfg
from rtfMRI.rtAtten.PatternsDesign2Config import createRunConfig

# parse experiment file
# copy run images every 2 seconds

expFile = 'rtAttenPennCfg.toml'
srcDir = '/scratch/amennen/newdataforgrant/20180122.0122182_rtAttenPenn.0122182_rtAttenPenn'
timeDelay = 2  # seconds

cfg = loadConfigFile(expFile)
dstDir = cfg.session.imgDir
print("Destination Dir: {}".format(dstDir))
if not os.path.exists(dstDir):
    os.makedirs(dstDir)

for runId in cfg.session.Runs:
    run = createRunConfig(cfg.session, runId)
    validateRunCfg(run)
    scanNumStr = str(run.scanNum).zfill(2)
    for blockGroup in run.blockGroups:
        for block in blockGroup.blocks:
            for TR in block.TRs:
                try:
                    # Assuming the output file volumes are still 1's based
                    fileNum = TR.vol + run.disdaqs // run.TRTime
                    fileNumStr = str(fileNum).zfill(3)
                    filename = cfg.session.dicomNamePattern.format(scanNumStr, fileNumStr)
                    srcFile = os.path.join(srcDir, filename)
                    print(filename)
                    shutil.copy(srcFile, dstDir)
                    time.sleep(timeDelay)
                except shutil.SameFileError as err:
                    print("skip: already exists: {}".format(filename))