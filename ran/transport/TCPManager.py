from __future__ import annotations

from dataclasses import dataclass
import random

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
    data: int #simple ascii encoding of string messages


class TCPManager:
    def makeSyn(self, src_port, dst_port):
        synPacket = TCPPacket(
            header=self.generateHeader(
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
    def processPacket():
        return 0
    def generateISN(self):
        return random.randint(0,4294967296)
    def makeSynAck(self, src_port, dst_port, clientISN):
        synAckPacket = TCPPacket(
                header=self.generateHeader(
                src_port=src_port,
                dst_port=dst_port,
                seq_num=self.generateISN(),
                ack_num=clientISN+1,
                flags=self.makeFlags(Syn=1, Ack=1),
                windowSize=64000
                ),
                data=0
        )
        return 0
    def makeAck(self, src_port, dst_port, serverISN):
        ackPacket = TCPPacket(
                        header=self.generateHeader(
                        src_port=src_port,
                        dst_port=dst_port,
                        seq_num=self.generateISN(),
                        ack_num=serverISN+1,
                        flags=self.makeFlags(Syn=1, Ack=1),
                        windowSize=64000
                        ),
                        data=0
                )
    def convertPacket(self):
        return 0
    def generateHeader(self, src_port, dst_port, seq_num, ack_num, flags, windowSize):
        checkSum=self.checkSum()
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
    def closeConnection(self):
        return 0
    def readPacket(self):
        return 0
    def checkSum(self):
        return 0
    def makeFlags(self, Cwr=0, Ece=0, Urg=0, Ack=0, Psh=0, Rst=0, Syn=0, Fin=0):
        return (Cwr*128 + Ece*64 + Urg*32 + Ack*16 + Psh*8 + Rst*4 + Syn*2 + Fin*1)