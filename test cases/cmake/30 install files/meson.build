project('cmake_install_files', ['c', 'cpp'])
data = 'text2'

cm = import('cmake')

cm_opts = cm.subproject_options()
cm_opts.add_cmake_defines({'DATA': data})
sub_pro = cm.subproject('data', options: cm_opts)

assert(sub_pro.found(), 'found() method reports not found, but should be found')

message('prefix is ' + get_option('prefix'))
prefix = get_option('prefix')

add_project_arguments([
  '-DFILE_STATIC="' + prefix / 'share' / 'data-static.txt' + '"',
  '-DFILE_DYNAMIC="' + prefix / 'share' / 'data-dynamic.txt' + '"',
  '-DDATA_STATIC="text1"',
  '-DDATA_DYNAMIC="' + data + '"',
  ], language: ['c', 'cpp'])

install_data('main.cpp')

exe1 = executable('main', ['main.cpp'], install: true)
test('test1', exe1)
