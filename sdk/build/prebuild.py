import os
import shutil
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        '''
        Copies generated Python bindings and packages them into a PyPI
        package for publishing.
        '''
        package = 'steeleagle_sdk'
        sources = {
            'api' : '../api',
            'dsl' : '../dsl',
            'protocol' : '../protocol/get_descriptors.py'
        }
        print('>>> Running pre-build steps...')
        #if os.path.isdir('src'):
        #    print('>>> Cleaning old src directory...')
        #    shutil.rmtree('src')
        for source in sources:
            os.makedirs(f'src/{package}/{source}', exist_ok=True)
        #print('>>> Generating code...')
        #os.system('cd generate; ./build.sh; cd ..')
        print('>>> Copying sources...')
        for source in sources:
            if os.path.isdir(sources[source]):
                shutil.copytree(sources[source], f'src/{package}/{source}', dirs_exist_ok=True)
            else:
                shutil.copy(sources[source], f'src/{package}/{source}/')
        for dirpath, dirnames, filenames in os.walk('src/{package}'):
            with open(f'{dirpath}/__init__.py', 'w') as f:
                pass # Create __init__.py at each level
        super().initialize(version, build_data)
