import importlib
from pathlib import Path
import sys

directory_path = Path(__file__).parent
for path in directory_path.glob('*_gen_*'):
    file = path.stem
    new_name = file.replace('_gen_', '')
    _gen_file = importlib.import_module(f'.{file}', package=__name__)
    sys.modules[f'{__name__}.{new_name}'] = _gen_file
