#!/bin/zsh
# Rebuild the prepared historical source adapters build/visual-loop/source-<name> from git history.
# Usage: tools/milk-analyzer/rebuild_historical_adapters.sh <name> <tv-commit> [<projectm-checkout>]
#   source-pr57: 62a68fca49a4a616614cd4871d5b644c61ab1788 (14 patches, patches_sha256 6e27be9d...)
#   source-pr59: be46967f8c8e89d72034b92062739037183efbff (15 patches, patches_sha256 65313919...)
# The engine is projectM at the checkout's HEAD (engine commit 6f64807467e3...) plus the commit's patch
# series, built through the source34 engine driver with that commit's analysis hooks. The reader and
# translator come from the commit's own tools/milk-analyzer; the audio/wave/noise/image/composite/random
# adapters (added later, which accept these patch identities) come from the current sources.
set -e
NAME=$1; COMMIT=$2; ROOT=${0:A:h:h:h}; SUB=${3:-$ROOT/../../third_party/projectm}
SUB=${SUB:A}; R=$ROOT/build/visual-loop/rebuild-$NAME/repo; O=$ROOT/build/visual-loop/source-$NAME; E=$O/production-engine
mkdir -p $R $O; git -C $ROOT archive $COMMIT | tar -x -C $R
if [ ! -f $E/CMakeLists.txt ]; then
  mkdir -p $E/vendor/projectm-eval; git -C $SUB archive HEAD | tar -x -C $E
  git -C $SUB/vendor/projectm-eval archive HEAD | tar -x -C $E/vendor/projectm-eval
  for p in $R/tools/projectm-patches/*.patch; do (cd $E && GIT_CEILING_DIRECTORIES=$O git apply $p); done
fi
mkdir -p $O/engine-driver
cat > $O/engine-driver/CMakeLists.txt <<'CM'
cmake_minimum_required(VERSION 3.22)
project(predictor_cpu_source LANGUAGES C CXX)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(ENABLE_PLAYLIST OFF CACHE BOOL "" FORCE)
set(ENABLE_SYSTEM_PROJECTM_EVAL OFF CACHE BOOL "" FORCE)
set(ENABLE_SDL_UI OFF CACHE BOOL "" FORCE)
set(ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(CMAKE_DISABLE_FIND_PACKAGE_FLEX ON)
set(CMAKE_DISABLE_FIND_PACKAGE_BISON ON)
include_directories("${PROJECTM_SOURCE}/vendor/glad/include")
add_compile_options("$<$<COMPILE_LANGUAGE:CXX>:-include${GL_SHIM}>")
add_subdirectory("${PROJECTM_SOURCE}" projectm)
CM
cmake -S $O/engine-driver -B $O/native-build -DPROJECTM_SOURCE=$E -DGL_SHIM=$R/tools/preset-lab/src/preset_lab/native/analysis_hooks.hpp -DCMAKE_BUILD_TYPE=Release > $O/native-configure.log
cmake --build $O/native-build -j 8 > $O/native-build.log
python3 - $R $O $SUB <<'PY'
import sys,hashlib,json,subprocess
from pathlib import Path
R,O,SUB=map(Path,sys.argv[1:4])
canon=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
patches=sorted((R/'tools/projectm-patches').glob('*.patch'))
digest=hashlib.sha256(canon([[p.name,hashlib.sha256(p.read_bytes()).hexdigest()] for p in patches]).encode()).hexdigest()
ident={'commit':subprocess.check_output(['git','-C',str(SUB),'rev-parse','HEAD'],text=True).strip(),'patches_sha256':digest}
(O/'native-build/build-identity.json').write_text(json.dumps(ident,separators=(',',':')));print(json.dumps(ident))
PY
cmake -S $R/tools/milk-analyzer -B $O/adapters -DENGINE_SOURCE=$E -DENGINE_BUILD=$O/native-build -DENGINE_IDENTITY_FILE=$O/native-build/build-identity.json -DSANITIZERS=OFF > $O/adapters-configure.log
cmake --build $O/adapters -j 8 > $O/adapters-build.log
cmake -S $ROOT/tools/milk-analyzer -B $O/adapters-current -DENGINE_SOURCE=$E -DENGINE_BUILD=$O/native-build -DENGINE_IDENTITY_FILE=$O/native-build/build-identity.json -DSANITIZERS=OFF > $O/adapters-current-configure.log
cmake --build $O/adapters-current -j 8 > $O/adapters-current-build.log
for b in milk-audio-inputs milk-composite-inputs milk-image-inputs milk-noise-inputs milk-shader-random milk-wave-inputs; do cp $O/adapters-current/$b $O/adapters/; done
echo "source-$NAME rebuilt"
