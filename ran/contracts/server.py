from __future__ import annotations

from dataclasses import dataclass, field
import random


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

@dataclass(slots=True)
class VideoServer(Server):
    videos: dict[str, Video]
    def receive(self, signal):
        self.uploadVideo("video", signal.payload.data)
    def uploadVideo(self, id, content):
        self.videos.update({id: content})
    def streamVideo(self, id):
        return self.videos[id]

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
    messagesToBeSent: list[Message]
    def receive(self, signal):
        self.messagesToBeSent.append(Message(
            content=signal.payload.data,
            recipient=signal.payload.destinationUe,
            sender=signal.payload.senderUe,
            size=signal.header.size,
        ))
    

@dataclass(slots=True)
class CallServer(Server):
    streams: list[Stream]
    def receive(self, signal):
        return 0

@dataclass(slots=True)
class IotServer(Server):
    devices = dict[str, IoTDevice]



