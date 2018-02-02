#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import sys
import threading
import getopt

import logging

from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.StructDict import StructDict
from rtfMRI.Errors import InvocationError, RequestError

defaultSettings = StructDict({
    'addr': 'localhost',
    'port': 5500,
    'model': None,
    'experiment_file': 'experiment.toml',
    'run_local': False
})


def printUsage(argv):
    usage_format = """Usage:
    {}: [-a <addr>, -p <port>, -m <model>, -l, -e <exp_file>]
    options:
        -a [--addr] -- server ip address
        -p [--port] -- server port
        -m [--model] -- model name
        -e [--experiment] -- experiment file (.json or .toml)
        -l [--run_local] -- run client and server together locally"""
    print(usage_format.format(argv[0]))


def parseCommandArgs(argv, settings):
    try:
        shortOpts = "a:p:m:e:l"
        longOpts = ["addr=", "port=", "model=", "experiment=", "run_local"]
        opts, _ = getopt.gnu_getopt(argv[1:], shortOpts, longOpts)
    except getopt.GetoptError as err:
        logging.error(repr(err))
        raise InvocationError("Invalid parameter specified: " + repr(err))
    for opt, arg in opts:
        if opt in ("-a", "--addr"):
            settings.addr = arg
        elif opt in ("-p", "--port"):
            settings.port = int(arg)
        elif opt in ("-m", "--model"):
            settings.model = arg
        elif opt in ("-e", "--experiment"):
            settings.experiment_file = arg
        elif opt in ("-l", "--run_local"):
            settings.run_local = True
        else:
            raise InvocationError("unimplemented option {} {}", opt, arg)
    return settings


def client_main(argv):
    logging.basicConfig(level=logging.INFO)
    try:
        settings = parseCommandArgs(argv, defaultSettings)
        cfg = loadConfigFile(settings.experiment_file)
        if 'session' not in cfg.keys():
            raise InvocationError("Experiment file must have session section")
        # Start local server if requested
        if settings.run_local is True:
            startLocalServer(settings)
        # Determine the desired model
        model = settings.model
        if model is None:
            if cfg.experiment is None or cfg.experiment.model is None:
                raise InvocationError("No model specified in experiment file or command line")
            model = cfg.experiment.model
        # Start up client logic for the specified model
        if model == 'base':
            client = RtfMRIClient(settings.addr, settings.port)
        elif model == 'rtAtten':
            client = RtAttenClient(settings.addr, settings.port)
        else:
            raise InvocationError("Unsupported model %s" % (settings.model))
        client.initModel(model)
        client.runSession(cfg)
        if settings.run_local is True:
            client.sendShutdownServer()
        client.close()
    except InvocationError as err:
        print(repr(err))
        printUsage(argv)
        return False
    except FileNotFoundError as err:
        print("File {} not found: {}".format(settings.experiment_file, err))
        return False
    except RequestError as err:
        print("Request Error: {}".format(err))
    return True


def startLocalServer(settings):
    from ServerMain import server_main

    def start_server():
        server_args = ['ServerMain.py', '-p', str(settings.port)]
        server_main(server_args)
    server_thread = threading.Thread(name='server', target=start_server)
    server_thread.setDaemon(True)
    server_thread.start()


if __name__ == "__main__":
    client_main(sys.argv)
