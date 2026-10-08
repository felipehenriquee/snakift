import time
from PIL import Image
from sdf import render
import models as m
def sheet(scenes, path, W=128, H=160, ox=64, oy=124, scale=2):
    ims=[]
    for s in scenes:
        t=time.time(); ims.append(Image.fromarray(render(s,W,H,ox,oy))); print(round(time.time()-t,1), end=' ', flush=True)
    out=Image.new('RGBA',(W*len(ims),H),(60,60,70,255))
    for i,im in enumerate(ims): out.alpha_composite(im,(i*W,0))
    out.resize((out.width*scale,out.height*scale),Image.LANCZOS).save(path); print()
