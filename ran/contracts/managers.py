from __future__ import annotations

from dataclasses import dataclass
import random
from .radio import Signal
from contracts import AgentIntent

CWR=0
ECE=1
URG=2
ACK=3
PSH=4
RST=5
SYN=6
FIN=7





class IPManager():
    def process(self, signal:Signal):
        return 0
    def prepareIpPacket(self, targetIp, src_ip, TCPdata):
         
        
@dataclass(slots=True)
class TCPHeader:
    src_port: int
    dst_port: int
    seq_num: int
    ack_num: int
    do: int
    flags: int
    window_size: int
    checksum: int
    urg: int = 0

@dataclass(slots=True)
class TCPPacket:
    header:TCPHeader
    data: int #ascii encoding of text characters
    dataLength:int

@dataclass
class ConnectionData:
    target: str
    localISN: int
    targetISN: int

class TransportManager:
    fin_wait_1: bool = False
    fin_wait_2: bool = False
    ipLayer: IPManager = IPManager()
    def initiateConnection(self, src_port, dst_port, targetIp):
        return self.makeSyn(src_port, dst_port)
    def processPacketTCP(self, packet:TCPPacket):
        flagList = self.decodeFlags(packet.header.flags)
        if flagList[SYN]==1 and flagList[ACK]!= 1:
            self.makeSynAck()
        return 0
    def processPacketUDP(self, packet:TCPPacket):
            flagList = self.decodeFlags(packet.header.flags)
            if flagList[SYN]==1 and flagList[ACK]!= 1:
                self.makeSynAck()
            return 0
    def process(self, ipData):
            packet = ipData
            self.processPacketTCP(packet)
            return 0
    def preparePacketTCP(self, src_port, dst_port, data, targetIp, srcIp):
            TCPdata = 0
            self.ipLayer.prepareIpPacket(targetIp, srcIp, TCPdata)
            return 0
    def preparePacketUDP(self, src_port, dst_port, data, targetIp, srcIp):
            return 0
    def generateISN(self):
        return random.randint(0,4294967296)
    def makeSyn(self, src_port, dst_port):
            synPacket = TCPPacket(
                header=self.generateHeaderTCP(
                    src_port=src_port,
                    dst_port=dst_port,
                    seq_num=self.generateISN(),
                    ack_num=0,
                    flags=self.makeFlags(Syn=1),
                    windowSize=64000
                ),
                data=0
            )
            return synPacket
    def makeSynAck(self, src_port, dst_port, ISN):
        synAckPacket = TCPPacket(
                header=self.generateHeaderTCP(
                src_port=src_port,
                dst_port=dst_port,
                seq_num=self.generateISN(),
                ack_num=ISN+1,
                flags=self.makeFlags(Syn=1, Ack=1),
                windowSize=64000
                ),
                data=0
        )
        return synAckPacket
    def makeAck(self, src_port, dst_port, ISN):
        ackPacket = TCPPacket(
                        header=self.generateHeaderTCP(
                        src_port=src_port,
                        dst_port=dst_port,
                        seq_num=ISN,
                        ack_num=ISN+1,
                        flags=self.makeFlags(Syn=1, Ack=1),
                        windowSize=64000
                        ),
                        data=0
                )
        return ackPacket
    def convertPacket(self):
        return 0
    def generateHeaderTCP(self, src_port, dst_port, seq_num, ack_num, flags, windowSize):
        checkSum=self.checksumTCP()
        return TCPHeader(
            src_port=src_port,
            dst_port=dst_port,
            seq_num=seq_num,
            ack_num=ack_num,
            do=5, #As options are excluded, this is always the header size
            flags=flags,
            window_size=windowSize,
            checksum=checkSum,
        )
    def beginCloseConnection(self, src_port, dst_port, ISN):
        finPacket = TCPPacket(
                        header=self.generateHeader(
                        src_port=src_port,
                        dst_port=dst_port,
                        seq_num=self.generateISN(),
                        ack_num=ISN+1,
                        flags=self.makeFlags(Syn=1, Ack=1),
                        windowSize=64000
                        ),
                        data=0
                )
        self.fin_wait_1 = True
        return finPacket

    def checksumTCP(self):
        return 0
    def makeFlags(self, Cwr=0, Ece=0, Urg=0, Ack=0, Psh=0, Rst=0, Syn=0, Fin=0):
        return (Cwr*128 + Ece*64 + Urg*32 + Ack*16 + Psh*8 + Rst*4 + Syn*2 + Fin*1)
    def decodeFlags(self, flags:int):
        result = ""
        while flags > 0:
            result = str(flags & 1) + result
            n >>= 1
        return result




class ApplicationManager():
    connections: dict[str:bool] = None
    transportLayer:TransportManager = TransportManager()
    def process(self, transportData):
        return 0
    def send(self, targetIp, targetPort, targetProtocol, data, source_port, srcIp):
        if targetProtocol == "TCP":
            if self.connections[targetIp]:
                self.transportLayer.preparePacketTCP(source_port, targetPort, data, targetIp, srcIp)
            else:
                self.transportLayer.initiateConnection(source_port, targetPort, targetIp, srcIp)
                self.connections.update({targetIp:True})
        else:
            self.transportLayer.preparePacketUDP(source_port, targetPort, data, targetIp,srcIp)

         
