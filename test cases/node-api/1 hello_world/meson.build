project(
  'Hello World for meson',
  ['cpp']
)

napi = import('node_api')

addon = napi.extension_module(
  'hello_world',
  [ 'hello_world.cc' ]
  )

napi.test('hello_world_test', 'test.js', addon)
