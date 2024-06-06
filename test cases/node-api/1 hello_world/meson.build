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

if not get_option('enabled')
  error('enabled not enabled')
endif
if get_option('disabled')
  error('disabled not disabled')
endif
if get_option('default_false')
  error('default_false not defaulted to false')
endif
if not get_option('default_true')
  error('default_true not defaulted to true')
endif
if get_option('string') != 'string'
  error('string not string')
endif
if get_option('choice') != 'a'
  error('choice a not a')
endif
if not get_option('lib').enabled()
  error('feature enabled not enabled')
endif

summary({
  'enabled': get_option('enabled'),
  'disabled': get_option('disabled'),
  'true': get_option('default_true'),
  'false': get_option('default_false'),
  'string': get_option('string'),
  'choice': get_option('choice'),
  'lib': get_option('lib'),
})

if host_machine.system() == 'emscripten'
  napi.test('hello_world_test', 'test-wasm.mjs', addon)
else
  napi.test('hello_world_test', 'test-native.cjs', addon)
endif
