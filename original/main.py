"""Irina -> olho -> coracao -> Kali Linux, animacao ASCII vertical.
Execute: python main.py --preview  (rapido, 540x960)
         python main.py            (1080x1920, 24 fps)
Opcional: coloque kali.png (logo transparente oficial) na mesma pasta.
"""
import argparse
from pathlib import Path
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CHARS = np.array(list("@#8&%$*+=;:,. "))
FPS = 24
DURATION = 12


def ease(x):
    x = np.clip(x, 0, 1)
    return x*x*(3-2*x)


def font_at(size):
    paths = ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
             "/System/Library/Fonts/Menlo.ttc"]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load_portrait(path, width, height):
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Foto nao encontrada: {path}")
    ih, iw = img.shape[:2]
    # Foto em proporcao vertical, com recorte central para a tela.
    scale = max(width / iw, height / ih)
    img = cv2.resize(img, (int(iw*scale)+2, int(ih*scale)+2))
    x = (img.shape[1]-width)//2
    y = (img.shape[0]-height)//2
    return img[y:y+height, x:x+width]


def logo_mask(width, height):
    """Usa kali.png se presente; caso contrario desenha um dragao estilizado."""
    logo = cv2.imread(str(ROOT / "kali.png"), cv2.IMREAD_UNCHANGED)
    mask = np.zeros((height, width), np.uint8)
    if logo is not None:
        if logo.ndim == 3 and logo.shape[2] == 4:
            raw = logo[:, :, 3]
        else:
            raw = cv2.cvtColor(logo[:, :, :3], cv2.COLOR_BGR2GRAY)
        scale = min(width*.78/raw.shape[1], height*.48/raw.shape[0])
        resized = cv2.resize(raw, (max(1,int(raw.shape[1]*scale)), max(1,int(raw.shape[0]*scale))))
        x, y = (width-resized.shape[1])//2, (height-resized.shape[0])//2
        mask[y:y+resized.shape[0], x:x+resized.shape[1]] = resized
        return mask
    # Curvas grossas estilizadas sugerindo a cabeca, espinha e cauda do dragao.
    pts = np.array([
        [.18,.61],[.25,.48],[.39,.39],[.54,.39],[.68,.46],[.77,.52],
        [.68,.56],[.58,.53],[.47,.49],[.37,.51],[.32,.61],[.40,.67],
        [.53,.67],[.64,.61],[.70,.64],[.61,.73],[.48,.77],[.34,.73],
        [.26,.66],[.21,.74],[.27,.82],[.41,.86],[.58,.83]
    ])
    xy = np.round(pts*np.array([width,height])).astype(np.int32)
    cv2.polylines(mask,[xy],False,255,max(3,width//38),cv2.LINE_AA)
    horns = np.array([[.66,.46],[.71,.36],[.72,.47],[.82,.40],[.76,.53]])
    cv2.polylines(mask,[np.round(horns*[width,height]).astype(np.int32)],False,255,max(2,width//65),cv2.LINE_AA)
    cv2.circle(mask,(int(width*.73),int(height*.51)),max(2,width//100),255,-1)
    return mask


def heart_mask(width, height, t):
    yy, xx = np.mgrid[0:height,0:width].astype(np.float32)
    beat = 1 + .055*math.sin(t*math.pi*4)
    x = (xx-width*.5)/(width*.32*beat)
    y = -(yy-height*.49)/(width*.32*beat)
    v = (x*x+y*y-1)**3-x*x*y**3
    return (v <= 0).astype(np.uint8)*255


def draw_ascii(source, out_w, out_h, cell, phase, t, seed=0):
    """Converte a imagem da fase atual em caracteres luminosos."""
    cw, ch = max(1,out_w//cell), max(1,out_h//int(cell*1.65))
    # Redimensionamento para uma grade de caracteres de proporcao aproximada.
    small = cv2.resize(source,(cw,ch),interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
    canvas = Image.new('RGB',(out_w,out_h),(2,3,8))
    d = ImageDraw.Draw(canvas)
    font = font_at(max(8,int(cell*1.28)))
    rng = np.random.default_rng(seed)
    for iy in range(ch):
        for ix in range(cw):
            val = int(gray[iy,ix])
            if val < 22: continue
            # Textura aleatoria estavel, mas distribuicao segue a luminosidade real.
            if rng.random() > min(1.0, val/135 + .12): continue
            idx = int((255-val)/256*len(CHARS))
            char = CHARS[min(idx,len(CHARS)-1)]
            if char == ' ': char = '.'
            if phase == 'portrait':
                color = (min(255,int(val*1.22)), min(240,int(val*.87)), min(220,int(val*.65)))
            elif phase == 'heart':
                color = (255,min(130,int(val*.27)),min(160,int(val*.38)))
            else:
                color = (min(155,int(val*.38)),min(240,int(val*.78)),255)
            d.text((ix*cell,iy*int(cell*1.65)),str(char),font=font,fill=color)
    return cv2.cvtColor(np.asarray(canvas),cv2.COLOR_RGB2BGR)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--preview',action='store_true',help='Renderiza em 540x960')
    ap.add_argument('--photo',type=Path,default=ROOT/'irina.jpg')
    ap.add_argument('--output',type=Path,default=ROOT/'irina_kali.mp4')
    args=ap.parse_args()
    w,h=(540,960) if args.preview else (1080,1920)
    # A versao full HD usa mais CPU; ajuste o tamanho da celula se necessario.
    cell=9 if args.preview else 15
    portrait=load_portrait(args.photo,w,h)
    dragon=logo_mask(w,h)
    video=cv2.VideoWriter(str(args.output),cv2.VideoWriter_fourcc(*'mp4v'),FPS,(w,h))
    if not video.isOpened(): raise RuntimeError('Nao foi possivel iniciar a gravacao MP4')
    try:
        for n in range(FPS*DURATION):
            t=n/FPS
            if t<3.3:
                # Revelacao, piscada estilizada e zoom progressivo no rosto.
                progress=ease((t-1.5)/1.8)
                zoom=1+progress*.35
                m=cv2.getRotationMatrix2D((w*.50,h*.39),0,zoom)
                frame=cv2.warpAffine(portrait,m,(w,h),borderMode=cv2.BORDER_REFLECT)
                # Piscada sobre ambos os olhos, estimativa para esta foto.
                blink=max(0,1-abs(t-1.55)/.18)
                if blink>0:
                    y=int(h*.37)
                    overlay=frame.copy()
                    cv2.rectangle(overlay,(int(w*.22),y-int(18*blink)),(int(w*.62),y+int(18*blink)),(18,17,20),-1)
                    frame=cv2.addWeighted(overlay,blink*.8,frame,1-blink*.8,0)
                frame=cv2.convertScaleAbs(frame,alpha=min(1, .25+t*.42))
                phase='portrait'
            elif t<5.2:
                # Zoom para olho direito da pessoa, a esquerda na foto.
                z=1.35+ease((t-3.3)/1.9)*7.0
                cx,cy=w*.32,h*.37
                m=cv2.getRotationMatrix2D((cx,cy),0,z)
                m[0,2]+=w*.5-cx; m[1,2]+=h*.5-cy
                frame=cv2.warpAffine(portrait,m,(w,h),borderMode=cv2.BORDER_REFLECT)
                phase='portrait'
            elif t<7.7:
                heart=heart_mask(w,h,t)
                frame=np.zeros((h,w,3),np.uint8)
                frame[:,:,2]=heart
                frame[:,:,1]=(heart*.22).astype(np.uint8)
                # Halo suave.
                blur=cv2.GaussianBlur(heart,(0,0),max(8,w//35))
                frame[:,:,2]=np.maximum(frame[:,:,2],(blur*.4).astype(np.uint8))
                phase='heart'
            else:
                p=ease((t-7.7)/2.0)
                frame=np.zeros((h,w,3),np.uint8)
                # Dissolve o coracao e faz aparecer o simbolo do Kali.
                if p<1:
                    old=heart_mask(w,h,t)
                    frame[:,:,2]=(old*(1-p)).astype(np.uint8)
                frame[:,:,0]=np.maximum(frame[:,:,0],(dragon*p).astype(np.uint8))
                frame[:,:,1]=np.maximum(frame[:,:,1],(dragon*p*.66).astype(np.uint8))
                frame[:,:,2]=np.maximum(frame[:,:,2],(dragon*p*.17).astype(np.uint8))
                phase='kali'
            ascii_frame=draw_ascii(frame,w,h,cell,phase,t,seed=n//3)
            # Particulas digitais esparsas e deterministicas.
            rng=np.random.default_rng(8000+n//2)
            for _ in range(70 if args.preview else 140):
                x=int(rng.integers(0,w)); y=int(rng.integers(0,h))
                c=(110,55,25) if t<5.2 else ((55,50,150) if t<7.7 else (180,110,35))
                cv2.circle(ascii_frame,(x,y),1,c,-1)
            if t>9.7:
                cv2.putText(ascii_frame,'KALI LINUX',(int(w*.25),int(h*.85)),cv2.FONT_HERSHEY_SIMPLEX,w/900,(255,180,75),max(1,w//550),cv2.LINE_AA)
            video.write(ascii_frame)
            if n%FPS==0: print(f'Gerando: {int(t)}s / {DURATION}s',flush=True)
    finally:
        video.release()
    print('Video salvo em:',args.output)

if __name__=='__main__': main()
