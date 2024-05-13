project(
  'Hello World for meson',
  ['cpp'],
  version: run_command('node', '-p', 'require("./package.json").version', check: true).stdout().strip()
)

napi = import('node_api')

addon = napi.extension_module(
  'hello_world',
  [ 'hello_world.cc' ]
  )

napi.test('hello_world_test', 'test.js', addon)
