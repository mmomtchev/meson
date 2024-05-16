#define NAPI_DISABLE_CPP_EXCEPTIONS

#include <napi.h>

using namespace Napi;

#if defined(NAPI_CPP_EXCEPTIONS) || defined(_CPPUNWIND) || defined(__EXCEPTIONS)
#error must compile without C++ exceptions
#endif

Napi::String Method(const Napi::CallbackInfo &info) {
  Napi::Env env = info.Env();
  return Napi::String::New(env, "world");
}

Napi::Object Init(Napi::Env env, Napi::Object exports) {
  exports.Set(Napi::String::New(env, "HelloWorld"),
              Napi::Function::New(env, Method));
  return exports;
}

NODE_API_MODULE(addon, Init)
