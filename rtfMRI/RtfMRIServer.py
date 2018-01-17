"""
RtfMRIServer Module - Server handler for loading and running a model
Listens for requests from a client
When an "Init" request is received, the indicated model is loaded (e.g. base model, rtAtten model etc.)
Receives requests from the client and forwards them to the model for handling
Sends replies back to the client
"""
import logging
from .BaseModel import BaseModel
from .rtAtten.RtAttenModel import RtAttenModel
from .MsgTypes import MsgType, MsgEvent
from .Messaging import RtMessagingServer, Message
from .Errors import *

class RtfMRIServer():
    """Class for event handling on the server"""

    def __init__(self, port):
        self.messaging = RtMessagingServer(port)
        self.model = None

    def RunEventLoop(self):
        while True:
            msg = None
            reply = None
            try:
                msg = self.messaging.getRequest()
                reply = successReply(msg.id)
                if msg.type == MsgType.Init:
                    if msg.fields.modelType == 'base':
                        logging.info("RtfMRIServer: init base model")
                        self.model = BaseModel()
                    elif msg.fields.modelType == 'rtAtten':
                        self.model = RtAttenModel()
                    else:
                        raise RequestError("unknown model type '{}'".format(msg.fields.modelType))
                elif msg.type == MsgType.Command:
                    if self.model is None:
                        raise StateError("No model object exists")
                    reply = self.model.handleMessage(msg)
                elif msg.type == MsgType.Shutdown:
                    break
                else:
                    raise RequestError("unknown request type '{}'".format(msg.type))
            except RTError as err:
                msg_id = 0 if msg is None else msg.id
                reply = errorReply(msg_id, err)
            except KeyError as err:
                msg_id = 0 if msg is None else msg.id
                reply = errorReply(msg_id, RTError("Field not found: {}".format(err)))
            self.messaging.sendReply(reply)
        return True

def errorReply(msgId, error):
    msg = Message()
    msg.id = msgId
    msg.type = MsgType.Reply
    msg.event_type = MsgEvent.Error
    msg.data = repr(error).encode()
    return msg

def successReply(msgId):
    msg = Message()
    msg.id = msgId
    msg.type = MsgType.Reply
    msg.event_type = MsgEvent.Success
    msg.data = None
    return msg
