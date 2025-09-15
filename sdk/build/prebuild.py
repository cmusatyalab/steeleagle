import os
import shutil
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        '''
        Copies generated Python bindings and packages them into a PyPI
        package for publishing. All paths are relative to the SDK root
        directory.
        '''
        package = 'steeleagle_sdk'
        sources = {
            'api' : 'api',
            'dsl' : 'dsl',
        }
        print('>>> Running pre-build steps...')
        if os.path.isdir('build/src'):
            print('>>> Cleaning old build/src directory...')
            shutil.rmtree('build/src')
        for source in sources:
            os.makedirs(f'build/src/{package}/{source}', exist_ok=True)
        print('>>> Generating code...')
        # This generates and copies the Proto, then generates the API and DSL
        os.system('cd build/generate; ./generate.sh; cd ../..')
        print('>>> Copying sources...')
        for source in sources:
            if os.path.isdir(sources[source]):
                shutil.copytree(sources[source], f'build/src/{package}/{source}', dirs_exist_ok=True)
            else:
                shutil.copy(sources[source], f'build/src/{package}/{source}/')
        for dirpath, dirnames, filenames in os.walk('build/src/{package}'):
            with open(f'{dirpath}/__init__.py', 'w') as f:
                pass # Create __init__.py at each level
        super().initialize(version, build_data)
