# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 momtchil@momtchev.com
# Inspired by the python.py module

from __future__ import annotations

import json, subprocess, os, sys, tarfile, io
import urllib.request, urllib.error, urllib.parse
from pathlib import Path
import typing as T

from . import ExtensionModule, ModuleInfo
from .. import mesonlib
from .. import mlog
from .. import mparser
from ..build import known_shmod_kwargs, CustomTarget, CustomTargetIndex, BuildTarget, GeneratedList, StructuredSources, ExtractedObjects, SharedModule, Executable
from ..programs import ExternalProgram
from ..interpreter.type_checking import SHARED_MOD_KWS, TEST_KWS
from ..interpreterbase import (
    permittedKwargs, typed_pos_args, typed_kwargs, KwargInfo
)

if T.TYPE_CHECKING:
    from ..interpreter import Interpreter
    from ..interpreter.interpreter import BuildTargetSource
    from ..interpreter.kwargs import SharedModule as SharedModuleKw


name_prefix = ''
name_suffix = 'node'

mod_kwargs = set()
mod_kwargs.update(known_shmod_kwargs)
mod_kwargs -= {'name_prefix', 'name_suffix'}

_MOD_KWARGS = [k for k in SHARED_MOD_KWS if k.name not in {'name_prefix', 'name_suffix'}]

def tar_strip1(files: T.List[tarfile.TarInfo]):
    for member in files:
        member.path = str(Path(*Path(member.path).parts[1:]))
        yield member

class NapiModule(ExtensionModule):

    INFO = ModuleInfo('node_api', '2.0.0')

    def __init__(self, interpreter: 'Interpreter') -> None:
        super().__init__(interpreter)
        self.node_process: Any = None
        self.napi_dir: Path = None
        self.load_node_process()
        self.download_headers()
        self.methods.update({
            'extension_module': self.extension_module_method,
            'test': self.test_method,
        })

    def load_node_process(self) -> None:
        if self.node_process is None:
            try:
                node_json = subprocess.Popen(['node', '-p', 'JSON.stringify(process)'], shell=False, stdout=subprocess.PIPE)
                data, err = node_json.communicate()
                node_json.wait()
                self.node_process = json.loads(data)
            except Exception as e:
                raise mesonlib.MesonException(f'Failed spawning node: {str(e)}')

            self.get_napi_dir()

    def get_napi_dir(self) -> None:
        if sys.platform == 'linux' or sys.platform == 'darwin':
            home = os.environ['HOME'] if 'HOME' in os.environ else '/tmp'
            self.napi_dir = Path(home) / '.cache' / 'node-hadron' / self.node_process['release']['name'] / self.node_process['version']
        elif sys.platform == 'darwin':
            home = os.environ['HOME'] if 'HOME' in os.environ else '/tmp'
            self.napi_dir = Path(home) / 'Library' / 'Caches' / 'node-hadron' / self.node_process['release']['name'] / self.node_process['version']
        elif sys.platform == 'win32':
            home = os.environ['LOCALAPPDATA'] if 'LOCALAPPDATA' in os.environ else 'C:\\'
            self.napi_dir = Path(home) / 'node-hadron' / node_process['release']['name'] / self.node_process['version']
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

        mlog.log(f'Node.js library distribution: ', mlog.bold(str(self.napi_dir)))
        return None

    @permittedKwargs(mod_kwargs)
    @typed_pos_args('node_api.extension_module', str, varargs=(str, mesonlib.File, CustomTarget, CustomTargetIndex, GeneratedList, StructuredSources, ExtractedObjects, BuildTarget))
    @typed_kwargs('node_api.extension_module', *_MOD_KWARGS)
    def extension_module_method(self, node: mparser.BaseNode, args: T.Tuple[str, T.List[BuildTargetSource]], kwargs: SharedModuleKw) -> 'SharedModule':
        if 'include_directories' not in kwargs:
            kwargs['include_directories'] = []
        kwargs.setdefault('include_directories', []).append(str(self.napi_dir / 'include' / 'node'))
        kwargs.setdefault('include_directories', []).append(str(Path('node_modules') / 'node-addon-api'))
        kwargs['name_prefix'] = name_prefix
        kwargs['name_suffix'] = name_suffix
        return self.interpreter.build_target(node, args, kwargs, SharedModule)

    @typed_pos_args('node_api_extension.test', str, (str, mesonlib.File), (SharedModule, mesonlib.File))
    @typed_kwargs('node_api_extenstion.test', *TEST_KWS, KwargInfo('is_parallel', bool, default=True))
    def test_method(self, node: mparser.BaseNode,
                  args: T.Tuple[
                    str,
                    T.Union[str, mesonlib.File],
                    T.Union[SharedModule, mesonlib.File]
                    ],
                  kwargs: 'kwtypes.FuncTest') -> None:

        test_name = args[0]
        js = args[1]
        addon = args[2]

        node_js = ''
        if isinstance(js, mesonlib.File):
            node_js = js
        else:
            node_js = mesonlib.File(False, '', js)

        node_arg = ''
        if isinstance(addon, SharedModule):
            kwargs.setdefault('depends', []).append(addon)
            node_arg = addon

        kwargs.setdefault('args', []).insert(0, node_arg)
        kwargs['args'].insert(0, node_js)

        self.interpreter.add_test(node, (test_name, ExternalProgram('node')), kwargs, True)

def initialize(interpreter: 'Interpreter') -> NapiModule:
    mod = NapiModule(interpreter)
    return mod
