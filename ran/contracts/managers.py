from __future__ import annotations

from dataclasses import dataclass
import random, math
# from .radio import Signal
# from contracts import AgentIntent

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
    def prepareIpPacket(self, targetIp, src_ip, transportData):
        print(transportData)
        return 0
        
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
        print(data_length)
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
        binResult = bin(result)[2:]
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
            totalstring = srcIp + targetIp +padding + protocol + length + bin(header.src_port)[2:].zfill(16)+ bin(header.dst_port)[2:].zfill(16) + bin(header.seq_num)[2:].zfill(32) + bin(header.ack_num)[2:].zfill(32)+ bin(header.do)[2:].zfill(4)  + bin(header.flags)[2:].zfill(12) + bin(header.window_size)[2:].zfill(16)+ tempChecksum + data
            result = 0
            for i in range(0,math.ceil(len(totalstring) /16)):
                result += int(totalstring[i*16:((i+1) *16)],2)
            #remove overflow
            binResult = bin(result)[2:]
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
            n >>= 1
        return result




class ApplicationManager():
    connections: dict[str:bool] = None
    transportLayer:TransportManager = TransportManager()
    ipLayer: IPManager = IPManager()
    def process(self, transportData):
        return 0
    def send(self, targetIp, targetPort, targetProtocol, data, source_port, srcIp):
        if targetProtocol == "TCP":
            # if self.connections[targetIp]:
                tcpData = self.transportLayer.preparePacketTCP(source_port, targetPort, data, targetIp, srcIp)
                self.ipLayer.prepareIpPacket(targetIp, srcIp, tcpData)
            # else:
            #     self.transportLayer.initiateConnection(source_port, targetPort, targetIp, srcIp)
            #     self.connections.update({targetIp:True})
        else:
            udpData = self.transportLayer.preparePacketUDP(source_port, targetPort, data, targetIp, srcIp)
            self.ipLayer.prepareIpPacket(targetIp, srcIp, udpData)


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