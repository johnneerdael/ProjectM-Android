#include "gl_context.hpp"
#include <MilkdropPreset/Waveform.hpp>
#include <MilkdropPreset/GeometryTargets.hpp>
#include <Renderer/Framebuffer.hpp>
#include <Renderer/ShaderCache.hpp>
#include <algorithm>
#include <MilkdropPreset/Waveforms/Circle.hpp>
#include <MilkdropPreset/Waveforms/XYOscillationSpiral.hpp>
#include <MilkdropPreset/Waveforms/Line.hpp>
#include <MilkdropPreset/PerFrameContext.hpp>
#include <MilkdropPreset/PresetState.hpp>
#include <MilkdropPreset/LineGeometry.hpp>
#include <cmath>
#include <iostream>
#include <array>
#include <stdexcept>
using namespace libprojectM::MilkdropPreset;
using libprojectM::Renderer::ColoredPoint;
using libprojectM::Renderer::LineBatch;
using Point=libprojectM::Renderer::Point;
static int failures=0;
static void Check(bool value,const std::string& why){if(!value){++failures;std::cerr<<"FAIL "<<why<<'\n';}}
class ObserveCircle:public Waveforms::Circle{
public:const VertexList& Raw()const{return m_wave1Vertices;} int Count()const{return m_samples;}
};
static bool Near(const Point&a,const Point&b){return std::abs(a.X()-b.X())<2e-6f&&std::abs(a.Y()-b.Y())<2e-6f;}
// Independent source-stage oracle: original milkdropfs.cpp circle case and
// SmoothWave formula. Projection is tested before original final Y reversal.
static std::vector<Point> OriginalRaw(const PresetState& state,float mystery,float wx,float wy){
 constexpr int n=240,offset=120;std::array<float,480> pcm{};
 const float scale=state.waveScale/128;pcm[0]=state.audioData.waveformRight[0]*scale;
 for(int i=1;i<480;++i)pcm[i]=state.audioData.waveformRight[i]*scale*(1-state.waveSmoothing)+pcm[i-1]*state.waveSmoothing;
 float ax=1,ay=1;if(state.renderContext.viewportSizeX>state.renderContext.viewportSizeY)ay=float(state.renderContext.viewportSizeY)/state.renderContext.viewportSizeX;else ax=float(state.renderContext.viewportSizeX)/state.renderContext.viewportSizeY;
 std::vector<Point> raw;for(int i=0;i<n;++i){float radius=.5f+.4f*pcm[i+offset]+mystery;
 if(i<n/10){float mix=float(i)/(n*.1f);mix=.5f-.5f*cosf(mix*3.1416f);const float second=.5f+.4f*pcm[i+n+offset]+mystery;radius=second*(1-mix)+radius*mix;}
 float angle=float(i)*(1.f/float(n-1))*6.28f+state.renderContext.time*.2f;
 raw.emplace_back(radius*cosf(angle)*ay+wx,radius*sinf(angle)*ax+wy);
 }raw.push_back(raw.front());return raw;
}
static std::vector<Point> OriginalSmooth(const std::vector<Point>& raw){std::vector<Point> out;size_t below=0;for(size_t i=0;i+1<raw.size();++i){const size_t above=i+1,above2=std::min(i+2,raw.size()-1);out.push_back(raw[i]);out.emplace_back((-.15f*raw[below].X()+1.15f*raw[i].X()+1.15f*raw[above].X()-.15f*raw[above2].X())*.5f,(-.15f*raw[below].Y()+1.15f*raw[i].Y()+1.15f*raw[above].Y()-.15f*raw[above2].Y())*.5f);below=i;}out.push_back(raw.back());return out;}
static void Density(){
 for(const auto dims:{std::array<int,5>{256,144,0,0,169},{3840,2160,1024,768,479},{3840,2160,0,0,479}}){
 PresetState state;state.renderContext.viewportSizeX=dims[0];state.renderContext.viewportSizeY=dims[1];state.renderContext.lineReferenceWidth=dims[2];state.renderContext.lineReferenceHeight=dims[3];
 PerFrameContext frame(state.globalMemory,&state.globalRegisters);frame.RegisterBuiltinVariables();frame.LoadStateVariables(state);Waveforms::Line line;
 Check(line.GetVertices(state,frame)[0].size()==size_t(dims[4]),"source-correct reference sample-density policy");
 }
}
static void Control(int width,int height,int refw,int refh,float time,float mystery,float smoothing,bool audio){
 PresetState state;state.audioData={};state.renderContext.viewportSizeX=width;state.renderContext.viewportSizeY=height;
 state.renderContext.lineReferenceWidth=refw;state.renderContext.lineReferenceHeight=refh;
 state.renderContext.time=time;state.waveScale=128;state.waveSmoothing=smoothing;
 state.waveX=.5f;state.waveY=.5f;state.waveParam=mystery;
 if(audio)for(int i=0;i<480;++i){state.audioData.waveformRight[i]=.2f*cosf(i*.07f);state.audioData.waveformLeft[i]=.3f*sinf(i*.11f);}
 PerFrameContext frame(state.globalMemory,&state.globalRegisters);frame.RegisterBuiltinVariables();frame.LoadStateVariables(state);
 ObserveCircle circle;const auto waves=circle.GetVertices(state,frame);
 const auto expected=OriginalRaw(state,mystery,2*state.waveX-1,2*state.waveY-1);const auto smooth=OriginalSmooth(expected);
 const std::string label=std::to_string(width)+"x"+std::to_string(height)+" time="+std::to_string(time)+" audio="+std::to_string(audio);
 Check(circle.Count()==241&&circle.Raw().size()==241,label+" pre-smoothing closure count");
 Check(waves[0].size()==481&&waves[1].empty(),label+" smoothed closure count");
 Check(!circle.IsLoop(),label+" explicit endpoint must draw as strip");
 Check(Near(circle.Raw()[120],expected[120]),label+" point120 denominator239");
 if(circle.Raw().size()==expected.size())for(size_t i=0;i<expected.size();++i)Check(Near(circle.Raw()[i],expected[i]),label+" raw point "+std::to_string(i));
 if(waves[0].size()==smooth.size())for(size_t i=0;i<smooth.size();++i)Check(Near(waves[0][i],smooth[i]),label+" smoothed point "+std::to_string(i));
 Check(circle.Raw().front().X()==circle.Raw().back().X()&&circle.Raw().front().Y()==circle.Raw().back().Y(),label+" exact raw duplicate");
 Check(waves[0].front().X()==waves[0].back().X()&&waves[0].front().Y()==waves[0].back().Y(),label+" exact smoothed duplicate");
 for(const auto&point:waves[0])Check(std::isfinite(point.X())&&std::isfinite(point.Y()),label+" finite geometry");
 std::vector<ColoredPoint> colored;for(const auto&p:waves[0])colored.push_back({p.X(),p.Y(),1,0,0,1});LineBatch batch;
 const auto strip=batch.Append(colored.data(),colored.size(),circle.IsLoop());Check(strip.segments==480,label+" Native strip segment count");
 // One production math producer supplies both targets; repeated calculation is
 // deterministic and does not write shared equation/RNG registers.
 state.globalRegisters[0]=17;const auto again=circle.GetVertices(state,frame);
 Check(state.globalRegisters[0]==17,label+" changed equation registers");
 Check(again[0].size()==waves[0].size(),label+" repeat changed vertex count");for(size_t i=0;i<waves[0].size();++i)Check(Near(again[0][i],waves[0][i]),label+" repeat changed geometry");
 if(width==256&&height==256&&time==0&&!audio&&mystery==0){
 const auto&p=circle.Raw()[120];std::cout<<"raw120="<<p.X()<<","<<p.Y()<<" count="<<circle.Count()<<" smoothed="<<waves[0].size()<<'\n';}
}
// Observe production authored submission and Native prepared replay.
static PFNGLDRAWELEMENTSPROC realElements;
static PFNGLDRAWARRAYSINSTANCEDPROC realInstanced;
static std::vector<std::pair<GLenum,int>> draws;
static void Elements(GLenum primitive,GLsizei count,GLenum type,const void* indices){
 draws.emplace_back(primitive,count);realElements(primitive,count,type,indices);
}
static void Instanced(GLenum primitive,GLint first,GLsizei count,GLsizei instances){
 draws.emplace_back(primitive,instances);realInstanced(primitive,first,count,instances);
}
static void Render(libprojectM::Renderer::ShaderCache& cache){
 using namespace libprojectM::Renderer;
 realElements=glad_glDrawElements;realInstanced=glad_glDrawArraysInstanced;
 glad_glDrawElements=Elements;glad_glDrawArraysInstanced=Instanced;
 for(bool dots:{false,true})for(bool thick:{false,true}){
  PresetState state;state.audioData={};auto& rc=state.renderContext;rc.shaderCache=&cache;state.LoadShaders();
  rc.viewportSizeX=rc.viewportSizeY=128;rc.lineReferenceWidth=rc.lineReferenceHeight=64;
  rc.aspectX=rc.aspectY=rc.invAspectX=rc.invAspectY=1;
  state.waveMode=0;state.waveAlpha=1;state.waveR=1;state.waveG=state.waveB=0;
  state.waveDots=dots;state.waveThick=thick;state.waveX=state.waveY=.5;state.waveParam=-.1;
  PerFrameContext frame(state.globalMemory,&state.globalRegisters);frame.RegisterBuiltinVariables();frame.LoadStateVariables(state);
  Framebuffer canvas(1),native(1);canvas.CreateColorAttachment(0,0,GL_RGBA8,GL_RGBA,GL_UNSIGNED_BYTE);
  native.CreateColorAttachment(0,0,GL_RGBA8,GL_RGBA,GL_UNSIGNED_BYTE);canvas.SetSize(64,64);native.SetSize(128,128);
  GeometryTargets targets(state,canvas,0,64,64,{},native,0);
  native.Bind(0);glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
  targets.Authored();glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
  state.globalRegisters[0]=17;Waveform wave(state);draws.clear();wave.Draw(frame,&targets);
  Check(glGetError()==GL_NO_ERROR,"circle production draw GL error");
  const int authoredPasses=dots||thick?4:1;
  const int nativePasses=dots?1:LineStyleFor(LineKind::MainWave,thick,2,128,128).passes;
  Check(int(draws.size())==authoredPasses+nativePasses,"circle changed pass/replay style");
  for(size_t i=0;i<draws.size();++i){
   const bool authored=i<size_t(authoredPasses);
   const auto expectedPrimitive=dots?GL_POINTS:authored?GL_LINE_STRIP:GL_TRIANGLE_STRIP;
   const int expectedCount=dots||authored?481:480;
   Check(draws[i].first==expectedPrimitive&&draws[i].second==expectedCount,"circle production closure/dot/segment submission");
  }
  Check(state.globalRegisters[0]==17,"circle replay changed persistent equations");
  for(int pass=0;pass<2;++pass){
   auto& target=pass==0?canvas:native;const int size=pass==0?64:128;
   target.BindRead(0);std::vector<unsigned char> pixels(size*size*4);glReadPixels(0,0,size,size,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
   bool visible=false;for(size_t i=0;i<pixels.size();i+=4){visible|=pixels[i]>0;Check(pixels[i+1]==0&&pixels[i+2]==0,"circle red palette");}
   Check(visible,"circle authored/Native output invisible");Check(glGetError()==GL_NO_ERROR,"circle read target GL error");
  }
 }
 glad_glDrawElements=realElements;glad_glDrawArraysInstanced=realInstanced;
}
int main(){try{GLContext gl;libprojectM::Renderer::ShaderCache cache;
 for(const auto dimensions:{std::array<int,4>{256,256,0,0},{256,144,0,0},{3840,2160,1024,768},{3840,2160,0,0},{144,256,0,0}})
 for(float time:{0.f,1.5f})for(bool audio:{false,true})Control(dimensions[0],dimensions[1],dimensions[2],dimensions[3],time,0, audio?.5f:0,audio);
 Control(256,256,0,0,2.f,-.2f,.3f,true);
 Density();Render(cache);
 Waveforms::XYOscillationSpiral spiral;Check(!spiral.IsLoop(),"retained mode1 open topology");
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<'\n';return 2;}
 std::cout<<"failures="<<failures<<'\n';return failures?1:0;}
