from __future__ import annotations

from dataclasses import dataclass, field
from .radio import Signal
from .managers import ApplicationManager, IpHeader, revertIp, convertIp
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
class Call:
    id: int
    members:list[str]

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
    protocols: list[str]
    dnn: str
    port: int
    service_types: frozenset
    applicationLayer: ApplicationManager
    def clearBuffer(self):
            self.bufferOut = []
            self.requiresDL = False
    def prepareBuffer(self):
        return 0
    def receive(self, signal):
            self.applicationLayer.receive(signal.payload)
            ipheader, ipdata = self.applicationLayer.ipLayer.process(signal.payload)
            if ipheader.protocol == 6:
                cleanConnections = []
                for connection in self.applicationLayer.connections:
                    if self.applicationLayer.connections[connection] == "CLOSED":
                        byteString = ''.join(self.applicationLayer.dataTable[connection])
                        byteList = []
                        for i in range(0, math.ceil(len(byteString)/8)):
                            if (i+1)*8 >= len(byteString):
                                byteList.append(int(byteString[i*8:],2))
                            else:
                                byteList.append(int(byteString[i*8:(i+1)*8],2))
                        data = ''
                        for char in byteList:
                            data += chr(char)
                        print(data)
                        self.interpret(data, ipheader)
                        cleanConnections.append(connection)
                for connection in cleanConnections:
                    self.applicationLayer.dataTable.pop(connection)
                    self.applicationLayer.connections.pop(connection)
            else:
                transheader, data = self.applicationLayer.transportLayer.processPacketUDP(ipdata)
                byteString = ''.join(self.applicationLayer.dataTable[transheader.dst_port, transheader.src_port, ipheader.srcIp, ipheader.destIp])
                self.applicationLayer.dataTable[transheader.dst_port, transheader.src_port, ipheader.srcIp, ipheader.destIp] = []
                byteList = []
                for i in range(0, math.ceil(len(byteString)/8)):
                    if (i+1)*8 >= len(byteString):
                        byteList.append(int(byteString[i*8:],2))
                    else:
                        byteList.append(int(byteString[i*8:(i+1)*8],2))
                data = ''
                for char in byteList:
                    data += chr(char)
                
                self.interpret(data, ipheader)
                

    

@dataclass(slots=True)
class VideoServer(Server):
    videos: dict[str, Video]
    videosToLeave: list[Message]
    messages: list[Message]
    def interpret(self, data, ipheader:IpHeader):
        splitData = data.split(':')
        if(splitData[1] == "video_upload"):
                name = splitData[1]
                content = splitData[2]
                size = splitData[3]
                creator = revertIp(ipheader.srcIp)
                self.uploadVideo(name, content, creator, size)
        if(splitData[1] == "video_stream"):
                name = splitData[1]
                self.streamVideo(name, revertIp(ipheader.srcIp))
        if(splitData[1] == "video_stream"):
            name = splitData[1]
            if self.videos[name].creator == revertIp(ipheader.srcIp):
                self.deleteVideo(name)
            else:
                self.messages.append(Message(
                                                content="You cannot delete this video as you did not post it",
                                                recipient=revertIp(ipheader.srcIp),
                                                sender=None,
                                                size= 2*1024,
                                                service_type="error"
                                                ))
        return 0
            
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
    
    def streamVideo(self, name, recipient):
        video = self.videos[name]
        self.videosToLeave.append(Message(
            video.content,
            recipient=recipient,
            sender=video.creator,
            size= video.size,
            service_type="video"
        ))
    def prepareBuffer(self):
            if len(self.videosToLeave) != 0:
                for message in self.videosToLeave:
                    self.bufferOut.append(message)
                self.requiresDL = True
                print(self.requiresDL)
                self.videosToLeave = []

@dataclass(slots=True)
class WebServer(Server):
    siteContent: dict[str, str]
    dataSizes: dict[str, int]

@dataclass(slots=True)
class GamingServer(Server):
    playerWins: dict[str, int]
    messages: list[Message]
    pendingChallenges: dict[str:list[str]]
    supportedGame: str
    def interpret(self, data, ipheader:IpHeader):
            splitData = data.split(':')
            match splitData[1]:
                case "make_challenge":
                    self.requestGame(revertIp(ipheader.srcIp), revertIp(ipheader.destIp), splitData[1])
                case "accept_challenge":
                    self.validateChallenge(revertIp(ipheader.destIp), revertIp(ipheader.srcIp))
                case "check_stats":
                    self.checkResults(revertIp(ipheader.srcIp))
    def checkResults(self, player):
        if player in self.playerWins:
            self.messages.append(Message(
                                content="You have won "+str(self.playerWins[player])+ " times!",
                                recipient=player,
                                sender=None,
                                size= 2*1024,
                                service_type="result"
                                ))
        else:
            self.messages.append(Message(
                                content="No wins are logged for this player, try challenging someone!",
                                recipient=player,
                                sender=None,
                                size= 2*1024,
                                service_type="error"
                                ))
    def calculateWinner(self, players):
        winner = players[random.randint(0, len(players)-1)]
        if winner in self.playerWins:
            self.playerWins.update({winner: self.playerWins[winner]+1})
        else:
            self.playerWins.update({winner: 1})
        losers = []
        for player in players:
            if player != winner:
                losers.append(player)
        return winner, losers
    def requestGame(self, challenger, challenged, message):
        if challenger in self.pendingChallenges:
            seen = False
            for challenge in self.pendingChallenges[challenger]:
                if challenge == challenged:
                    seen = True
            if (not seen):
                self.messages.append(Message(
                            content=message,
                            recipient=challenged,
                            sender=challenger,
                            size= 2*1024,
                            service_type="challenge"
                        ))
                self.pendingChallenges[challenger].append(challenged)  
            else:
                self.messages.append(Message(
                                content="You have already challenged this player, please wait for their response",
                                recipient=challenger,
                                sender=None,
                                size= 2*1024,
                                service_type="error"
                                ))
        self.pendingChallenges.update({challenger:[challenged]})
        self.messages.append(Message(
                                    content=message,
                                    recipient=challenged,
                                    sender=challenger,
                                    size= 2*1024,
                                    service_type="challenge"
                                ))

    def validateChallenge(self, challenger, challenged):
        if challenger in self.pendingChallenges:
            seen = False
            for challenge in self.pendingChallenges[challenger]:
                if challenge == challenged:
                    seen = True
                    if seen:
                        winner, losers = self.calculateWinner(players=[challenger, challenged])
                        self.messages.append(Message(
                                            content="Congratulations, you have won the game against: " +losers[0],
                                            recipient=winner,
                                            sender=None,
                                            size= 2*1024,
                                            service_type="result"
                                            ))
                        self.messages.append(Message(
                                            content="Unfortunately, you have lost the game against: " +winner,
                                            recipient=losers[0],
                                            sender=None,
                                            size= 2*1024,
                                            service_type="result"
                                            ))
                    else:
                        self.messages.append(Message(
                                            content="This player has not challenged you, perhaps send them a challenge yourself?",
                                            recipient=challenger,
                                            sender=None,
                                            size= 2*1024,
                                            service_type="error"
                                            ))
        else:
            self.messages.append(Message(
                                content="This player has not challenged you, perhaps send them a challenge yourself?",
                                recipient=challenger,
                                sender=None,
                                size= 2*1024,
                                service_type="error"
                                ))
    def prepareBuffer(self):
                
                if len(self.messages) != 0:
                    for message in self.messages:
                        self.bufferOut.append(message)
                    self.requiresDL = True
                    self.messages = []


@dataclass(slots=True)
class MessageServer(Server):
    #use ips of the sender to differentiate signals, composed with the session ids to distinguish between messages sent by the same person. 
    storedMessages: list[Message]
    def interpret(self, data, ipheader):
            self.storedMessages.append(Message(
                content=data,
                recipient=data.split(':')[0],
                sender=ipheader.srcIp,
                size=math.ceil(len(data)/8),
                service_type="message"
            ))

    def prepareBuffer(self):
        if len(self.storedMessages) != 0:
            for message in self.storedMessages:
                self.bufferOut.append(message)
            self.requiresDL = True
            self.storedMessages = []
    
    

@dataclass(slots=True)
class CallServer(Server):
    messages: list[Message]
    activeCalls: dict[int:Call]
    pendingCalls: dict[str:list[str]]
    def interpret(self, data, ipheader:IpHeader):
        splitdata = data.split(':')
        match splitdata[1]:
                                case "make_call":
                                    self.requestCall(revertIp(ipheader.srcIp), splitdata[0])
                                case "accept_call":
                                    self.validateCall(splitdata[0], revertIp(ipheader.srcIp))
                                case "call_data":
                                    callId = int(splitdata[2])
                                    self.forwardStream(callId, revertIp(ipheader.srcIp), data, splitdata[len(splitdata)-1])
                                case "end_call":
                                    callId = int(splitdata[2])
                                    self.endCall(callId, revertIp(ipheader.srcIp))
    def setUpCall(self, members):
        callId = random.randint(0,1024)
        while(callId in self.activeCalls):
            callId = random.randint(0,1024)
        #TEMPORARY, PLEASE REMOVE
        callId = 1
        self.activeCalls.update({callId:Call(
            id = callId,
            members=members,
        )})
        return callId
    def requestCall(self, caller, callee):
        if caller in self.pendingCalls:
                    seen = False
                    for challenge in self.pendingCalls[caller]:
                        if challenge == callee:
                            seen = True
                    if (not seen):
                        self.messages.append(Message(
                                    content=None,
                                    recipient=callee,
                                    sender=caller,
                                    size= 2*1024,
                                    service_type="call request"
                                ))
                        self.pendingCalls[caller].append(callee)  
                    else:
                        self.messages.append(Message(
                                        content="You have already called this person, please wait for their response",
                                        recipient=caller,
                                        sender=None,
                                        size= 2*1024,
                                        service_type="error"
                                        ))
        self.pendingCalls.update({caller:[callee]})
        self.messages.append(Message(
                                        content=None,
                                        recipient=callee,
                                        sender=caller,
                                        size= 2*1024,
                                        service_type="call request"
                                    ))  
    def forwardStream(self, id, speaker, data, size):
        if id in self.activeCalls:
            if speaker in self.activeCalls[id].members:
                for member in self.activeCalls[id].members:
                    if member != speaker:
                        self.messages.append(Message(
                                        content=data,
                                        recipient=member,
                                        sender=speaker,
                                        size= size,
                                        service_type="call stream"
                                        ))
            else:
                self.messages.append(Message(
                            content="You are not in this call",
                            recipient=speaker,
                            sender=None,
                            size= 2*1024,
                            service_type="error"
                            ))
        else:
            self.messages.append(Message(
                                                    content="This call does not exist",
                                                    recipient=speaker,
                                                    sender=None,
                                                    size= 2*1024,
                                                    service_type="error"
                                                    ))
        return 0   
    def endCall(self, id, speaker):
        if id in self.activeCalls:
            if speaker in self.activeCalls[id].members:
                for member in self.activeCalls[id].members:
                    self.messages.append(Message(
                    content=speaker+" has ended the call",
                    recipient=member,
                    sender=speaker,
                    size= 2*1024,
                    service_type="call end"
                    ))
                self.activeCalls.pop(id)
            else:
                            self.messages.append(Message(
                                        content="You are not in this call",
                                        recipient=speaker,
                                        sender=None,
                                        size= 2*1024,
                                        service_type="error"
                                        ))
        else:
                    self.messages.append(Message(
                                                            content="This call does not exist",
                                                            recipient=speaker,
                                                            sender=None,
                                                            size= 2*1024,
                                                            service_type="error"
                                                            ))

    def validateCall(self, caller, callee):
            if caller in self.pendingCalls:
                seen = False
                for call in self.pendingCalls[caller]:
                    if call == callee:
                        seen = True
                        if seen:
                            callId = self.setUpCall(members=[caller, callee])
                            self.messages.append(Message(
                                                content=str(callId)+":You are now in a call with " +callee,
                                                recipient=caller,
                                                sender=None,
                                                size= 2*1024,
                                                service_type="call setup"
                                                ))
                            self.messages.append(Message(
                                                content=str(callId)+":You are now in a call with " +caller,
                                                recipient=callee,
                                                sender=None,
                                                size= 2*1024,
                                                service_type="call setup"
                                                ))
                        else:
                            self.messages.append(Message(
                                                content="This person has not called you, perhaps call them yourself?",
                                                recipient=caller,
                                                sender=None,
                                                size= 2*1024,
                                                service_type="error"
                                                ))
            else:
                self.messages.append(Message(
                                    content="This player has not called you, perhaps call them yourself?",
                                    recipient=caller,
                                    sender=None,
                                    size= 2*1024,
                                    service_type="error"
                                    ))
    
    def prepareBuffer(self):
            if len(self.messages) != 0:
                for message in self.messages:
                    self.bufferOut.append(message)
                self.requiresDL = True
                self.messages = []

@dataclass(slots=True)
class IotServer(Server):
    devices = dict[str, IoTDevice]



