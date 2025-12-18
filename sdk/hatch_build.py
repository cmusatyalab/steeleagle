import os
import shutil
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from pathlib import Path

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        '''
        Copies generated Python bindings and packages them into a PyPI
        package for publishing. All paths are relative to the SDK root
        directory.
        '''
        print('>>> Running custom build hook')
        package = 'steeleagle_sdk'
        print('>>> Generating code...')
        # This generates and copies the Proto, then generates the API and DSL
        os.system('cd generate; ./generate.sh; cd ../..')

        for dirpath, dirnames, filenames in os.walk(f"src/{package}"):
            init_file = os.path.join(dirpath, "__init__.py")
            # Create the file only if it doesn't exist; "a" won't overwrite
            open(init_file, "a").close()

        super().initialize(version, build_data)
