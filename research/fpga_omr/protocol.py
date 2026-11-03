"""The same CRC8 wire framing as the instrument, with an isolated OMR namespace."""
import time
import struct
from .model import pack_pixels

def crc8(data):
    value=0
    for b in data:
        value^=b
        for _ in range(8):value=((value<<1)^7 if value&128 else value<<1)&255
    return value

def frame(kind,sequence,payload=b''):
    if not(0<=kind<=255 and 0<=sequence<=255 and len(payload)<=14):raise ValueError('Bad frame')
    body=bytes([1,kind,sequence,len(payload)])+payload
    return b'\xa5'+body+bytes([crc8(body)])

class FrameStream:
    def __init__(self):self.buffer=bytearray()
    def push(self,data):
        self.buffer.extend(data);out=[]
        while self.buffer:
            if self.buffer[0]!=165:del self.buffer[0];continue
            if len(self.buffer)<5:break
            if self.buffer[1]!=1 or self.buffer[4]>14:del self.buffer[0];continue
            size=6+self.buffer[4]
            if len(self.buffer)<size:break
            packet=bytes(self.buffer[:size])
            if crc8(packet[1:-1])!=packet[-1]:del self.buffer[0];continue
            out.append((packet[2],packet[3],packet[5:-1]));del self.buffer[:size]
        return out

class HardwareModel:
    """Transport provides write(bytes) and read(size). No cloud/CPU inference fallback."""
    def __init__(self,transport,model_crc,timeout=3):
        self.transport=transport;self.model_crc=model_crc;self.timeout=timeout;self.seq=0;self.glyph=0;self.stream=FrameStream()
    def request(self,kind,payload):
        self.seq=(self.seq+1)&255;self.transport.write(frame(kind,self.seq,payload));deadline=time.monotonic()+self.timeout
        while time.monotonic()<deadline:
            for typ,seq,data in self.stream.push(self.transport.read(64)):
                if typ!=0xe0 or seq!=self.seq:continue
                if len(data)!=14:raise RuntimeError('FPGA OMR reply length mismatch')
                gid,status,digit,margin,count,version,model=struct.unpack('<HBBIBBI',data)
                if model!=self.model_crc or version!=1:raise RuntimeError('FPGA OMR model identity mismatch')
                if gid!=self.glyph:raise RuntimeError('FPGA OMR glyph identity mismatch')
                if status not in (0,1):raise RuntimeError(f'FPGA OMR rejected request: {status}')
                return status,digit,margin,count
        raise TimeoutError('FPGA did not respond; no API or CPU replacement was used')
    def predict(self,bits):
        self.glyph=self.glyph%65535+1;identifier=struct.pack('<H',self.glyph);raw=pack_pixels(bits)
        self.request(0x60,identifier)
        for offset in range(0,32,11):self.request(0x61,identifier+bytes([offset])+raw[offset:offset+11])
        status,digit,margin,count=self.request(0x62,identifier)
        if status!=1 or count!=32:raise RuntimeError('Incomplete FPGA inference')
        return {'digit':digit if digit<=7 else None,'class':digit,'margin':margin,'model_crc':self.model_crc,'inference_location':'fpga'}
