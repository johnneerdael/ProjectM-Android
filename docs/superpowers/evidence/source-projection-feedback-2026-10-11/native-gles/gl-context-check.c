#define GL_SILENCE_DEPRECATION
#include <OpenGL/OpenGL.h>
#include <OpenGL/gl3.h>
#include <stdio.h>
int main(void) {
 CGLPixelFormatAttribute attrs[]={kCGLPFAOpenGLProfile,(CGLPixelFormatAttribute)kCGLOGLPVersion_3_2_Core,kCGLPFAAccelerated,(CGLPixelFormatAttribute)0};
 CGLPixelFormatObj format=0;GLint count=0;CGLContextObj context=0;
 CGLError error=CGLChoosePixelFormat(attrs,&format,&count);
 if(error!=kCGLNoError||!format){fprintf(stderr,"CGLChoosePixelFormat failed: %d %s, formats=%d\n",error,CGLErrorString(error),count);return 2;}
 error=CGLCreateContext(format,0,&context);CGLDestroyPixelFormat(format);
 if(error!=kCGLNoError||!context){fprintf(stderr,"CGLCreateContext failed: %d %s\n",error,CGLErrorString(error));return 3;}
 CGLSetCurrentContext(context);printf("renderer=%s\nversion=%s\n",glGetString(GL_RENDERER),glGetString(GL_VERSION));
 CGLSetCurrentContext(0);CGLDestroyContext(context);return 0;
}
