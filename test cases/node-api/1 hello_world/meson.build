project(
  'Hello World for meson',
  ['c', 'cpp']
)

napi = import('node-api')

run_command(['npm', '--prefix', meson.global_source_root(), 'install'], check: true)

addon = napi.extension_module(
  'hello_world',
  [ 'hello_world.cc' ],
  install: true
  )

if not napi.get_option('enabled', false)
  error('enabled not enabled')
endif
if napi.get_option('disabled', true)
  error('disabled not disabled')
endif
if napi.get_option('absent', false)
  error('absent not defaulted to false')
endif
if not napi.get_option('absent', true)
  error('absent not defaulted to true')
endif

summary({
  'enabled': napi.get_option('enabled', false),
  'disabled': napi.get_option('disabled', true),
  'true': napi.get_option('absent', true),
  'false': napi.get_option('absent', false)
})

if host_machine.system() == 'emscripten'
  napi.test('hello_world_test', 'test-wasm.mjs', addon)
else
  napi.test('hello_world_test', 'test-native.cjs', addon)
endif
