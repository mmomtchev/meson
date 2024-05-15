napi = import('node-api')

addon = napi.extension_module(
  'hello_subworld',
  [ 'hello_subworld.cc' ]
  )

if meson.get_compiler('cpp').get_id() == 'emscripten'
  napi.test('hello_world_test', 'test-wasm.mjs', addon)
else
  napi.test('hello_world_test', 'test-native.cjs', addon)
endif
