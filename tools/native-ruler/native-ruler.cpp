#include <glad/egl.h>
#include <glad/gles2.h>
#include "ProjectM.hpp"
#include "Audio/PCM.hpp"
#include "vendor/json.hpp"
#include <dlfcn.h>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <vector>
#include <cmath>
#include <stdexcept>
using json=nlohmann::json;
static void* eglLibrary=nullptr;
static void* glLibrary=nullptr;
static GLADapiproc loadEgl(const char* name){return reinterpret_cast<GLADapiproc>(dlsym(eglLibrary,name));}
static GLADapiproc loadGles(const char* name){auto fn=dlsym(glLibrary,name);return fn?reinterpret_cast<GLADapiproc>(fn):reinterpret_cast<GLADapiproc>(eglGetProcAddress(name));}
static void require(bool good,const char* message){if(!good)throw std::runtime_error(message);}
struct Engine:libprojectM::ProjectM{
 mutable std::string failure;
 void PresetSwitchFailedEvent(const std::string& file,const std::string& why)const override{failure=file+": "+why;}
};
int main(int argc,char** argv){try{
 require(argc==9,"usage: native-ruler SWIFTSHADER_DIR PRESET PCM_FLOAT32 OUTPUT_PREFIX FRAME_COUNT WIDTH HEIGHT TEXTURE_DIR");
 std::string dir=argv[1],prefix=argv[4];int frames=std::stoi(argv[5]);require(frames>0&&frames<=600,"bounded frame schedule required");
 eglLibrary=dlopen((dir+"/libswiftshader_libEGL.dylib").c_str(),RTLD_NOW|RTLD_LOCAL);
 glLibrary=dlopen((dir+"/libswiftshader_libGLESv2.dylib").c_str(),RTLD_NOW|RTLD_LOCAL);
 require(eglLibrary&&glLibrary,"SwiftShader dylib loading failed");
 require(gladLoadEGL(EGL_NO_DISPLAY,loadEgl)!=0,"EGL loader failed");
 EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);EGLint major=0,minor=0;
 require(eglInitialize(display,&major,&minor),"EGL initialization failed");
 require(gladLoadEGL(display,loadEgl)!=0,"display EGL loader failed");
 EGLint attrs[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x0040, /* EGL_OPENGL_ES3_BIT_KHR */EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
 EGLConfig config;EGLint count=0;require(eglChooseConfig(display,attrs,&config,1,&count)&&count>0,"GLES3 config failed");
 require(eglBindAPI(EGL_OPENGL_ES_API),"GLES binding failed");
 const int width=std::stoi(argv[6]),height=std::stoi(argv[7]),fps=30;require(width>=16&&height>=16&&width<=1920&&height<=1080,"bounded size required");
 EGLint surfaceAttrs[]={EGL_WIDTH,width,EGL_HEIGHT,height,EGL_NONE};EGLSurface surface=eglCreatePbufferSurface(display,config,surfaceAttrs);
 EGLint contextAttrs[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};EGLContext context=eglCreateContext(display,config,EGL_NO_CONTEXT,contextAttrs);
 require(surface!=EGL_NO_SURFACE&&context!=EGL_NO_CONTEXT&&eglMakeCurrent(display,surface,surface,context),"GLES3 pbuffer context failed");
 require(gladLoadGLES2(loadGles)!=0&&GLAD_GL_ES_VERSION_3_0,"GLES3 entrypoints unavailable");
 std::string renderer=reinterpret_cast<const char*>(glGetString(GL_RENDERER));
 std::string version=reinterpret_cast<const char*>(glGetString(GL_VERSION));
 glViewport(0,0,width,height);glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);glPixelStorei(GL_PACK_ALIGNMENT,1);
 std::ifstream pcm(argv[3],std::ios::binary);require(pcm.good(),"PCM unavailable");
 std::ofstream stats(prefix+".frames.jsonl");require(stats.good(),"Output unavailable");std::vector<float> previous;
 std::ofstream raw(prefix+".rgb.u8",std::ios::binary);require(raw.good(),"Raw output unavailable");
 std::vector<float> input(1470);std::vector<uint8_t> waveform(1470),rgba(width*height*4),rgb(width*height*3);
 {Engine engine;engine.SetWindowSize(width,height);engine.SetMeshSize(48,32);engine.SetLineReferenceSize(width,height);engine.SetLineAntialiasing(false);engine.SetTargetFramesPerSecond(fps);engine.SetPresetLocked(true);engine.SetHardCutEnabled(false);engine.SetEasterEgg(0);engine.SetDirectOutput(true);engine.SetFeedbackDetail(0.f);engine.SetFrameTime(0);engine.SetTexturePaths({argv[8]});engine.LoadPresetFile(argv[2],false);require(engine.failure.empty(),engine.failure.c_str());
 for(int frame=0;frame<frames;++frame){pcm.read(reinterpret_cast<char*>(input.data()),input.size()*sizeof(float));require(pcm.gcount()==static_cast<std::streamsize>(input.size()*sizeof(float)),"Incomplete PCM schedule");
 for(size_t i=0;i<input.size();++i){require(std::isfinite(input[i])&&std::abs(input[i])<=1,"Invalid PCM");waveform[i]=static_cast<uint8_t>(std::clamp(static_cast<int>(std::floor(input[i]*128+128+.5f)),0,255));}
 engine.PCM().Add(waveform.data(),1,waveform.size());engine.SetFrameTime(double(frame+1)/fps);engine.RenderFrame(0);
 glBindFramebuffer(GL_READ_FRAMEBUFFER,0);glReadPixels(0,0,width,height,GL_RGBA,GL_UNSIGNED_BYTE,rgba.data());require(glGetError()==GL_NO_ERROR,"Native renderer/readback GL error");
 for(int y=0;y<height;++y)for(int x=0;x<width;++x)for(int c=0;c<3;++c)rgb[(y*width+x)*3+c]=rgba[((height-1-y)*width+x)*4+c];
 // Displayed statistics only: Rec.709 luma of sRGB-encoded values, HSV saturation, change and global jump.
 std::vector<float> luma(width*height);double lumaSum=0,satSum=0,change=0;
 for(int i=0;i<width*height;++i){float r=rgb[i*3]/255.f,g=rgb[i*3+1]/255.f,b=rgb[i*3+2]/255.f;luma[i]=.2126f*r+.7152f*g+.0722f*b;lumaSum+=luma[i];
  float mx=std::max({r,g,b}),mn=std::min({r,g,b});satSum+=mx>0?(mx-mn)/mx:0;if(!previous.empty())change+=std::abs(luma[i]-previous[i]);}
 auto a=engine.PCM().GetFrameAudioData();
 stats<<json({{"frame",frame},{"mean_luma",lumaSum/(width*height)},{"mean_saturation",satSum/(width*height)},{"mean_abs_luma_change",previous.empty()?json(nullptr):json(change/(width*height))},{"bass",a.bass},{"mid",a.mid},{"treb",a.treb}}).dump()<<'\n';
 previous=luma;raw.write(reinterpret_cast<char*>(rgb.data()),rgb.size());
 if(frame==frames/2||frame==frames-1){std::ofstream thumb(prefix+(frame==frames-1?".last":".mid")+".rgb.u8",std::ios::binary);thumb.write(reinterpret_cast<char*>(rgb.data()),rgb.size());}
 }
 }
 stats.close();raw.close();require(stats.good()&&raw.good(),"Write failure");
 json result={{"status","captured"},{"width",width},{"height",height},{"fps",fps},{"frames",frames},{"renderer",renderer},{"version",version},{"backend","native-macOS-patched-source-GLES-SwiftShader"},{"published_AAR_execution",false},{"scope","Source-matched comparison render, not Android AAR/device certification"},{"audio","synthetic float32 quantized to U8 as CoreBackendRunner"},{"clock","public SetFrameTime"},{"line_reference_size",{width,height}},{"direct_output",true},{"native_trails",false}};
 std::ofstream meta(prefix+".json");meta<<result.dump(2)<<'\n';std::cout<<result.dump()<<'\n';
 eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);eglDestroyContext(display,context);eglDestroySurface(display,surface);eglTerminate(display);return 0;
 }catch(const std::exception& e){std::cerr<<"native-ruler: "<<e.what()<<'\n';return 1;}}
