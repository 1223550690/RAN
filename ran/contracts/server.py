from __future__ import annotations

from dataclasses import dataclass, field
from .radio import Signal
import random, math


@dataclass(slots=True)
class Website:
    name: str
    content: str
    size: int


@dataclass(slots=True)
class File:
    id: str
    content: str
    size: int

@dataclass(slots=True)
class Message:
    content: str
    recipient: str
    sender: str
    size: int
    service_type: str

@dataclass(slots=True)
class Video:
    id: str
    content: str
    size: int
    creator: str

@dataclass(slots=True)
class Stream:
    id: str
    content: str
    size: int
    sender: str
    recipient: str

@dataclass(slots=True)
class IoTDevice:
    id: str
    typeOfReading:str
    reading: float

@dataclass(slots=True)
class Request:
    recipient: str
    data: str

@dataclass(slots=True)
class Server:
    name: str
    address:str
    bufferOut:list
    requiresDL: bool
    collectedSignals: list[Signal]
    def clearBuffer(self):
            self.bufferOut = []
            self.requiresDL = False
    def prepareBuffer(self):
        return 0

@dataclass(slots=True)
class VideoServer(Server):
    videos: dict[str, Video]
    videosToLeave: list[Message]
    def receive(self, signal):
        self.collectedSignals.append(signal)
        if signal.payload.endOfMessage:
            size = 0
            newSignals = []
            for collectedSignal in self.collectedSignals:
                if collectedSignal.header.senderIp == signal.header.senderIp and collectedSignal.header.sessionId == signal.header.sessionId:
                    size += collectedSignal.header.size
                else:
                    newSignals.append(collectedSignal)
            overhead = max(1, math.ceil(size /1500)) * 2
            if(signal.payload.service_type == "video_upload"):
                video = signal.payload.data.split(':')
                name = video[0]
                content = video[1]
                creator = signal.payload.senderUe
                self.uploadVideo(name, content, creator, size-overhead)
            if(signal.payload.service_type == "video_stream"):
                name = signal.payload.data
                self.streamVideo(name, signal)
            
    def uploadVideo(self, name, content, creator, size):
        video = Video(
            id=name,
            content=content,
            size=size,
            creator=creator
        )
        self.videos.update({name: video})
    
    def deleteVideo(self, name):
        self.videos.pop(name)
    
    def streamVideo(self, name, signal):
        video = self.videos[name]
        self.videosToLeave.append(Message(
            video.content,
            recipient=signal.payload.senderUe,
            sender=video.creator,
            size= video.size,
            service_type="video"
        ))
    def prepareBuffer(self):
            if len(self.videosToLeave) != 0:
                for message in self.videosToLeave:
                    self.bufferOut.append(message)
                self.requiresDL = True
                self.videosToLeave = []

@dataclass(slots=True)
class WebServer(Server):
    siteContent: dict[str, str]
    dataSizes: dict[str, int]

@dataclass(slots=True)
class GamingServer(Server):
    playerWins: dict[str, int]
    def calculateWinner(self, players):
        winner = players(random.randint(0, len(players)-1))
        self.playerwins.update({winner: self.playerwins[winner]+1})
        return winner

@dataclass(slots=True)
class MessageServer(Server):
    #use ips of the sender to differentiate signals, composed with the session ids to distinguish between messages sent by the same person. 
    storedMessages: list[Message]
    def receive(self, signal):
        self.collectedSignals.append(signal)
        if signal.payload.endOfMessage:
            size = 0
            newSignals = []
            for collectedSignal in self.collectedSignals:
                if collectedSignal.header.senderIp == signal.header.senderIp and collectedSignal.header.sessionId == signal.header.sessionId:
                    size += collectedSignal.header.size
                else:
                    newSignals.append(collectedSignal)
            overhead = max(1, math.ceil(size /1500)) * 2
            self.storedMessages.append(Message(
                content=signal.payload.data,
                recipient=signal.payload.destinationUe,
                sender=signal.payload.senderUe,
                size=size -overhead,
                service_type="message"
            ))
            self.collectedSignals = newSignals

    def prepareBuffer(self):
        if len(self.storedMessages) != 0:
            for message in self.storedMessages:
                self.bufferOut.append(message)
            self.requiresDL = True
            self.storedMessages = []
    
    

@dataclass(slots=True)
class CallServer(Server):
    streams: list[Stream]
    def receive(self, signal):
        return 0

@dataclass(slots=True)
class IotServer(Server):
    devices = dict[str, IoTDevice]



