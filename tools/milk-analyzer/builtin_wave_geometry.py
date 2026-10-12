"""Built-in waveform vertices for projectM modes 0-9 from declared PCM (numpy, no rendering).

Mirrors projectM 4.1.7 ``Waveforms/*.cpp`` and ``WaveformMath::GetVertices``:
waveform samples are in +-128 units, scaled by wave_scale/128 and IIR-smoothed
(s[i] = scale*(1-smoothing)*p[i] + smoothing*s[i-1]), modes build vertices in NDC
(x right, y up) from wave_x/wave_y/wave_mystery/time and the viewport aspect,
and line modes get the 4-tap (-.15, 1.15, 1.15, -.15)/2 midpoint insertion.
The PCM alignment pass (MilkdropWaveAlign) and modes 10-15 are not modelled.
Mono input is copied to both channels, as projectM does for one channel.
"""
import math

import numpy as np

WAVEFORM_SAMPLES=480
NORMALIZED_MYSTERY={0,1,4}
LOOP_MODES={0,1}


def _smooth(points):
    n=len(points)
    if n<2:return points
    below=np.concatenate([[0],np.arange(n-2)]);index=np.arange(n-1)
    above=np.arange(1,n);above2=np.minimum(n-1,np.arange(2,n+1))
    mids=(-.15*points[below]+1.15*points[index]+1.15*points[above]-.15*points[above2])/2
    out=np.empty((2*n-1,2),np.float64);out[0::2]=points;out[1::2]=mids
    return out


def _clip_edges(angle,wave_x,samples):
    """LineBase::ClipWaveformEdges: line endpoints clipped to |x|,|y| <= 1.1."""
    dx,dy=math.cos(angle),math.sin(angle)
    ex=[wave_x*math.cos(angle+1.57)-dx*3,wave_x*math.cos(angle+1.57)+dx*3]
    ey=[wave_x*math.sin(angle+1.57)-dy*3,wave_x*math.sin(angle+1.57)+dy*3]
    for i in range(2):
        for j in range(4):
            t=None
            if j==0 and ex[i]>1.1:t=(1.1-ex[1-i])/(ex[i]-ex[1-i])
            elif j==1 and ex[i]<-1.1:t=(-1.1-ex[1-i])/(ex[i]-ex[1-i])
            elif j==2 and ey[i]>1.1:t=(1.1-ey[1-i])/(ey[i]-ey[1-i])
            elif j==3 and ey[i]<-1.1:t=(-1.1-ey[1-i])/(ey[i]-ey[1-i])
            if t is not None:
                ddx=ex[i]-ex[1-i];ddy=ey[i]-ey[1-i];ex[i]=ex[1-i]+ddx*t;ey[i]=ey[1-i]+ddy*t
    step_x=(ex[1]-ex[0])/samples;step_y=(ey[1]-ey[0])/samples
    angle2=math.atan2(step_y,step_x)
    return ex[0],ey[0],step_x,step_y,math.cos(angle2+1.57),math.sin(angle2+1.57)


def vertices(mode,*,left,right=None,wave_x=.5,wave_y=.5,mystery=0.,scale=1.,smoothing=.75,time=0.,viewport=(480,270)):
    """Return (polylines, is_loop): polylines are (N,2) NDC arrays after midpoint smoothing."""
    mode=int(mode)%16
    if mode>9:raise ValueError('built-in waveform mode %d not modelled'%mode)
    left=np.asarray(left,np.float64)[:WAVEFORM_SAMPLES+64]
    right=left if right is None else np.asarray(right,np.float64)[:WAVEFORM_SAMPLES+64]
    def prepare(data):
        out=np.array(data,np.float64);k=scale/128.
        out[0]*=k
        for i in range(1,len(out)):out[i]=out[i]*k*(1-smoothing)+out[i-1]*smoothing
        return out
    L,R=prepare(left),prepare(right)
    width,height=viewport
    aspect_x=1. if width>height else width/height
    aspect_y=height/width if width>height else 1.
    if mode in NORMALIZED_MYSTERY and (mystery<-1 or mystery>1):
        mystery=mystery*.5+.5;mystery-=math.floor(mystery);mystery=abs(mystery)*2-1
    wx=2*wave_x-1;wy=2*wave_y-1
    lines=[]
    if mode==0:
        n=WAVEFORM_SAMPLES//2;off=(WAVEFORM_SAMPLES-n)//2;i=np.arange(n)
        radius=.5+.4*R[i+off]+mystery;angle=i/n*6.28+time*.2
        head=i<n/10
        mix=.5-.5*np.cos(i/(n*.1)*3.1416)
        radius2=.5+.4*R[np.minimum(i+n+off,len(R)-1)]+mystery
        radius=np.where(head,radius2*(1-mix)+radius*mix,radius)
        lines=[np.stack([radius*np.cos(angle)*aspect_y+wx,radius*np.sin(angle)*aspect_x+wy],-1)]
    elif mode==1:
        n=WAVEFORM_SAMPLES//2;i=np.arange(n)
        radius=.53+.43*R[i]+mystery;angle=L[i+32]*1.57+time*2.3
        lines=[np.stack([radius*np.cos(angle)*aspect_y+wx,radius*np.sin(angle)*aspect_x+wy],-1)]
    elif mode in (2,3):
        i=np.arange(WAVEFORM_SAMPLES)
        lines=[np.stack([R[i]*aspect_y+wx,L[i+32]*aspect_x+wy],-1)]
    elif mode==4:
        n=WAVEFORM_SAMPLES
        if n>width/3:n//=3
        off=(WAVEFORM_SAMPLES-n)//2
        w1=.45+.5*(mystery*.5+.5);w2=1-w1
        pts=np.zeros((n,2))
        for i in range(n):
            x=-1+2*(i/n)+wx+R[i+25+off]*.44;y=L[i+off]*.47+wy
            if i>1:x=x*w2+w1*(pts[i-1,0]*2-pts[i-2,0]);y=y*w2+w1*(pts[i-1,1]*2-pts[i-2,1])
            pts[i]=(x,y)
        lines=[pts]
    elif mode==5:
        i=np.arange(WAVEFORM_SAMPLES);c,s=math.cos(time*.3),math.sin(time*.3)
        x0=R[i]*L[i+32]+L[i]*R[i+32];y0=R[i]*R[i]-L[i+32]*L[i+32]
        lines=[np.stack([(x0*c-y0*s)*aspect_y+wx,(x0*s+y0*c)*aspect_x+wy],-1)]
    else:
        n=WAVEFORM_SAMPLES//2
        if n>width/3:n//=3
        ex,ey,sx,sy,px,py=_clip_edges(1.57*mystery,wx,n)
        off=(WAVEFORM_SAMPLES-n)//2;i=np.arange(n)
        base=np.stack([ex+sx*i,ey+sy*i],-1);perp=np.array([px,py])
        if mode==6:lines=[base+perp*(.25*L[i+off])[:,None]]
        elif mode==7:
            sep=(wy*.5+.5)**2
            lines=[base+perp*(.25*L[i+off]+sep)[:,None],base+perp*(.25*R[i+off]-sep)[:,None]]
        elif mode==8:
            raise ValueError('spectrum waveform mode 8 not modelled')
        else:lines=[base+perp*(.35*L[i+off])[:,None]]
    return [_smooth(p) for p in lines],mode in LOOP_MODES


def reference_windows(path=None):
    """Declared reference PCM windows (uint8, 576 per frame) as +-128 float waveform data."""
    from pathlib import Path
    data=np.load(Path(path) if path else Path(__file__).with_name('fixtures')/'reference-waveform-windows-2026-10-12.npy')
    return (data.astype(np.float64)-128.)
