"""Source-derived warp mesh and texture operators for the pinned renderer.

No renderer, reference images or preset ranking is used. Coordinates/fields are
explicit inputs. These operators preserve the vertex operation order, native
triangle diagonal, texel-centre sampling and addressing. They are building blocks
for the full pipeline, not a complete preset appearance predictor.
"""
import numpy as np
import ctypes
import platform
from functools import lru_cache

PORTABLE_PROFILE='portable'
APPLE_NAN_MESH_PROFILE='apple-m4pro-gl41-nan-mesh-v1'
LEGACY_ROTATION='legacy-numpy-float-trig-v1'
CPU_ROTATION='projectmtv-core-2.3.17-cpu-float-trig-v1'


@lru_cache(maxsize=1)
def _float_trig():
    library=ctypes.CDLL(None)
    try:
        functions=[library.sinf,library.cosf]
    except AttributeError as error:
        raise ValueError('CPU float rotation requires available sinf/cosf') from error
    for function in functions:
        function.argtypes=[ctypes.c_float]
        function.restype=ctypes.c_float
    return functions


@lru_cache(maxsize=1)
def _float_pow():
    try:function=ctypes.CDLL(None).powf
    except AttributeError as error:raise ValueError('CPU zoom power requires available powf') from error
    function.argtypes=[ctypes.c_float,ctypes.c_float]
    function.restype=ctypes.c_float
    return function


def cpu_float_power(base,exponent):
    """Host float power after narrowing, retaining IEEE domain failures."""
    a,b=np.broadcast_arrays(np.asarray(base,np.float32),np.asarray(exponent,np.float32))
    function=_float_pow()
    return np.asarray([function(float(x),float(y)) for x,y in zip(a.flat,b.flat)],np.float32).reshape(a.shape)


def zoom_power_producer(policy):
    from engine_profiles import LEGACY_ZOOM,CORE_2315_ZOOM,CORE_2327_ZOOM
    if policy not in {LEGACY_ZOOM,CORE_2315_ZOOM,CORE_2327_ZOOM}:
        raise ValueError('unsupported warp zoom policy')
    result={'policy':policy,'positive_base_producer':'NumPy float32 power',
            'numpy_version':np.__version__,'android_bit_parity_verified':False}
    if policy==CORE_2327_ZOOM:
        _float_pow()
        result.update(negative_base_producer='ctypes.CDLL(None) host powf after float32 narrowing',
                      platform=platform.platform(),python_version=platform.python_version())
    return result


def rotation_pair(angle,policy=LEGACY_ROTATION):
    values=_finite(angle,'rotation')
    if policy==LEGACY_ROTATION:return np.sin(values),np.cos(values)
    if policy!=CPU_ROTATION:raise ValueError('unsupported warp rotation policy')
    sine,cosine=_float_trig()
    return tuple(np.asarray([function(float(v)) for v in values.flat],np.float32).reshape(values.shape)
                 for function in (sine,cosine))


def rotation_producer(policy):
    if policy==LEGACY_ROTATION:return {'policy':policy,'producer':'NumPy float32 trigonometry','numpy_version':np.__version__}
    if policy!=CPU_ROTATION:raise ValueError('unsupported warp rotation policy')
    _float_trig()
    return {'policy':policy,'producer':'ctypes.CDLL(None) host sinf/cosf',
            'platform':platform.platform(),'python_version':platform.python_version(),
            'android_bit_parity_verified':False}


def _runtime_profile(profile):
    if profile not in (PORTABLE_PROFILE,APPLE_NAN_MESH_PROFILE):
        raise ValueError('unsupported spatial runtime profile')


def _finite(value, name):
    result=np.asarray(value,dtype=np.float32)
    if not np.all(np.isfinite(result)):
        raise ValueError(f'nonfinite spatial input: {name}')
    return result


def mesh_inputs(grid_x:int,grid_y:int,*,aspect_x:float,aspect_y:float,legacy_angle_seam=False)->dict:
    if type(legacy_angle_seam) is not bool:raise ValueError('boolean legacy angle seam required')
    if any(type(n) is not int or n<8 or n>400 or n%2 for n in (grid_x,grid_y)):
        raise ValueError('native mesh requires even grid dimensions from8to400')
    if not np.isfinite(aspect_x) or not np.isfinite(aspect_y) or min(aspect_x,aspect_y)<=0:
        raise ValueError('positive finite aspect factors required')
    px=np.arange(grid_x+1,dtype=np.float32)/np.float32(grid_x)*2-1
    py=np.arange(grid_y+1,dtype=np.float32)/np.float32(grid_y)*2-1
    x,y=np.meshgrid(px,py)
    ax=x*np.float32(aspect_x);ay=y*np.float32(aspect_y)
    angle=np.arctan2(ay,ax);angle[grid_y//2,grid_x//2]=0
    equation_ang=np.where((x<0)&(y==0),angle,-angle) if legacy_angle_seam else -angle
    return {'position':np.stack((x,y),axis=-1),'radius':np.hypot(ax,ay),
            'angle':angle,'equation_ang':equation_ang,'equation_x':ax*.5+.5,
            'equation_y':ay*.5+.5}


def warp_vertex_uv(position,*,aspect_x=1,aspect_y=1,zoom=1,zoomexp=1,
                   sx=1,sy=1,cx=.5,cy=.5,rot=0,dx=0,dy=0,warp=0,
                   time=0,warp_anim_speed=1,warp_scale=1,numeric_profile=PORTABLE_PROFILE,
                   zoom_policy='legacy-glsl-pow-v1',rotation_policy=LEGACY_ROTATION,
                   legacy_warp_policy='legacy-custom-shared-warp-v1'):
    """Evaluate PresetWarpVertexShader in its original float32 operation order.

    Parameters can be scalar or per-vertex fields matching position's leading
    dimensions. This is the vertex result; interpolate the finished UV values
    over native triangles, rather than re-evaluating nonlinear transforms per
    display pixel. Portable mode leaves invalid numeric domains unresolved.
    The explicit Apple profile retains only the observed zero-stretch NaN case
    for interpolation; it rejects infinity and unrelated numeric failures.
    """
    _runtime_profile(numeric_profile)
    from engine_profiles import LEGACY_WARP,CORE_2331_LEGACY_WARP
    if legacy_warp_policy not in {LEGACY_WARP,CORE_2331_LEGACY_WARP}:raise ValueError('unsupported legacy warp policy')
    from engine_profiles import LEGACY_ZOOM,CORE_2315_ZOOM,CORE_2327_ZOOM
    if zoom_policy not in {LEGACY_ZOOM,CORE_2315_ZOOM,CORE_2327_ZOOM}:raise ValueError('unsupported warp zoom policy')
    if rotation_policy not in (LEGACY_ROTATION,CPU_ROTATION):raise ValueError('unsupported warp rotation policy')
    p=_finite(position,'position')
    if p.shape[-1:]!=(2,):raise ValueError('position requires two components')
    names=('aspect_x','aspect_y','zoom','zoomexp','sx','sy','cx','cy','rot','dx','dy',
           'warp','time','warp_anim_speed','warp_scale')
    values=(aspect_x,aspect_y,zoom,zoomexp,sx,sy,cx,cy,rot,dx,dy,warp,time,warp_anim_speed,warp_scale)
    a={name:_finite(value,name) for name,value in zip(names,values)}
    if np.any(a['aspect_x']<=0) or np.any(a['aspect_y']<=0):raise ValueError('positive aspect required')
    zero_stretch=(a['sx']==0)|(a['sy']==0)
    if np.any(a['warp_scale']==0) or (np.any(zero_stretch) and numeric_profile==PORTABLE_PROFILE):
        raise ValueError('zero spatial divisor')
    if np.any(zero_stretch):
        # Establish that zero stretch is the only new numeric domain. The
        # observed profile does not authorize unrelated invalid arithmetic.
        safe={key:value for key,value in a.items()}
        safe['sx']=np.where(a['sx']==0,1,a['sx']);safe['sy']=np.where(a['sy']==0,1,a['sy'])
        warp_vertex_uv(p,**safe,zoom_policy=zoom_policy,rotation_policy=rotation_policy,legacy_warp_policy=legacy_warp_policy)
    x,y=p[...,0],p[...,1]
    with np.errstate(all='ignore'):
        radius=np.hypot(x*a['aspect_x'],y*a['aspect_y'])
        radial_exponent=radius*2-1
        negative_cpu=(a['zoom']<0)&(zoom_policy==CORE_2327_ZOOM)
        if np.any(((a['zoomexp']<0)|((a['zoomexp']==0)&(radial_exponent<=0)))&~negative_cpu):
            raise ValueError('unresolved warp power domain')
        zoom_exponent=np.power(a['zoomexp'],radial_exponent)
        signed=(a['zoom']<0)&(a['zoomexp']==1)&(zoom_policy in {CORE_2315_ZOOM,CORE_2327_ZOOM})
        if np.any((a['zoom']<0)&~signed&~negative_cpu) or np.any((a['zoom']==0)&(zoom_exponent<=0)):
            raise ValueError('unresolved warp power domain')
        effective_zoom=np.where(signed|negative_cpu,1,np.power(np.where(signed|negative_cpu,1,a['zoom']),zoom_exponent))
        if np.any(negative_cpu):
            cpu_exponent=cpu_float_power(a['zoomexp'],radial_exponent)
            negative_result=cpu_float_power(a['zoom'],cpu_exponent)
            effective_zoom=np.where(negative_cpu,negative_result,effective_zoom)
        effective_zoom=np.where(signed,a['zoom'],effective_zoom)
        inverse_zoom=np.float32(1)/effective_zoom
        u=x*a['aspect_x']*.5*inverse_zoom+.5
        v=y*a['aspect_y']*.5*inverse_zoom+.5
        u=(u-a['cx'])/a['sx']+a['cx'];v=(v-a['cy'])/a['sy']+a['cy']
        wt=a['time']*a['warp_anim_speed'];ws=np.float32(1)/a['warp_scale']
        f0=np.float32(11.68)+4*np.cos(wt*np.float32(1.413)+10)
        f1=np.float32(8.77)+3*np.cos(wt*np.float32(1.113)+7)
        f2=np.float32(10.54)+3*np.cos(wt*np.float32(1.233)+3)
        f3=np.float32(11.49)+4*np.cos(wt*np.float32(.933)+5)
        oscillator_y=-y if legacy_warp_policy==CORE_2331_LEGACY_WARP else y
        u+=a['warp']*np.float32(.0035)*np.sin(wt*np.float32(.333)+ws*(x*f0-oscillator_y*f3))
        v+=a['warp']*np.float32(.0035)*np.cos(wt*np.float32(.375)-ws*(x*f2+oscillator_y*f1))
        u+=a['warp']*np.float32(.0035)*np.cos(wt*np.float32(.753)-ws*(x*f1-oscillator_y*f2))
        v+=a['warp']*np.float32(.0035)*np.sin(wt*np.float32(.825)+ws*(x*f0+oscillator_y*f3))
        u2=u-a['cx'];v2=v-a['cy'];sin,cos=rotation_pair(a['rot'],rotation_policy)
        u=u2*cos-v2*sin+a['cx'];v=u2*sin+v2*cos+a['cy']
        u-=a['dx'];v-=a['dy']
        inverse_aspect_x=np.float32(1)/a['aspect_x']
        inverse_aspect_y=np.float32(1)/a['aspect_y']
        u=(u-.5)*inverse_aspect_x+.5;v=(v-.5)*inverse_aspect_y+.5
        result=np.stack((u,v),axis=-1)
    if not np.all(np.isfinite(result)):
        bad=np.any(~np.isfinite(result),axis=-1)
        if numeric_profile!=APPLE_NAN_MESH_PROFILE or np.any(np.isinf(result)) or np.any(bad&~zero_stretch):
            raise ValueError('unresolved warp numeric domain')
    return result


def interpolate_mesh(vertex_values,original_uv,*,numeric_profile=PORTABLE_PROFILE,raster_subpixel_bits=None,viewport=None,diagonal='bc'):
    """Interpolate native triangles with clip w=1.

    The opt-in Apple NaN rule is supported by direct float readback of the
    pinned mesh and full native comparisons for two zero-stretch presets.
    It does not establish portable or Android nonfinite interpolation behavior.
    """
    _runtime_profile(numeric_profile)
    if diagonal not in {'bc','ad'}:raise ValueError('unsupported mesh diagonal')
    if raster_subpixel_bits is not None:
        if type(raster_subpixel_bits) is not int or not 4<=raster_subpixel_bits<=16:
            raise ValueError('supported explicit raster subpixel bits required (4..16)')
        if not isinstance(viewport,(tuple,list)) or len(viewport)!=2 or any(type(n) is not int or n<=0 for n in viewport):
            raise ValueError('explicit positive integer raster viewport required')
    if numeric_profile==APPLE_NAN_MESH_PROFILE:
        values=np.asarray(vertex_values,dtype=np.float32)
        if values.ndim!=3 or values.shape[-1]!=2 or np.any(np.isinf(values)):
            raise ValueError('observed NaN profile requires two-component UV mesh without infinity')
        missing=np.isnan(values)
        finite=interpolate_mesh(np.where(missing,0,values),original_uv,raster_subpixel_bits=raster_subpixel_bits,viewport=viewport,diagonal=diagonal)
        support=interpolate_mesh(missing.astype(np.float32),original_uv,raster_subpixel_bits=raster_subpixel_bits,viewport=viewport,diagonal=diagonal)>0
        return np.where(support,np.finfo(np.float32).max,finite)
    values=_finite(vertex_values,'mesh values');uv=_finite(original_uv,'original UV')
    if values.ndim<2 or min(values.shape[:2])<2 or uv.shape[-1:]!=(2,):
        raise ValueError('mesh values and two-component UV required')
    if np.any((uv<0)|(uv>1)):raise ValueError('mesh query outside viewport')
    ny,nx=values.shape[0]-1,values.shape[1]-1
    if raster_subpixel_bits is None:
        q=uv*np.array([nx,ny],dtype=np.float32)
        cell=np.minimum(np.floor(q).astype(np.int64),[nx-1,ny-1])
        fraction=q-cell;fx,fy=fraction[...,0].astype(np.float32),fraction[...,1].astype(np.float32)
    else:
        cells=[];fractions=[];scale=2**raster_subpixel_bits
        for i,(count,extent) in enumerate(zip((nx,ny),viewport)):
            clip=np.arange(count+1,dtype=np.float32)/np.float32(count)*2-1
            axis=np.rint((clip*.5+.5)*extent*scale)/(extent*scale)
            widths=np.diff(axis);valid=np.flatnonzero(widths>0)
            if not len(valid):raise ValueError('raster mesh axis collapsed')
            indices=np.clip(np.searchsorted(axis,uv[...,i],side='right')-1,0,count-1)
            # Degenerate boundary cells cover no fragments. Use the adjacent
            # nonzero interval for endpoint queries; GPU seam ties stay unverified.
            fallback=valid[np.clip(np.searchsorted(valid,indices,side='right')-1,0,len(valid)-1)]
            indices=np.where(widths[indices]>0,indices,fallback)
            cells.append(indices);fractions.append((uv[...,i]-axis[indices])/widths[indices])
        cell=np.stack(cells,axis=-1);fx,fy=fractions
    x,y=cell[...,0],cell[...,1]
    a,b,c,d=values[y,x],values[y,x+1],values[y+1,x],values[y+1,x+1]
    extra=(None,)*(values.ndim-2)
    fx=fx[(...,)+extra];fy=fy[(...,)+extra]
    if diagonal=='ad':
        first=a+(b-a)*fx+(d-b)*fy
        second=a+(d-c)*fx+(c-a)*fy
        return np.where(fx>=fy,first,second)
    first=a+(b-a)*fx+(c-a)*fy
    second=d+(c-d)*(1-fx)+(b-d)*(1-fy)
    return np.where(fx+fy<=1,first,second)


def sample2d(texture,uv,*,wrap:bool,linear:bool,origin:str):
    """Sample explicit top-row-first fields, with a declared coordinate origin.

    `bottom` matches normalized OpenGL UV on the given texture. `top` is useful
    for a logical main-feedback field after composing its native vertical flip
    with OpenGL sampling. Do not apply an additional flip implicitly.
    """
    field=_finite(texture,'texture');coords=_finite(uv,'sample UV')
    if field.ndim not in (2,3) or min(field.shape[:2])<=0 or coords.shape[-1:]!=(2,):
        raise ValueError('2D field and two-component UV required')
    if origin not in {'top','bottom'}:raise ValueError('explicit top/bottom origin required')
    height,width=field.shape[:2]
    coords=np.mod(coords,1) if wrap else np.clip(coords,0,1)
    q=coords*np.array([width,height],dtype=np.float32)
    def fetch(x,y):
        x=np.mod(x,width) if wrap else np.clip(x,0,width-1)
        y=np.mod(y,height) if wrap else np.clip(y,0,height-1)
        if origin=='bottom':y=height-1-y
        return field[y,x]
    if not linear:
        index=np.floor(q).astype(np.int64)
        return fetch(index[...,0],index[...,1])
    q-=np.float32(.5)
    # Same bilinear rule in scipy's C map_coordinates (wrap: grid-wrap; clamp: nearest edge).
    from scipy import ndimage
    source=field[::-1] if origin=='bottom' else field
    planes=source.reshape(height,width,-1);points=q.reshape(-1,2)
    mode='grid-wrap' if wrap else 'nearest'
    out=np.stack([ndimage.map_coordinates(planes[...,c],[points[:,1],points[:,0]],order=1,mode=mode,prefilter=False)
                  for c in range(planes.shape[2])],axis=-1)
    return out.reshape(q.shape[:-1]+field.shape[2:]).astype(np.float32)


def sample3d(volume,uvw,*,wrap:bool,linear:bool):
    """Sample native volume upload layout [z,w; y,v; x,u; optional channels].

    Index zero in each axis corresponds to normalized UVW zero. This is raw
    generated texture storage, not a captured top-origin framebuffer image.
    """
    field=_finite(volume,'volume');coords=_finite(uvw,'volume UVW')
    if field.ndim not in (3,4) or min(field.shape[:3])<=0 or coords.shape[-1:]!=(3,):
        raise ValueError('3D volume and three-component UVW required')
    depth,height,width=field.shape[:3]
    coords=np.mod(coords,1) if wrap else np.clip(coords,0,1)
    q=coords*np.array([width,height,depth],dtype=np.float32)
    def fetch(x,y,z):
        x=np.mod(x,width) if wrap else np.clip(x,0,width-1)
        y=np.mod(y,height) if wrap else np.clip(y,0,height-1)
        z=np.mod(z,depth) if wrap else np.clip(z,0,depth-1)
        return field[z,y,x]
    if not linear:
        index=np.floor(q).astype(np.int64)
        return fetch(index[...,0],index[...,1],index[...,2])
    q-=np.float32(.5);index=np.floor(q).astype(np.int64);fraction=(q-index).astype(np.float32)
    x,y,z=index[...,0],index[...,1],index[...,2]
    result=np.zeros(coords.shape[:-1]+field.shape[3:],dtype=np.float32)
    for dz in (0,1):
        for dy in (0,1):
            for dx in (0,1):
                weight=(fraction[...,0] if dx else 1-fraction[...,0])
                weight=weight*(fraction[...,1] if dy else 1-fraction[...,1])
                weight=weight*(fraction[...,2] if dz else 1-fraction[...,2])
                if field.ndim==4:weight=weight[...,None]
                result+=fetch(x+dx,y+dy,z+dz)*weight
    return result
