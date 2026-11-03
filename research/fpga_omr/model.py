from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageOps

SIDE=16
HIDDEN=64
CLASSES=11
REJECT=10

def normalize(image):
    """Ink is one. Same aspect ratio, centered in 14x14 inside a 16x16 bitmap."""
    image=image.convert('L')
    ink=np.asarray(image)<200
    yy,xx=np.where(ink)
    if not len(xx):return np.zeros(256,dtype=np.uint8)
    image=image.crop((int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1))
    scale=14/max(image.size)
    image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.BILINEAR)
    canvas=Image.new('L',(SIDE,SIDE),255)
    canvas.paste(image,((SIDE-image.width)//2,(SIDE-image.height)//2))
    return (np.asarray(canvas).reshape(-1)<144).astype(np.uint8)

def pack_pixels(bits):
    bits=np.asarray(bits).reshape(-1)
    if len(bits)!=256 or np.any((bits!=0)&(bits!=1)):raise ValueError('Expected 256 binary pixels')
    bits=bits.astype(np.uint8)
    return np.packbits(bits,bitorder='little').tobytes()

def unpack_pixels(raw):
    if len(raw)!=32:raise ValueError('Expected exactly 32 bitmap bytes')
    return np.unpackbits(np.frombuffer(raw,dtype=np.uint8),bitorder='little')

def integer_forward(bits,weights):
    x=np.atleast_2d(bits)
    if x.shape[1]!=256 or np.any((x!=0)&(x!=1)):raise ValueError('Invalid binary bitmap')
    x=x.astype(np.int64)
    acc=x@weights['w1'].astype(np.int64).T+weights['b1'].astype(np.int64)
    shift=int(weights['shift1']);rounding=(1<<(shift-1)) if shift else 0
    hidden=np.clip((np.maximum(acc,0)+rounding)>>shift,0,255)
    logits=hidden@weights['w2'].astype(np.int64).T+weights['b2'].astype(np.int64)
    if np.any(logits>2147483647) or np.any(logits< -2147483648):raise OverflowError('RTL accumulator overflow')
    return logits.astype(np.int32)

def classify(logits):
    scores=np.asarray(logits,dtype=np.int64)
    winner=np.argmax(scores,axis=-1)
    ordered=np.sort(scores,axis=-1)
    return winner,ordered[...,-1]-ordered[...,-2]

def load_weights(folder):
    with np.load(Path(folder)/'integer_weights.npz')as f:return {k:f[k] for k in f.files}
