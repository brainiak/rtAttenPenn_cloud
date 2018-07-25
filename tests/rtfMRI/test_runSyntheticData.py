import pytest  # type: ignore
import os
import inspect
import typing
import logging
import rtfMRI.scripts.ClientMain as ClientMain
import tests.rtfMRI.simfmri.generate_data as gd
# import generate_fmri_data.generate_data as gd

cfgFile = './syntheticDataCfg.toml'
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="module")
def setupTest():  # type: ignore
    """Generate synthetic image data for the test runs"""
    gd.generate_data(getCfgFileFullPath())


@pytest.fixture(scope="module")
def getCfgFileFullPath():  # type: ignore
    """Get the directory of this test file"""
    frame = inspect.currentframe()
    moduleFile = typing.cast(str, frame.f_code.co_filename)  # type: ignore
    moduleDir = os.path.dirname(moduleFile)
    cfgFullPath = os.path.join(moduleDir, cfgFile)
    return cfgFullPath


def test_runSyntheticData():
    print("rtfMRI: test_runSyntheticData")
    setupTest()
    # import pdb; pdb.set_trace()
    result = ClientMain.ClientMain("localhost", 5211, getCfgFileFullPath(), True, None)
    assert result is True


if __name__ == '__main__':
    pytest.main(['-s', '--log-cli-level', 'debug', 'tests/rtfMRI/test_runSyntheticData.py'])
