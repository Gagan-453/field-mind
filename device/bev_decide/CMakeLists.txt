# bev-decide: links against an INSTALLED llama.cpp package (cmake --install
# prefix: include/ and lib/), so the binary uses exactly the libraries that are
# on the board. Android: device/bev_decide/build_android.sh. Host (any OS):
#   cmake -S device/bev_decide -B build-bev -DLLAMA_PKG=<prefix> -DLLAMA_SRC=<checkout>
#   cmake --build build-bev
cmake_minimum_required(VERSION 3.14)
project(bev_decide CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

set(LLAMA_PKG "" CACHE PATH "installed llama.cpp package (include/, lib/), the same build as the board's")
set(LLAMA_SRC "" CACHE PATH "llama.cpp checkout at the same commit (vendor/nlohmann/json.hpp)")
if(NOT LLAMA_PKG OR NOT LLAMA_SRC)
  message(FATAL_ERROR "set -DLLAMA_PKG=<installed package> and -DLLAMA_SRC=<checkout>")
endif()

foreach(lib llama ggml ggml-base)
  string(MAKE_C_IDENTIFIER "${lib}" var)
  find_library(LIB_${var} ${lib} PATHS "${LLAMA_PKG}/lib" NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
  if(NOT LIB_${var})
    message(FATAL_ERROR "lib${lib} not found in ${LLAMA_PKG}/lib")
  endif()
endforeach()

add_executable(bev-decide bev_decide.cpp)
target_include_directories(bev-decide PRIVATE "${LLAMA_PKG}/include" "${LLAMA_SRC}/vendor")
target_link_libraries(bev-decide PRIVATE ${LIB_llama} ${LIB_ggml} ${LIB_ggml_base})
# No fast-math: the head must match bev_decider's fp32 arithmetic and stay
# order invariant (llama.cpp's own preset uses -ffp-model=fast; not here).
target_compile_options(bev-decide PRIVATE -O2 -Wall -Wextra)
