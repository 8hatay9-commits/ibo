#!/usr/bin/env python3
import os, math, wave, subprocess, textwrap
from pathlib import Path
import requests
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path.cwd()
WORK = ROOT / 'hatice_film_work'
ASSETS = WORK / 'assets'
FRAMES = WORK / 'frames'
CLIPS = WORK / 'clips'
for p in (WORK, ASSETS, FRAMES, CLIPS): p.mkdir(parents=True, exist_ok=True)
OUT = ROOT / 'hatice-dortyol-takeover.mp4'
POSTER = ROOT / 'hatice-dortyol-poster.jpg'
W,H,FPS = 1080,1920,30

SOURCES = [
('hbb01','https://hataycdn.hatay.bel.tr/icerik/img/medya/gallery/6SGnZhVjIjEKGAu2hSRq.jpeg'),
('hbb02','https://hataycdn.hatay.bel.tr/icerik/img/medya/gallery/I6LFYgG2uqTMTcDId54a.jpeg'),
('hbb03','https://hataycdn.hatay.bel.tr/icerik/img/medya/gallery/XWewSD1Y3Q2mLLXyg00Z.jpeg'),
('hbb04','https://hataycdn.hatay.bel.tr/icerik/img/medya/gallery/82Um32VIfMip9DYwI51T.jpeg'),
('hbb05','https://hataycdn.hatay.bel.tr/icerik/img/medya/gallery/l84v7AXZWYur5dXrwkKP.jpeg'),
('hbb06','https://hataycdn.hatay.bel.tr/icerik/img/medya/gallery/GWHReRWB5S3PEgdw9JpU.jpeg'),
('saat01','https://www.akdenizgercek.com.tr/cropImages/1280x/olds/akdenizgercek-comtr/d/news/104567.jpg'),
]

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

def run(cmd):
    print('RUN', ' '.join(map(str,cmd)))
    subprocess.run(list(map(str,cmd)), check=True)

def dl(name,url):
    path=ASSETS/f'{name}.img'
    r=requests.get(url,timeout=45,headers={'User-Agent':'Mozilla/5.0'})
    r.raise_for_status(); path.write_bytes(r.content)
    print(name, r.headers.get('content-type'), len(r.content))
    return path

def cover_crop(im, xbias=0.5, ybias=0.5):
    im=im.convert('RGB')
    src=im.width/im.height; tgt=W/H
    if src>tgt:
        nw=int(im.height*tgt)
        x=int((im.width-nw)*xbias); x=max(0,min(im.width-nw,x))
        im=im.crop((x,0,x+nw,im.height))
    else:
        nh=int(im.width/tgt)
        y=int((im.height-nh)*ybias); y=max(0,min(im.height-nh,y))
        im=im.crop((0,y,im.width,y+nh))
    return im.resize((W,H),Image.Resampling.LANCZOS)

def grade(im):
    im=ImageEnhance.Contrast(im).enhance(1.10)
    im=ImageEnhance.Color(im).enhance(0.92)
    # warm highlights + cool shadows
    arr=np.array(im).astype(np.float32)/255
    l=arr.mean(2,keepdims=True)
    arr[:,:,0]+=0.035*l[:,:,0]
    arr[:,:,2]+=0.025*(1-l[:,:,0])
    arr=np.clip(arr,0,1)
    im=Image.fromarray((arr*255).astype(np.uint8))
    # vignette
    yy,xx=np.mgrid[0:H,0:W]
    dx=(xx-W/2)/(W/2); dy=(yy-H/2)/(H/2)
    mask=np.clip(1-0.36*(dx*dx+dy*dy),0.58,1.0)[...,None]
    a=np.array(im).astype(np.float32)*mask
    return Image.fromarray(np.clip(a,0,255).astype(np.uint8))

def stamp(draw, left, right):
    f=ImageFont.truetype(MONO,24)
    draw.text((48,54),left,font=f,fill=(226,226,218))
    bb=draw.textbbox((0,0),right,font=f)
    draw.text((W-48-(bb[2]-bb[0]),54),right,font=f,fill=(160,160,158))
    draw.line((48,98,W-48,98),fill=(110,110,110),width=1)

def perspective_text(base, text, quad, size=120, color=(248,238,215), glow=True, stroke=2):
    font=ImageFont.truetype(BOLD,size)
    temp=Image.new('RGBA',(1500,500),(0,0,0,0)); d=ImageDraw.Draw(temp)
    bb=d.textbbox((0,0),text,font=font,stroke_width=stroke)
    tw,th=bb[2]-bb[0],bb[3]-bb[1]
    x=(temp.width-tw)//2; y=(temp.height-th)//2-bb[1]
    if glow:
        glow_im=Image.new('RGBA',temp.size,(0,0,0,0)); gd=ImageDraw.Draw(glow_im)
        gd.text((x,y),text,font=font,fill=(*color,210),stroke_width=stroke,stroke_fill=(*color,200))
        glow_im=glow_im.filter(ImageFilter.GaussianBlur(16))
        temp=Image.alpha_composite(temp,glow_im)
    d=ImageDraw.Draw(temp)
    d.text((x,y),text,font=font,fill=(*color,255),stroke_width=stroke,stroke_fill=(255,255,255,130))
    rgba=np.array(temp)
    src=np.float32([[0,0],[temp.width-1,0],[temp.width-1,temp.height-1],[0,temp.height-1]])
    dst=np.float32(quad)
    M=cv2.getPerspectiveTransform(src,dst)
    warped=cv2.warpPerspective(rgba,M,(W,H),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT)
    wb=Image.fromarray(warped,'RGBA')
    out=Image.alpha_composite(base.convert('RGBA'),wb)
    return out.convert('RGB')

def road_reflection(base, text, y=1450, alpha=90):
    layer=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(layer)
    f=ImageFont.truetype(BOLD,120)
    bb=d.textbbox((0,0),text,font=f); tw=bb[2]-bb[0]
    d.text(((W-tw)//2,y),text,font=f,fill=(245,225,180,alpha))
    layer=layer.filter(ImageFilter.GaussianBlur(5))
    arr=np.array(layer)
    # vertical streaks
    for x in range(0,W,11):
        if np.random.RandomState(x).rand()>0.55:
            arr[y+110:min(H,y+380),x:x+3,3] = (arr[y+110:min(H,y+380),x:x+3,3]*0.35).astype(np.uint8)
    return Image.alpha_composite(base.convert('RGBA'),Image.fromarray(arr,'RGBA')).convert('RGB')

def bubble(base, text, x, y, align='left'):
    im=base.convert('RGBA'); layer=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(layer)
    f=ImageFont.truetype(FONT,34)
    lines=textwrap.wrap(text,width=24)
    bb=d.multiline_textbbox((0,0),'\n'.join(lines),font=f,spacing=8)
    bw=bb[2]-bb[0]+60; bh=bb[3]-bb[1]+50
    if align=='right': x=W-x-bw
    d.rounded_rectangle((x,y,x+bw,y+bh),radius=24,fill=(10,10,13,205),outline=(255,255,255,75),width=2)
    d.multiline_text((x+30,y+23),'\n'.join(lines),font=f,fill=(244,244,240),spacing=8)
    return Image.alpha_composite(im,layer).convert('RGB')

def card(lines, small=None, sub=None):
    im=Image.new('RGB',(W,H),(2,2,4)); d=ImageDraw.Draw(im)
    # subtle grain
    rng=np.random.default_rng(9)
    noise=rng.integers(0,12,(H,W),dtype=np.uint8)
    arr=np.array(im); arr=np.clip(arr+noise[...,None],0,255).astype(np.uint8); im=Image.fromarray(arr); d=ImageDraw.Draw(im)
    if small:
        f0=ImageFont.truetype(MONO,25); bb=d.textbbox((0,0),small,font=f0); d.text(((W-(bb[2]-bb[0]))/2,140),small,font=f0,fill=(120,120,125))
    f=ImageFont.truetype(BOLD,68)
    txt='\n'.join(lines); bb=d.multiline_textbbox((0,0),txt,font=f,spacing=30,align='center')
    d.multiline_text(((W-(bb[2]-bb[0]))/2,720),txt,font=f,fill=(244,242,235),spacing=30,align='center')
    if sub:
        sf=ImageFont.truetype(FONT,38); sb=d.multiline_textbbox((0,0),sub,font=sf,spacing=15,align='center')
        d.multiline_text(((W-(sb[2]-sb[0]))/2,1050),sub,font=sf,fill=(210,180,120),spacing=15,align='center')
    return im

# Download and open
paths={n:dl(n,u) for n,u in SOURCES}
imgs={}
xbiases=[0.45,0.52,0.42,0.50,0.58,0.48]
for i,n in enumerate(['hbb01','hbb02','hbb03','hbb04','hbb05','hbb06']):
    imgs[n]=grade(cover_crop(Image.open(paths[n]),xbias=xbiases[i]))
# Saat Meydanı image: use only upper/side area via upper-biased crop to avoid incident subjects.
saat_raw=Image.open(paths['saat01']).convert('RGB')
# crop upper 58%, then cover crop
top=saat_raw.crop((0,0,saat_raw.width,int(saat_raw.height*0.58)))
imgs['saat01']=grade(cover_crop(top,xbias=0.52,ybias=0.15))

scenes=[]
# 1 opening real street
im=imgs['hbb01'].copy(); d=ImageDraw.Draw(im); stamp(d,'DÖRTYOL // 23:47','KAYIT 001')
im=perspective_text(im,'HATICE',[(740,330),(1000,330),(990,430),(730,430)],size=80,color=(235,214,174),glow=False)
scenes.append(im)
# 2 deeper street + reaction
im=imgs['hbb02'].copy(); d=ImageDraw.Draw(im); stamp(d,'ÇARŞI MERKEZİ','KAYIT 002')
im=perspective_text(im,'HATICE',[(58,510),(430,475),(440,610),(70,640)],size=120)
im=bubble(im,'Bu Hatice kim?',70,1230)
scenes.append(im)
# 3 wet road reflection + reaction
im=imgs['hbb03'].copy(); d=ImageDraw.Draw(im); stamp(d,'DÖRTYOL','KAYIT 003')
im=road_reflection(im,'HATICE',y=1350,alpha=120); im=bubble(im,'Her yerde aynı isim var.',72,1170,'right')
scenes.append(im)
# letter sequence across actual streets
letters='HATICE'
for idx,(n,L) in enumerate(zip(['hbb04','hbb05','hbb06','hbb01','hbb02','hbb03'],letters)):
    im=imgs[n].copy(); d=ImageDraw.Draw(im); stamp(d,f'ÇARŞI // {idx+1:02d}',f'HARF {idx+1}/6')
    im=perspective_text(im,L,[(250,520),(835,490),(820,900),(260,920)],size=320,color=(255,234,190),glow=True,stroke=3)
    scenes.append(im)
# final approach, recent Saat Meydanı neutral upper crop
im=imgs['saat01'].copy(); d=ImageDraw.Draw(im); stamp(d,'SAAT MEYDANI // DÖRTYOL','KAYIT SON')
im=perspective_text(im,'HATICE',[(120,460),(960,460),(940,830),(140,830)],size=230,color=(255,236,194),glow=True,stroke=3)
im=road_reflection(im,'HATICE',y=1340,alpha=105); im=bubble(im,"Saat Meydanı'nda da yazıyor.",55,1110,'right')
scenes.append(im)
# black end cards
scenes.append(card(['Dörtyol bir gece','tek bir ismi merak etti.'],small='KAYIT TAMAMLANDI'))
scenes.append(card(['Ben zaten','cevabı biliyordum.'],small='1.0 sn sessizlik'))
scenes.append(card(['HATICE'],small='DÖRTYOL // 23:47',sub='Bazı isimler şehre yazılmaz.\nŞehir onları hatırlar.'))

for i,im in enumerate(scenes): im.save(FRAMES/f'scene_{i:02d}.jpg',quality=95)
scenes[-1].save(POSTER,quality=95)

# duration design
DURS=[2.5,2.6,2.5,1.35,1.35,1.35,1.35,1.35,1.35,3.5,3.5,2.8,4.0]
clip_paths=[]
for i,dur in enumerate(DURS):
    inp=FRAMES/f'scene_{i:02d}.jpg'; out=CLIPS/f'c_{i:02d}.mp4'; frames=int(dur*FPS)
    if i<10:
        zoom=1.09 if i in (3,4,5,6,7,8) else 1.055
        step=(zoom-1)/max(frames,1)
        # mild travel; alternating pan
        sign=-1 if i%2 else 1
        xexpr=f"iw/2-(iw/zoom/2)+{sign}*sin(on/35)*7"
        vf=f"zoompan=z='min(zoom+{step:.8f},{zoom})':x='{xexpr}':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},eq=contrast=1.03:saturation=1.00,format=yuv420p"
    else:
        step=0.00006; vf=f"zoompan=z='min(zoom+{step},1.018)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p"
    run(['ffmpeg','-y','-loop','1','-i',inp,'-vf',vf,'-t',str(dur),'-r',str(FPS),'-an','-c:v','libx264','-preset','fast','-crf','18',out])
    clip_paths.append(out)
# concatenate with hard match cuts (luxury ad style, no cheesy fades)
concat=WORK/'concat.txt'
concat.write_text(''.join([f"file '{p.resolve()}'\n" for p in clip_paths]))
video=WORK/'video.mp4'
run(['ffmpeg','-y','-f','concat','-safe','0','-i',concat,'-c','copy',video])

# soundtrack base
T=sum(DURS); sr=48000; t=np.linspace(0,T,int(T*sr),endpoint=False); audio=np.zeros_like(t)
audio += 0.025*np.sin(2*np.pi*41*t) + 0.010*np.sin(2*np.pi*82*t)
audio += 0.004*np.sin(2*np.pi*(530+5*np.sin(2*np.pi*t/6))*t)
rng=np.random.default_rng(77); noise=rng.normal(0,1,len(t)); audio += 0.003*noise
# urban distant pulse
for ht in np.arange(1.1,20,1.25):
    dt=t-ht; env=np.exp(-np.maximum(dt,0)*9)*(dt>=0); audio += 0.07*np.sin(2*np.pi*55*dt)*env
# letter ticks synced around beginning of letter run
letter_start=sum(DURS[:3])
for j in range(6):
    ht=letter_start+sum(DURS[3:3+j])+0.15; dt=t-ht
    audio += 0.12*np.sin(2*np.pi*1100*dt)*np.exp(-np.maximum(dt,0)*35)*(dt>=0)
    audio += 0.065*np.sin(2*np.pi*66*dt)*np.exp(-np.maximum(dt,0)*7)*(dt>=0)
# final takeover impact
ht=sum(DURS[:9])+0.25; dt=t-ht; audio += 0.16*np.sin(2*np.pi*48*dt)*np.exp(-np.maximum(dt,0)*3.5)*(dt>=0)
# deliberate near-silence before second black card
sil_start=sum(DURS[:11]); m=(t>sil_start)&(t<sil_start+1.0); audio[m]*=0.03
# outro rise
m=t>(T-5); audio[m]+=0.018*np.sin(2*np.pi*220*t[m])*np.clip((t[m]-(T-5))/5,0,1)
audio*=np.clip(t/0.7,0,1)*np.clip((T-t)/1.0,0,1); audio=np.tanh(audio*2.5)*0.42
pcm=(audio*32767).astype(np.int16); bed=WORK/'bed.wav'
with wave.open(str(bed),'wb') as wf: wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())

# TTS whispers and final narrator, clearly fictional ad voices
voices=[('Bu Hatice kim?',5.0,150,50),('Her yerde aynı isim var.',7.6,165,42),("Saat Meydanı'nda da yazıyor.",21.5,145,48),('Dörtyol bir gece tek bir ismi merak etti.',25.0,128,40),('Ben zaten cevabı biliyordum. Hatice.',29.4,118,35)]
inputs=['-i',str(video),'-i',str(bed)]; filters=[]; labels=['[1:a]']
for k,(txt,delay,speed,pitch) in enumerate(voices):
    wavp=WORK/f'voice{k}.wav'
    run(['espeak-ng','-v','tr','-s',str(speed),'-p',str(pitch),'-w',wavp,txt])
    inputs += ['-i',str(wavp)]
    ms=int(delay*1000); filters.append(f'[{k+2}:a]volume=0.25,highpass=f=110,lowpass=f=4200,aecho=0.7:0.55:65:0.18,adelay={ms}|{ms}[v{k}]'); labels.append(f'[v{k}]')
filter_complex=';'.join(filters+[ ''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:normalize=0[a]' ])
run(['ffmpeg','-y',*inputs,'-filter_complex',filter_complex,'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',OUT])

# Verify
run(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,r_frame_rate','-of','default=noprint_wrappers=1',OUT])
print('DONE',OUT,POSTER)
