import unittest
import numpy as np
from PIL import Image
from fpga_omr.model import pack_pixels,unpack_pixels,normalize,integer_forward
from fpga_omr.protocol import FrameStream,frame,HardwareModel

class ModelContractTests(unittest.TestCase):
    def test_packing_roundtrip_and_little_endian(self):
        bits=np.zeros(256,dtype=np.uint8);bits[[0,7,8,255]]=1
        raw=pack_pixels(bits)
        self.assertEqual(raw[0],129);self.assertEqual(raw[1],1);self.assertEqual(raw[31],128)
        np.testing.assert_array_equal(unpack_pixels(raw),bits)
        with self.assertRaises(ValueError):unpack_pixels(raw[:-1])
        with self.assertRaises(ValueError):pack_pixels([2]*256)
        with self.assertRaises(ValueError):pack_pixels([.5]*256)

    def test_blank_and_padding(self):
        np.testing.assert_array_equal(normalize(Image.new('L',(30,40),255)),np.zeros(256))
        im=Image.new('L',(20,30),255);im.paste(0,(8,5,11,25))
        bits=normalize(im).reshape(16,16)
        self.assertGreater(bits.sum(),10);self.assertFalse(bits[0].any());self.assertFalse(bits[-1].any())

    def test_exact_half_up_saturation_and_signed_weights(self):
        w=dict(w1=np.zeros((64,256),dtype=np.int8),b1=np.zeros(64,dtype=np.int32),w2=np.zeros((11,64),dtype=np.int8),b2=np.zeros(11,dtype=np.int32),shift1=np.array(1))
        w['b1'][:3]=[1,1000,-9];w['w2'][0,:3]=[1,-1,100]
        scores=integer_forward(np.zeros(256),w)
        self.assertEqual(int(scores[0,0]),1-255)

    def test_wire_fragments_crc_and_resynchronization(self):
        stream=FrameStream();bad=bytearray(frame(0x60,1,b'\x01\x00'));bad[-1]^=1
        self.assertEqual(stream.push(bytes(bad)+b'noise'),[])
        good=frame(0xe0,2,bytes(range(14)))
        self.assertEqual(stream.push(good[:7]),[])
        self.assertEqual(stream.push(good[7:]),[(0xe0,2,bytes(range(14)))])

    def test_no_hardware_does_not_silently_run_cpu_or_cloud(self):
        class DeadTransport:
            def write(self,data):pass
            def read(self,size):return b''
        with self.assertRaises(TimeoutError):HardwareModel(DeadTransport(),123,timeout=.001).predict(np.zeros(256,dtype=np.uint8))

if __name__=='__main__':unittest.main()
