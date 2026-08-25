from __future__ import annotations

from dataclasses import dataclass
import random, math
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



@dataclass(slots=True)
class IpHeader:
    tos: int
    totalLength: int
    identification: int
    flags: int
    fragmentOffset: int
    protocol: int
    headerChecksum: int
    srcIp: str
    destIp: str
    version: int = 4 
    ttl: int = 1
    headerLength: int = 5


class IPManager():
    def process(self, packet):
        packetLength = math.ceil(len(packet)/8)
        headLength = int(packet[4:8],2) *4
        transportData = packet[headLength *8:packetLength]
        header = IpHeader(
            version=int(packet[0:4],2),
            headerLength=headLength,
            tos=int(packet[8:16],2),
            totalLength=packetLength,
            identification=int(packet[32:48],2),
            flags=int(packet[48:51],2),
            fragmentOffset=int(packet[51:64],2),
            ttl=int(packet[64:72],2),
            protocol=int(packet[72:80],2),
            checksum=int(packet[80:96],2),
            srcIp=(packet[96:128],2),
            destIp=(packet[128:160],2),
        )
        return header, transportData
    def generateHeader(self, dst_ip, src_ip, data, ToS, transportProtocol):
        data_length = math.ceil(len(data) /8)
        header = IpHeader(
            tos=ToS,
            totalLength=data_length+20,
            identification=0,
            flags= 0,
            fragmentOffset=0,
            protocol=transportProtocol,
            headerChecksum=0,
            srcIp=convertIp(src_ip),
            destIp=convertIp(dst_ip),
        )
        header = self.checksum(header)
        header = bin(header.version)[2:].zfill(4) + bin(header.headerLength)[2:].zfill(4) +bin(header.tos)[2:].zfill(8) + bin(header.totalLength)[2:].zfill(16) + bin(header.identification)[2:].zfill(16) + bin(header.flags)[2:].zfill(3) + bin(header.fragmentOffset)[2:].zfill(13) + bin(header.ttl)[2:].zfill(8) + bin(header.protocol)[2:].zfill(8) + bin(header.headerChecksum)[2:].zfill(16) +(header.srcIp)+(header.destIp)
        return header
    def prepareIpPacket(self, dst_ip, src_ip, ToS, transportData, transportProtocol):
        header = self.generateHeader(dst_ip, src_ip, transportData, ToS, transportProtocol)
        return header + transportData
    def checksum(self,header:IpHeader):
        totalstring = bin(header.version)[2:].zfill(4) + bin(header.headerLength)[2:].zfill(4) +bin(header.tos)[2:].zfill(8) + bin(header.totalLength)[2:].zfill(16) + bin(header.identification)[2:].zfill(16) + bin(header.flags)[2:].zfill(3) + bin(header.fragmentOffset)[2:].zfill(13) + bin(header.ttl)[2:].zfill(8) + bin(header.protocol)[2:].zfill(8) + bin(header.headerChecksum)[2:].zfill(16) +(header.srcIp)+(header.destIp)
        result = 0
        for i in range(0,math.ceil(len(totalstring) /16)):
            result += int(totalstring[i*16:((i+1) *16)],2)
        #remove overflow
        binResult = bin(result)[2:].zfill(16)
        while (len(binResult) >16):
            result = int(binResult[:len(binResult)-16],2) + int(binResult[len(binResult)-16:],2)
            binResult = bin(result)[2:].zfill(16)
        checksum = ""
        for i in range(0, 16):
            if binResult[i] == '0':
                checksum+='1'
            if binResult[i] == '1':
                checksum+='0'
        header.headerChecksum=int(checksum,2)
        return header
         
        
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
class UDPHeader:
    src_port: int
    dst_port: int
    length: int
    checksum: int

@dataclass(slots=True)
class ConnectionData:
    localISN: int
    targetISN: int

class TransportManager:
    fin_wait_1: bool = False
    fin_wait_2: bool = False
    connectionTable: dict[tuple:ConnectionData] ={}
    ipLayer: IPManager = IPManager()
    def initiateConnection(self, src_port, dst_port, targetIp, srcIp):
        return self.makeSyn(src_port, dst_port, targetIp, srcIp)
    def processPacketTCP(self, packet):
        flagList = self.decodeFlags(packet.header.flags)
        if flagList[SYN]==1 and flagList[ACK]!= 1:
            self.makeSynAck()
        return 0
    def processPacketUDP(self, packet):
            flagList = self.decodeFlags(packet.header.flags)
            if flagList[SYN]==1 and flagList[ACK]!= 1:
                self.makeSynAck()
            return 0
    def process(self, ipData):
            packet = ipData
            self.processPacketTCP(packet)
            return 0
    def preparePacketTCP(self, src_port, dst_port, data, targetIp, srcIp):
            data_length = math.ceil(len(data) /8)
            seq_num = 125
            ack_num = 48123402
            flags = self.makeFlags()
            windowSize = 64000
            header = self.generateHeaderTCP(src_port, dst_port, seq_num, ack_num, flags, windowSize, targetIp, srcIp, data, data_length )
            tcpData = header+ data
            return tcpData
    def preparePacketUDP(self, src_port, dst_port, data, targetIp, srcIp):
            data_length = math.ceil(len(data) /8)
            header = self.generateHeaderUDP(src_port, dst_port, data, data_length, targetIp, srcIp)
            udpData = header+ data
            return udpData
    def generateHeaderUDP(self, src_port, dst_port, data, data_length, srcIp, targetIp):
        header = UDPHeader(
            src_port=src_port,
            dst_port=dst_port,
            length=8 +data_length,
            checksum=0,
        )
        header = self.checksumUDP(srcIp=srcIp, targetIp=targetIp, header=header, data=data)
        header = bin(header.src_port)[2:].zfill(16) + bin(header.dst_port)[2:].zfill(16) + bin(header.length)[2:].zfill(16) + bin(header.checksum)[2:].zfill(16)
        return header
    def checksumUDP(self, srcIp, targetIp, header, data, padding=0, protocol=17):
        srcIp = convertIp(srcIp)
        targetIp = convertIp(targetIp)
        padding = bin(padding)[2:].zfill(8)
        protocol = bin(protocol)[2:].zfill(8)
        if header.length %2 != 0:
            data += bin(0)[2:].zfill(8)
        length = bin(header.length)[2:].zfill(16)
        tempChecksum = bin(0)[2:].zfill(16)
        totalstring = srcIp + targetIp +padding + protocol + length + bin(header.src_port)[2:].zfill(16) + bin(header.dst_port)[2:].zfill(16) + length + tempChecksum + data
        result = 0
        for i in range(0,math.ceil(len(totalstring) /16)):
            result += int(totalstring[i*16:((i+1) *16)],2)
        #remove overflow
        binResult = bin(result)[2:].zfill(16)
        while (len(binResult) >16):
            result = int(binResult[:len(binResult)-16],2) + int(binResult[len(binResult)-16:],2)
            binResult = bin(result)[2:].zfill(16)
        checksum = ""
        for i in range(0, 16):
            if binResult[i] == '0':
                checksum+='1'
            if binResult[i] == '1':
                checksum+='0'
        header.checksum=int(checksum,2)
        return header
    
    def generateISN(self):
        return random.randint(0,4294967296)
    def makeSyn(self, src_port, dst_port, targetIp, srcIp):
            isn = self.generateISN()
            self.connectionTable.update({(src_port, dst_port, targetIp, srcIp):ConnectionData(
                localISN=isn,
                targetISN=None,
            )})
            header=self.generateHeaderTCP(
                src_port=src_port,
                dst_port=dst_port,
                seq_num=isn,
                ack_num=0,
                flags=self.makeFlags(Syn=1),
                windowSize=64000,
                srcIp=srcIp,
                targetIp=targetIp,
                data=None,
                data_length=0,
            )
            return header
    def makeSynAck(self, src_port, dst_port, targetIp, srcIp, otherISN):
        localISN = self.generateISN()
        self.connectionTable.update({(src_port, dst_port, targetIp, srcIp):ConnectionData(
                        localISN=localISN,
                        targetISN=otherISN +1,
                    )})
        header=self.generateHeaderTCP(
                        src_port=src_port,
                        dst_port=dst_port,
                        seq_num=localISN,
                        ack_num=otherISN +1,
                        flags=self.makeFlags(Syn=1, Ack=1),
                        windowSize=64000,
                        srcIp=srcIp,
                        targetIp=targetIp,
                        data=None,
                        data_length=0,
                    )
        return header
    def makeAck(self, src_port, dst_port, targetIp, srcIp):
        self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN += 1
        self.connectionTable[(src_port, dst_port, targetIp, srcIp)].targetISN += 1
        header=self.generateHeaderTCP(
                        src_port=src_port,
                        dst_port=dst_port,
                        seq_num=self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN,
                        ack_num=self.connectionTable[(src_port, dst_port, targetIp, srcIp)].targetISN,
                        flags=self.makeFlags(Ack=1),
                        windowSize=64000,
                        srcIp=srcIp,
                        targetIp=targetIp,
                        data=None,
                        data_length=0,
                    )
        return header
    def convertPacket(self):
        return 0
    def generateHeaderTCP(self, src_port, dst_port, seq_num, ack_num, flags, windowSize, srcIp, targetIp, data, data_length):
        header = TCPHeader(
            src_port=src_port,
            dst_port=dst_port,
            seq_num=seq_num,
            ack_num=ack_num,
            do=5, #As options are excluded, this is always the header size in 32 bit words
            flags=flags,
            window_size=windowSize,
            checksum=0, 
        )
        header = self.checksumTCP(srcIp=srcIp, targetIp=targetIp, header=header, data=data, data_length=data_length)
        header = bin(header.src_port)[2:].zfill(16) + bin(header.dst_port)[2:].zfill(16)+ bin(header.seq_num)[2:].zfill(32) + bin(header.ack_num)[2:].zfill(32)+ bin(header.do)[2:].zfill(4) + bin(header.flags)[2:].zfill(12) + bin(header.window_size)[2:].zfill(16) + bin(header.checksum)[2:].zfill(16)
        return header
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

    def checksumTCP(self, srcIp, targetIp, header, data, data_length, padding=0, protocol=6):
            srcIp = convertIp(srcIp)
            targetIp = convertIp(targetIp)
            padding = bin(padding)[2:].zfill(8)
            protocol = bin(protocol)[2:].zfill(8)
            if data_length %2 != 0:
                data += bin(0)[2:].zfill(8)
            length = bin((header.do * 4)+data_length)[2:].zfill(16)
            tempChecksum = bin(0)[2:].zfill(16)
            totalstring = srcIp + targetIp +padding + protocol + length + bin(header.src_port)[2:].zfill(16)+ bin(header.dst_port)[2:].zfill(16) + bin(header.seq_num)[2:].zfill(32) + bin(header.ack_num)[2:].zfill(32)+ bin(header.do)[2:].zfill(4)  + bin(header.flags)[2:].zfill(12) + bin(header.window_size)[2:].zfill(16)+ tempChecksum
            if (data is not None):
                totalstring += data
            result = 0
            for i in range(0,math.ceil(len(totalstring) /16)):
                result += int(totalstring[i*16:((i+1) *16)],2)
            #remove overflow
            binResult = bin(result)[2:].zfill(16)
            while (len(binResult) >16):
                result = int(binResult[:len(binResult)-16],2) + int(binResult[len(binResult)-16:],2)
                binResult = bin(result)[2:].zfill(16)
            checksum = ""
            for i in range(0, 16):
                if binResult[i] == '0':
                    checksum+='1'
                if binResult[i] == '1':
                    checksum+='0'
            header.checksum=int(checksum,2)
            return header
    def makeFlags(self, Cwr=0, Ece=0, Urg=0, Ack=0, Psh=0, Rst=0, Syn=0, Fin=0):
        return (Cwr*128 + Ece*64 + Urg*32 + Ack*16 + Psh*8 + Rst*4 + Syn*2 + Fin*1)
    def decodeFlags(self, flags:int):
        result = ""
        while flags > 0:
            result = str(flags & 1) + result
            flags >>= 1
        return result




class ApplicationManager():
    connections: dict[tuple:str] = {}
    delayedData: dict[tuple: str] = {}
    transportLayer:TransportManager = TransportManager()
    ipLayer: IPManager = IPManager()
    def process(self, transportData):
        return 0
    def send(self, targetIp, targetPort, targetProtocol, data, source_port, srcIp):
        if targetProtocol == "TCP":
            if (source_port, targetPort, targetIp, srcIp) in self.connections and self.connections[(source_port, targetPort, targetIp, srcIp)] == "CONNECTED":
                tcpData = self.transportLayer.preparePacketTCP(source_port, targetPort, data, targetIp, srcIp)
                ipPacket = self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, tcpData, 6)
            elif (source_port, targetPort, targetIp, srcIp) not in self.connections:
                tcpData = self.transportLayer.initiateConnection(source_port, targetPort, targetIp, srcIp)
                ipPacket = self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, tcpData, 6)
                self.connections.update({(source_port, targetPort, targetIp, srcIp):"SYN"})
                self.delayedData.update({(source_port, targetPort, targetIp, srcIp):data})
            elif (source_port, targetPort, targetIp, srcIp) in self.connections and self.connections[(source_port, targetPort, targetIp, srcIp)] != "CONNECTED":
                #waiting for connection
                self.delayedData.update({(source_port, targetPort, targetIp, srcIp):data})
        else:
            udpData = self.transportLayer.preparePacketUDP(source_port, targetPort, data, targetIp, srcIp)
            ipPacket= self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, udpData, 17)
    def receive(self, signal:Signal):
        header, transportData = self.ipLayer.process(signal.payload.data)
        if header.protocol == 6:
            header, data = self.transportLayer.process(transportData)
            if header.flags[SYN]==1 and header.flags[ACK] !=1:
                tcpData = self.transportLayer.makeSynAck()
        else:
            header, data = self.transportLayer.process(self.transportData)

def convertIp(ip):
    splitIp = ip.split('.')
    finalIp = ""
    for i in range(0,4):
        IpByte = bin(int(splitIp[i]))[2:].zfill(8)
        finalIp+=(IpByte)
    return finalIp


        
        


manager= ApplicationManager()
manager.send(source_port=144, targetPort=187, targetProtocol="UDP", data="00011100111100101011001000001110", targetIp="10.30.3.40", srcIp="10.20.2.20")
manager.send(source_port=144, targetPort=187, targetProtocol="TCP", data="00011100111100101011001000001110", targetIp="10.30.3.40", srcIp="10.20.2.20")