project('cmakeCustomBinariesTest', ['c', 'cpp'])

if not find_program('chmod', required: false).found()
  error('MESON_SKIP_TEST chmod not available.')
endif

python = find_program('python', required: false)
if not python.found()
  error('MESON_SKIP_TEST python binary not available.')
endif

configure_file(input: 'ninja2.py.in', output: 'ninja2.py', configuration: { 'LOG': meson.global_build_root() / 'log'})
run_command(['chmod', '755', meson.global_build_root() / 'ninja2.py'])

cm = import('cmake')

sub_pro = cm.subproject('cmMod')
sub_dep = sub_pro.dependency('cmModLib++', include_type: 'system')

exe1 = executable('main', ['main.cpp'], dependencies: [sub_dep])
test('test_exe', exe1)
test('check_log', python, args: [meson.global_source_root() / 'check.py', meson.global_build_root() / 'log'])
