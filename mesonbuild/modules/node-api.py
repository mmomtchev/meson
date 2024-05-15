# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 momtchil@momtchev.com
# Inspired by the python.py module

from __future__ import annotations

import json, subprocess, os, sys, tarfile, io
import urllib.request, urllib.error, urllib.parse
from pathlib import Path
from enum import Enum
import typing as T

from . import ExtensionModule, ModuleInfo, ModuleObject
from .. import mesonlib
from .. import mlog
from .. import mparser
from ..build import known_shmod_kwargs, CustomTarget, CustomTargetIndex, BuildTarget, GeneratedList, StructuredSources, ExtractedObjects, SharedModule
from ..programs import ExternalProgram
from ..interpreter.type_checking import SHARED_MOD_KWS, TEST_KWS
from ..interpreterbase import (
    permittedKwargs, typed_pos_args, typed_kwargs, KwargInfo
)

if T.TYPE_CHECKING:
    from ..interpreter import Interpreter
    from ..interpreter.kwargs import SharedModule as SharedModuleKw, FuncTest as FuncTestKw
    from ..interpreterbase import TYPE_kwargs, TYPE_var
    from typing import Any

    SourcesVarargsType = T.List[T.Union[str, mesonlib.File, CustomTarget, CustomTargetIndex, GeneratedList, StructuredSources, ExtractedObjects, BuildTarget]]

name_prefix = ''
name_suffix_native = 'node'
name_suffix_wasm = 'mjs'

mod_kwargs = { 'node_api_options' }
mod_kwargs.update(known_shmod_kwargs)
mod_kwargs -= {'name_prefix', 'name_suffix'}

_MOD_KWARGS = [k for k in SHARED_MOD_KWS if k.name not in {'name_prefix', 'name_suffix'}]

class NodeAPIEnv(Enum):
    node    = 'node'
    web     = 'web'
    webview = 'webview'
    worker  = 'worker'

class NodeAPIOptions(T.TypedDict):
    async_workers:  bool
    async_pool:     int
    es6:            bool
    fs:             bool
    stack:          str
    exceptions:     bool
    swig:           bool
    environments:   T.Set[NodeAPIEnv]

# These are the defauls
node_api_defaults: NodeAPIOptions = {
    'async_workers':    False,
    'async_pool':       4,
    'es6':              True,
    'stack':            '2MB',
    'exceptions':       True,
    'swig':             False,
    'environments':     { NodeAPIEnv.node, NodeAPIEnv.web, NodeAPIEnv.webview, NodeAPIEnv.worker }
}
_SUBDIR_KW = KwargInfo('node_api_options', dict, default=node_api_defaults)

emscripten_default_link_args_debug = [
    '-gsource-map',
    '-sSAFE_HEAP=1',
    '-sASSERTIONS=2',
    '-sSTACK_OVERFLOW_CHECK=2'
]

if T.TYPE_CHECKING:
    class ExtensionModuleKw(SharedModuleKw):
        options: NodeAPIOptions

def tar_strip1(files: T.List[tarfile.TarInfo]) -> T.Generator[tarfile.TarInfo, None, None]:
    for member in files:
        member.path = str(Path(*Path(member.path).parts[1:]))
        yield member

class NapiModule(ExtensionModule):

    INFO = ModuleInfo('node-api', '2.0.0')

    def __init__(self, interpreter: 'Interpreter') -> None:
        super().__init__(interpreter)
        self.node_process: Any = None
        self.emnapi_package: Any = None
        self.napi_dir: Path = None
        self.load_node_process()
        self.download_headers()
        self.methods.update({
            'extension_module': self.extension_module_method,
            'test': self.test_method,
        })

    def parse_node_json_output(self, code: str) -> Any:
        result: Any = None
        try:
            node_json = subprocess.Popen(['node', '-p', f'JSON.stringify({code})'], shell=False, stdout=subprocess.PIPE,
                                         cwd=self.interpreter.environment.get_source_dir())
            data, err = node_json.communicate()
            node_json.wait()
            result = json.loads(data)
        except Exception as e:
            raise mesonlib.MesonException(f'Failed spawning node: {str(e)}')
        return result

    def load_node_process(self) -> None:
        if self.node_process is None:
            self.node_process = self.parse_node_json_output('process')
            self.get_napi_dir()

    def load_emnapi_package(self) -> None:
        if self.emnapi_package is None:
            self.emnapi_package = self.parse_node_json_output('require("emnapi")')

    def construct_native_options(self, name:str, opts: NodeAPIOptions) -> T.Tuple[T.List[str], T.List[str]]:
        return [], []

    # As these options are mandatory in order to build an emnapi WASM module, they are hardcoded here
    def construct_emscripten_options(self, name: str, opts: NodeAPIOptions) -> T.Tuple[T.List[str], T.List[str]]:
        full_opts = {**node_api_defaults, **opts}
        c_args = []
        link_args = ['-Wno-emcc', '-Wno-pthreads-mem-growth', '-sALLOW_MEMORY_GROWTH=1',
                     '-sEXPORTED_FUNCTIONS=["_malloc","_free","_napi_register_wasm_v1","_node_api_module_get_api_version_v1"]',
                     '--bind', f'-sSTACK_SIZE={full_opts["stack"]}' ]

        if full_opts['es6']:
            link_args.extend(['-sMODULARIZE', '-sEXPORT_ES6=1', f'-sEXPORT_NAME={name}'])
        if full_opts['async_workers']:
            c_args.extend(['-phtread'])
            link_args.extend(['-pthread', f'-sDEFAULT_PTHREAD_STACK_SIZE={full_opts["stack"]}',
                              f'-sPTHREAD_POOL_SIZE={full_opts["async_workers"]}'])
        if full_opts['exceptions'] or full_opts['swig']:
            link_args.extend(['-sNO_DISABLE_EXCEPTION_CATCHING'])

        env = '-sENVIRONMENT='
        for e in full_opts['environments']:
            env += f'{e.value},'
        link_args.append(env)

        return c_args, link_args

    def get_napi_dir(self) -> None:
        if sys.platform in 'linux':
            home = os.environ['HOME'] if 'HOME' in os.environ else '/tmp'
            self.napi_dir = Path(home) / '.cache' / 'node-hadron' / self.node_process['release']['name'] / self.node_process['version']
        elif sys.platform == 'darwin':
            home = os.environ['HOME'] if 'HOME' in os.environ else '/tmp'
            self.napi_dir = Path(home) / 'Library' / 'Caches' / 'node-hadron' / self.node_process['release']['name'] / self.node_process['version']
        elif sys.platform == 'win32':
            home = os.environ['LOCALAPPDATA'] if 'LOCALAPPDATA' in os.environ else 'C:\\'
            self.napi_dir = Path(home) / 'node-hadron' / self.node_process['release']['name'] / self.node_process['version']
        else:
            raise mesonlib.MesonException(f'Unsupported platform: {sys.platform}')

    def download_item(self, url: str, dest: Path) -> None:
        remote = urllib.request.urlopen(url)
        if url.endswith('.tar.gz'):
            if not os.path.exists(dest):
                mlog.log(f'Downloading {url} to {dest}')
                with tarfile.open(fileobj=io.BytesIO(remote.read()), mode='r:gz') as input:
                    input.extractall(path=dest, members=tar_strip1(input.getmembers()))
        else:
            filename = urllib.parse.urlparse(url)
            file = Path(dest, os.path.basename(filename.path))
            if not os.path.exists(file):
                mlog.log(f'Downloading {url} to {str(file)}')
                with file.open('wb') as output:
                    output.write(remote.read())

    def download_headers(self) -> None:
        if 'headersUrl' in self.node_process['release']:
            self.download_item(self.node_process['release']['headersUrl'], self.napi_dir)
        if 'libUrl' in self.node_process['release']:
            self.download_item(self.node_process['release']['libUrl'], self.napi_dir)

        mlog.log('Node.js library distribution: ', mlog.bold(str(self.napi_dir)))

    def emnapi_sources(self) -> T.List[Path]:
        self.load_emnapi_package()
        sources: T.List[str] = self.emnapi_package['sources']
        source_root = Path(self.interpreter.environment.get_source_dir())
        return [(Path(d).relative_to(source_root) if Path(d).is_relative_to(source_root) else Path(d)) for d in sources]

    def emnapi_include_dirs(self) -> T.List[Path]:
        self.load_emnapi_package()
        inc_dirs: T.List[str] = [self.emnapi_package['include_dir']]
        source_root = Path(self.interpreter.environment.get_source_dir())
        return [(Path(d).relative_to(source_root) if Path(d).is_relative_to(source_root) else Path(d)) for d in inc_dirs]

    def emnapi_js_library(self) -> Path:
        self.load_emnapi_package()
        js_lib: str = self.emnapi_package['js_library']
        return js_lib

    @permittedKwargs(mod_kwargs)
    @typed_pos_args('node-api.extension_module', str, varargs=(str, mesonlib.File, CustomTarget, CustomTargetIndex, GeneratedList, StructuredSources, ExtractedObjects, BuildTarget))
    @typed_kwargs('node-api.extension_module', *_MOD_KWARGS, _SUBDIR_KW)
    def extension_module_method(self, node: mparser.BaseNode, args: T.Tuple[str, SourcesVarargsType], kwargs: ExtensionModuleKw) -> 'SharedModule':
        if 'include_directories' not in kwargs:
            kwargs['include_directories'] = []
        kwargs['name_prefix'] = name_prefix
        if 'cpp' not in self.interpreter.environment.get_coredata().compilers.host:
            raise mesonlib.MesonException('Node-API requires C++')
        if self.interpreter.environment.get_coredata().compilers.host['cpp'].id == 'emscripten':
            # emscripten WASM mode
            if 'c' not in self.interpreter.environment.get_coredata().compilers.host:
                raise mesonlib.MesonException('Node-API requires C for WASM mode')

            kwargs['name_suffix'] = name_suffix_wasm

            extra_c_args, extra_link_args = self.construct_emscripten_options(args[0], kwargs['node_api_options'])
            kwargs.setdefault('link_args', []).extend(extra_link_args)
            kwargs.setdefault('c_args', []).extend(extra_c_args)
            kwargs.setdefault('cpp_args', []).extend(extra_c_args)

            js_lib = self.emnapi_js_library()
            kwargs['link_args'].append(f'--js-library={js_lib}')

            inc_dirs = self.emnapi_include_dirs()
            kwargs['include_directories'] += [str(d) for d in inc_dirs]

            sources = self.emnapi_sources()
            args[1].extend([str(d) for d in sources])

        else:
            # Node.js native mode
            kwargs['name_suffix'] = name_suffix_native

        kwargs.setdefault('include_directories', []).append(str(self.napi_dir / 'include' / 'node'))
        kwargs.setdefault('include_directories', []).append(str(Path('node_modules') / 'node-addon-api'))

        return self.interpreter.build_target(node, args, kwargs, SharedModule)

    @typed_pos_args('node_api_extension.test', str, (str, mesonlib.File), (SharedModule, mesonlib.File))
    @typed_kwargs('node_api_extenstion.test', *TEST_KWS, KwargInfo('is_parallel', bool, default=True))
    def test_method(self, node: mparser.BaseNode,
                    args: T.Tuple[
                        str,
                        T.Union[str, mesonlib.File],
                        T.Union[SharedModule, mesonlib.File]
                        ],
                    kwargs: 'FuncTestKw') -> None:

        test_name = args[0]
        script = args[1]
        addon = args[2]

        node_script: mesonlib.File = None
        if isinstance(script, mesonlib.File):
            node_script = script
        else:
            node_script = mesonlib.File(False, '', script)

        node_env = kwargs.setdefault('env', mesonlib.EnvironmentVariables())
        node_addon: T.Union[SharedModule, mesonlib.File] = None
        node_path: str = None
        if isinstance(addon, SharedModule):
            kwargs.setdefault('depends', []).append(addon)
            node_path = str((Path(self.interpreter.environment.get_build_dir()) / addon.subdir).resolve())
            node_addon = addon
            node_env.set('NODE_ADDON', [node_addon.filename])
        elif isinstance(addon, mesonlib.File):
            node_path = addon.absolute_path()
            node_addon = addon
            node_env.set('NODE_ADDON', [str(node_addon.relative_name)])
        else:
            raise mesonlib.MesonException('The target must be either a napi.ExtensionModule or an ExternalProgram')
        node_env.set('NODE_PATH', [node_path])

        kwargs.setdefault('args', []).insert(0, node_script)

        self.interpreter.add_test(node, (test_name, ExternalProgram('node')), T.cast('T.Dict[str, Any]', kwargs), True)

def initialize(interpreter: 'Interpreter') -> NapiModule:
    mod = NapiModule(interpreter)
    return mod
