import pytest
import os
import sys
import dateutil
scriptPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(scriptPath, "../")
sys.path.append(rootPath)
from rtfMRI.StructDict import StructDict
from rtfMRI.RtfMRIClient import loadConfigFile
from ClientMain import writeRegConfigFile, runRegistration


@pytest.fixture(scope="module")
def getConfig():
    currentDir = os.path.dirname(os.path.realpath(__file__))
    cfg = loadConfigFile(os.path.join(currentDir, 'rtfMRI/syntheticDataCfg.toml'))
    return cfg


def localCreateRegConfig(cfg):
    regGlobals = StructDict()
    regGlobals.subjectNum = cfg.session.subjectNum
    regGlobals.dayNum = cfg.session.subjectDay
    regGlobals.runNum = cfg.session.Runs[0]
    regGlobals.highresScan = 5  # TODO load from request
    regGlobals.functionalScan = 7  # TODO load from request
    regGlobals.project_path = "/Data1/registration"
    regGlobals.roi_name = "wholebrain_mask"
    scanDate = dateutil.parser.parse(cfg.session.date)
    regGlobals.subjName = scanDate.strftime("%m%d%Y") + str(regGlobals.runNum) + \
        '_' + cfg.experiment.experimentName
    dicomFolder = scanDate.strftime("%Y%m%d") + '.' + regGlobals.subjName + '.' + regGlobals.subjName
    regGlobals.scanFolder = os.path.join(cfg.session.imgDir, dicomFolder)
    return regGlobals


def test_createRegConfig():
    cfg = getConfig()
    regGlobals = localCreateRegConfig(cfg)
    writeRegConfigFile(regGlobals, '/tmp')
    assert os.path.exists(os.path.join('/tmp', 'globals_gen.sh'))


def test_runRegistration():
    params = StructDict()
    params.cfg = getConfig()
    regGlobals = localCreateRegConfig(params.cfg)
    request = {'cmd': 'runReg',
               'regConfig': regGlobals,
               'regType': 'test',
               'dayNum': 1}
    lineCount = runRegistration(params, request, test=['ping', 'www.google.com', '-c', '3'])
    assert lineCount == 8
