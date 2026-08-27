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

MTU = 1450


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
        packetLength = len(packet)
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
            headerChecksum=int(packet[80:96],2),
            srcIp=(packet[96:128]),
            destIp=(packet[128:160]),
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
    dataToLeave: list[str]
    initialSyn:int

class TransportManager:
    connectionTable: dict[tuple:ConnectionData]
    def __init__(self):
        self.connectionTable = {}
    def processPacketTCP(self, packet):
        packetLength = math.ceil(len(packet)/8)
        header = TCPHeader(
            src_port=int(packet[0:16],2),
            dst_port=int(packet[16:32],2),
            seq_num=int(packet[32:64],2),
            ack_num=int(packet[64:96],2),
            do=int(packet[96:100],2),
            flags=int(packet[100:112],2),
            window_size=int(packet[112:128],2),
            checksum=int(packet[128:144],2),
        )
        headlength = header.do * 4
        transportData = packet[headlength *8:packetLength]
        return header, transportData
    def processPacketUDP(self, packet):
            length = math.ceil(len(packet)/8)
            header = UDPHeader(
                src_port=int(packet[0:16],2),
                dst_port=int(packet[16:32],2),
                length=int(packet[32:48],2),
                checksum=int(packet[48:64],2)
            )
            data = packet[64:]
            return header, data
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
                targetISN=0,
                dataToLeave="",
                initialSyn=isn
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
            print("Seq: " + str(isn))
            print("Ack: None")
            return header
    def makeSynAck(self, src_port, dst_port, targetIp, srcIp, otherISN):
        localISN = self.generateISN()
        self.connectionTable.update({(src_port, dst_port, targetIp, srcIp):ConnectionData(
                        localISN=localISN,
                        targetISN=otherISN +1,
                        dataToLeave="",
                        initialSyn=localISN
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
        print("Seq: " + str(localISN))
        print("Ack: " + str(otherISN +1))
        return header
    def makeAck(self, src_port, dst_port, targetIp, srcIp, otherISN):
        self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN += 1
        self.connectionTable[(src_port, dst_port, targetIp, srcIp)].targetISN = otherISN +1
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
        print("Seq: " + str(self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN))
        print("Ack: " + str(self.connectionTable[(src_port, dst_port, targetIp, srcIp)].targetISN))
        return header
    def makeFinAck(self, src_port, dst_port, targetIp, srcIp):
            self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN
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
    def makeFin(self, src_port, dst_port, targetIp, srcIp):
        self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN +1
        self.connectionTable[(src_port, dst_port, targetIp, srcIp)].targetISN
        header=self.generateHeaderTCP(
                        src_port=src_port,
                        dst_port=dst_port,
                        seq_num=self.connectionTable[(src_port, dst_port, targetIp, srcIp)].localISN,
                        ack_num=self.connectionTable[(src_port, dst_port, targetIp, srcIp)].targetISN,
                        flags=self.makeFlags(Fin=1, Ack=1),
                        windowSize=64000,
                        srcIp=srcIp,
                        targetIp=targetIp,
                        data=None,
                        data_length=0,
                    )
        return header

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
        return result.zfill(8)




class ApplicationManager():
    connections: dict[tuple:str]
    delayedData: dict[tuple: str]
    transportLayer:TransportManager
    ipLayer: IPManager
    dataBuffer: list[str]
    messageBuffer: list[str]
    def __init__(self):
        self.connections = {}
        self.delayedData = {}
        self.transportLayer = TransportManager()
        self.ipLayer = IPManager()
        self.dataBuffer = []
        self.messageBuffer = []
    #prepare data for division by transport
    def send(self, targetIp, targetPort, targetProtocol, data, source_port, srcIp):
        if targetProtocol == "TCP":
            tcpData = 0
            # if (source_port, targetPort, targetIp, srcIp) in self.connections and self.connections[(source_port, targetPort, targetIp, srcIp)] == "CONNECTED":
            #     tcpData = self.transportLayer.preparePacketTCP(source_port, targetPort, data, targetIp, srcIp)
            #     ipPacket = self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, tcpData, 6)
            if (source_port, targetPort, targetIp, srcIp) not in self.connections:
                tcpData = self.transportLayer.makeSyn(source_port, targetPort, targetIp, srcIp)
                ipPacket = self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, tcpData, 6)
                self.connections.update({(source_port, targetPort, targetIp, srcIp):"SYN"})
                #Split data up and send it one packet at a time, allows retransmission as data is stored
                self.transportLayer.connectionTable[(source_port, targetPort, targetIp, srcIp)].dataToLeave+=data
                self.messageBuffer.append(ipPacket)
            else:
                self.transportLayer.connectionTable[(source_port, targetPort, targetIp, srcIp)].dataToLeave+=data
        else:
            byteLength = len(data) /8
            for i in range(0, math.floor(byteLength/MTU)):
                dataSegment = data[i*8*MTU:(i+1)*8*MTU]
                udpData = self.transportLayer.preparePacketUDP(source_port, targetPort, dataSegment, targetIp, srcIp)
                ipPacket= self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, udpData, 17)
                self.messageBuffer.append(ipPacket)
            dataSegment = data[i*8*MTU:]
            if dataSegment != "":
                udpData = self.transportLayer.preparePacketUDP(source_port, targetPort, dataSegment, targetIp, srcIp)
                ipPacket= self.ipLayer.prepareIpPacket(targetIp, srcIp, 0, udpData, 17)
                self.messageBuffer.append(ipPacket)
        
    def receive(self, data):
        ipheader, transportData = self.ipLayer.process(data)
        if ipheader.protocol == 6:
            transheader, data = self.transportLayer.processPacketTCP(transportData)
            flags = self.transportLayer.decodeFlags(transheader.flags)
            destIp = revertIp(ipheader.destIp)
            srcIp = revertIp(ipheader.srcIp)
            if flags[SYN]=='1' and flags[ACK] !='1': 
                tcpData = self.transportLayer.makeSynAck(src_port=transheader.dst_port, dst_port=transheader.src_port, targetIp=srcIp, srcIp=destIp, otherISN=transheader.seq_num)
                self.connections.update({(transheader.dst_port, transheader.src_port, srcIp, destIp):"SYN-ACK"})
                ipPacket = self.ipLayer.prepareIpPacket(dst_ip=srcIp, src_ip=destIp, ToS=0, transportData=tcpData, transportProtocol=6)
                self.messageBuffer.append(ipPacket)
            elif flags[SYN]=='1' and flags[ACK]=='1':
                tcpData = self.transportLayer.makeAck(transheader.dst_port, transheader.src_port, srcIp, destIp, transheader.seq_num)
                self.connections.update({(transheader.dst_port, transheader.src_port, srcIp, destIp):"CONNECTED"})
                ipPacket = self.ipLayer.prepareIpPacket(dst_ip=srcIp, src_ip=destIp, ToS=0, transportData=tcpData, transportProtocol=6)
                self.messageBuffer.append(ipPacket)

            elif flags[ACK]=='1' and self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="FIN_WAIT_1":
                self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="FIN_WAIT_2"

            elif flags[ACK]=='1' and self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="SYN-ACK":
                self.connections.update({(transheader.dst_port, transheader.src_port, srcIp, destIp):"CONNECTED"})
            elif flags[ACK]=='1' and self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="CLOSE_WAIT":
                self.connections.pop((transheader.dst_port, transheader.src_port, srcIp, destIp))
            elif flags[ACK]=='1' and self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="CONNECTED":
                #track which packets have been acked and prepare for more sending!
                if transheader.ack_num != self.transportLayer.connectionTable[transheader.dst_port, transheader.src_port, srcIp, destIp].localISN:
                    return 0
                if data != "":
                    self.dataBuffer.append(data)

            elif flags[FIN]=='1' and self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="FIN_WAIT_2":
                tcpData = self.transportLayer.makeFinAck(transheader.src_port, transheader.dst_port, destIp, srcIp)
                ipPacket = self.ipLayer.prepareIpPacket(dst_ip=srcIp, src_ip=destIp, ToS=0, transportData=tcpData, transportProtocol=6)
                self.messageBuffer.append(ipPacket)
                self.connections.pop((transheader.dst_port, transheader.src_port, srcIp, destIp))

            elif flags[FIN]=='1':
                tcpData = self.transportLayer.makeFinAck(transheader.dst_port, transheader.src_port, srcIp, destIp)
                ipPacket = self.ipLayer.prepareIpPacket(dst_ip=srcIp, src_ip=destIp, ToS=0, transportData=tcpData, transportProtocol=6)
                self.messageBuffer.append(ipPacket)
                self.connections[transheader.dst_port, transheader.src_port, srcIp, destIp] =="CLOSE_WAIT"
                tcpData = self.transportLayer.makeFin(transheader.dst_port, transheader.src_port, srcIp, destIp)
                ipPacket = self.ipLayer.prepareIpPacket(dst_ip=srcIp, src_ip=destIp, ToS=0, transportData=tcpData, transportProtocol=6)
                self.messageBuffer.append(ipPacket)
        else:
            transheader, data = self.transportLayer.processPacketUDP(transportData)
            if data != "":
                self.dataBuffer.append(data)
    def endConnection(self, source_port, targetPort, targetIp, srcIp):
        self.connections[source_port, targetPort, targetIp, srcIp] = "FIN_WAIT_1"
        tcpData = self.transportLayer.makeFin(source_port, targetPort, targetIp, srcIp)
        ipPacket = self.ipLayer.prepareIpPacket(dst_ip=targetIp, src_ip=srcIp, ToS=0, transportData=tcpData, transportProtocol=6)
        self.messageBuffer.append(ipPacket)
    #run every tick to prepare messages to send
    def updateManagers(self):
        for connection in self.transportLayer.connectionTable:
            if self.connections[connection] == "CONNECTED":
                connectdata = self.transportLayer.connectionTable[connection]
                byteLength = len(connectdata.dataToLeave) /8
                totalLength = 0
                for i in range(connectdata.localISN -connectdata.initialISN, math.floor(byteLength/MTU)+(connectdata.localISN -connectdata.initialISN)):
                    dataSegment = self.transportLayer.connectionTable[connection].dataToLeave[i*8*MTU:(i+1)*8*MTU]
                    segLength = len(dataSegment) /8
                    tcpData = self.transportLayer.generateHeaderTCP(src_port=connection[0], dst_port=connection[1], targetIp=connection[2], srcIp=connection[3], seq_num=connectdata.localISN +segLength, ack_num=connectdata.otherISN, flags=self.transportLayer.makeFlags(Ack=1), windowSize=64000, data_length=segLength)
                    ipPacket = self.ipLayer.prepareIpPacket(dst_ip=connection[2], src_ip=connection[3], ToS=0, transportData=tcpData, transportProtocol=6)
                    totalLength += segLength
                dataSegment = self.transportLayer.connectionTable[connection].dataToLeave[i*8*MTU:]








def convertIp(ip):
    splitIp = ip.split('.')
    finalIp = ""
    for i in range(0,4):
        IpByte = bin(int(splitIp[i]))[2:].zfill(8)
        finalIp+=(IpByte)
    return finalIp

def revertIp(bytes):
    result = str(int(bytes[0:8],2))
    for i in range (1, 4):
        result += '.'
        result += str(int(bytes[i*8:(i+1)*8],2))
    return result



        
        


host1= ApplicationManager()
host2= ApplicationManager()
#Split data 1450 byte packets to be sent one by one
host1.send(source_port=144, targetPort=187, targetProtocol="UDP", data="00011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110000111001111001010110010000011100001110011110010101100100000111000011100111100101011001000001110", targetIp="10.30.3.40", srcIp="10.20.2.20")
host2.receive(host1.messageBuffer[0])
host2.receive(host1.messageBuffer[1])