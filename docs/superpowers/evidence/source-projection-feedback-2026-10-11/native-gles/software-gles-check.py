import ctypes as C,json,sys
from pathlib import Path
folder=Path('/Users/jneerdael/Library/Android/sdk/emulator/lib64/gles_angle')
egl=C.CDLL(str(folder/'libswiftshader_libEGL.dylib'))
gl=C.CDLL(str(folder/'libswiftshader_libGLESv2.dylib'))
def function(lib,name,restype,*args):
 f=getattr(lib,name);f.restype=restype;f.argtypes=args;return f
get_display=function(egl,'eglGetDisplay',C.c_void_p,C.c_void_p)
initialize=function(egl,'eglInitialize',C.c_uint,C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int))
get_error=function(egl,'eglGetError',C.c_uint)
choose=function(egl,'eglChooseConfig',C.c_uint,C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_void_p),C.c_int,C.POINTER(C.c_int))
bind_api=function(egl,'eglBindAPI',C.c_uint,C.c_uint)
pbuffer=function(egl,'eglCreatePbufferSurface',C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_int))
create=function(egl,'eglCreateContext',C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_int))
current=function(egl,'eglMakeCurrent',C.c_uint,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
def check(ok,stage):
 if not ok:raise RuntimeError(stage+' EGL error '+hex(get_error()))
display=get_display(None);check(display,'get display')
major=C.c_int();minor=C.c_int();check(initialize(display,C.byref(major),C.byref(minor)),'initialize')
attrs=(C.c_int*13)(0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038)
config=C.c_void_p();count=C.c_int();check(choose(display,attrs,C.byref(config),1,C.byref(count)) and count.value>0,'choose GLES3 pbuffer')
check(bind_api(0x30A0),'bind GLES')
surface=pbuffer(display,config,(C.c_int*5)(0x3057,8,0x3056,8,0x3038));check(surface,'pbuffer')
context=create(display,config,None,(C.c_int*3)(0x3098,3,0x3038));check(context,'context')
check(current(display,surface,surface,context),'make current')
get_string=function(gl,'glGetString',C.c_char_p,C.c_uint)
clear_colour=function(gl,'glClearColor',None,C.c_float,C.c_float,C.c_float,C.c_float)
clear=function(gl,'glClear',None,C.c_uint)
read=function(gl,'glReadPixels',None,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p)
error=function(gl,'glGetError',C.c_uint)
clear_colour(.2,.4,.6,1.);clear(0x4000);pixels=(C.c_ubyte*256)();read(0,0,8,8,0x1908,0x1401,pixels)
result={'renderer':get_string(0x1F01).decode(),'version':get_string(0x1F02).decode(),'EGL':[major.value,minor.value],'first_pixel':list(pixels[:4]),'gl_error':error(),'preset_rendered':False,'scope':'Software GLES infrastructure check only'}
print(json.dumps(result),flush=True)
check(result['gl_error']==0 and result['first_pixel']==[51,102,153,255],'clear/readback control')
