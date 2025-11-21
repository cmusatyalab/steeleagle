import os
import time
import subprocess
import argparse
import requests
import json
import tomllib
# Utility imports
from util.cleanup import register_cleanup_handler
register_cleanup_handler()

ROOST_REPO = 'https://git.cmusatyalab.org/steeleagle/roost/-/raw/main/drivers/'
ROOST_PYPI = 'https://git.cmusatyalab.org/api/v4/projects/85/packages/pypi/simple'
PYTHON_DEFAULT = '3.12' # Default Python used by the vehicle driver

def start_services(log, info):
    running = []
    logger = ['python', 'logger/main.py']
    if log:
        task = subprocess.Popen(logger)
        running.append(task)
    # Start the driver
    startup = []
    if info:
        # Get and read the cap file
        cap_request = requests.get(f'{ROOST_REPO}/{info["package"]}/cap.toml')
        if cap_request.status_code == 200:
            try:
                # Attempt to load startup commands
                startup = tomllib.loads(cap_request.text)['startup']
            except:
                print('WARNING: Cap could not be read for startup commands, ignoring...')
        else:
            print('WARNING: No cap found!')
        # Get and read the pyproject file
        python = PYTHON_DEFAULT
        py_request = requests.get(f'{ROOST_REPO}/{info["package"]}/pyproject.toml')
        if py_request.status_code == 200:
            try:
                # Attempt to get the requires-python string
                python = tomllib.loads(py_request.text)['project']['requires-python']
            except Exception as e:
                print('WARNING: Could not read Python version for driver, ignoring...')
        else:
            print('ERROR: Could not find associated pyproject.toml, are you sure the package exists?')
            return
        if info["kwargs"]:
            driver = ['uvx', 
                      '--extra-index-url', ROOST_PYPI,
                      '--python', python,
                      info["package"], '--kwargs', json.dumps(info["kwargs"]), info["name"], info["address"], info["telemetry"], info["imagery"]]
        else:
            driver = ['uvx', 
                      '--extra-index-url', ROOST_PYPI,
                      '--python', python,
                      info["package"], info["name"], info["address"], info["telemetry"], info["imagery"]]
        task = subprocess.Popen(driver)
        running.append(task)
        time.sleep(5)
    # Start the mission
    mission = ['python', 'mission/main.py']
    task = subprocess.Popen(mission)
    running.append(task)
    time.sleep(1)
    # Start the kernel
    kernel = ['python', 'kernel/main.py']
    if len(startup) > 0:
        kernel.append('--startup')
        for s in startup:
            kernel.append(f'{s}')
    task = subprocess.Popen(kernel)
    running.append(task)
    
    running.reverse() # Reverse the processes so the logger dies last
    try:
        for subp in running:
            subp.wait()
    except SystemExit:
        for subp in running:
            subp.terminate()
            subp.wait()

def test_services(test, log):
    logger_task = subprocess.Popen(['python', 'logger/main.py'])
    time.sleep(0.1)
    test_task = subprocess.Popen(['pytest', f'{test}', '-s', '-vv'])
    time.sleep(0.1)
    try:
        test_task.wait()
        logger_task.terminate()
        logger_task.wait()
    except SystemExit:
        test_task.terminate()
        test_task.wait()
        logger_task.terminate()
        logger_task.wait()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Configures the logger and starts all major modules.')
    parser.add_argument('--test', type=str, help='run a test or set of tests in a directory (e.g. test/)')
    parser.add_argument('--config', type=str, default='config.toml', help='override config file path (default: config.toml)')
    parser.add_argument('--internal', type=str, default='.internal.toml', help='override internal config file path (default: .internal.toml)')
    parser.add_argument('--law', type=str, default='.laws.toml', help='override law config file path (default: .laws.toml)')
    parser.add_argument('--headless', action='store_true', default=False, help='starts the kernel without a driver (default: False)')
    args = parser.parse_args()

    # Set environment variables here
    os.environ['PYTHONPATH'] = '.'
    os.environ['CONFIGPATH'] = args.config
    os.environ['INTERNALPATH'] = args.internal
    os.environ['LAWPATH'] = args.law
    
    from util.config import query_config
    log = query_config('logging.generate_flight_log')
    
    driver_info = None
    if not args.headless and not args.test:
        kwargs = query_config('vehicle.kwargs')
        driver_info = {
                'name': query_config('vehicle.name'),
                'package': query_config('vehicle.package'),
                'address': query_config('internal.services.driver'),
                'telemetry': query_config('internal.streams.driver_telemetry'),
                'imagery': query_config('internal.streams.imagery'),
                'kwargs': kwargs if kwargs != {} else None
        }

    if args.test:
        test_services(args.test, log)
    else:
        start_services(log, driver_info)
