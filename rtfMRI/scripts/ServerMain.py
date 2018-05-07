#!/usr/bin/env python3
"""
Top level routine for server side rtfMRI processing
Usage: ServerMain.py -p 5200
Will start a server listening for new connections on port 5200.
Only one connection (therefore) only one client can be supported at a time.
The server will receive commands from the client, execute them and reply.
"""
import os
import logging
import click
from rtfMRI.RtfMRIServer import RtfMRIServer


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--port', '-p', default=5200, type=int, help="server port")
def ServerMain(port):
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        filename='logs/rtAttenServer.log')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    try:
        # Parse and add any additional settings from the command line
        should_exit = False
        while not should_exit:
            logging.info("RtfMRI: Server Starting")
            rtfmri = RtfMRIServer(port)
            should_exit = rtfmri.RunEventLoop()
        logging.info("Server shutting down")
    except Exception as err:
        logging.error(repr(err))
        raise err


if __name__ == "__main__":
    ServerMain()
