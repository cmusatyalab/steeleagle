import os
import time
import subprocess
import argparse
import requests
import json
# Utility imports
from util.cleanup import register_cleanup_handler
register_cleanup_handler()

ROOST = 'https://git.cmusatyalab.org/api/v4/projects/85/packages/pypi/simple'

def start_services(log, info):
    running = []
    logger = ['python', 'logger/main.py']
    if log:
        task = subprocess.Popen(logger)
        running.append(task)
    # Start the driver
    if info:
        if info["kwargs"]:
            driver = ['uvx', 
                      '--extra-index-url', ROOST,
                      '--python', info["python"],
                      info["package"], '--kwargs', json.dumps(info["kwargs"]), info["name"], info["address"], info["telemetry"], info["imagery"]]
            print(driver)
        else:
            driver = ['uvx', 
                      '--extra-index-url', ROOST,
                      '--python', info["python"],
                      info["package"], info["name"], info["address"], info["telemetry"], info["imagery"]]
        task = subprocess.Popen(driver)
        running.append(task)
        time.sleep(5)
    # Start core services
    core = [
        ['python', 'mission/main.py'], # Mission
        ['python', 'kernel/main.py'] # Kernel
    ]
    for subp in core:
        task = subprocess.Popen(subp)
        running.append(task)
        time.sleep(0.1)
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
    if not args.headless:
        kwargs = query_config('vehicle.kwargs')
        driver_info = {
                'name': query_config('vehicle.name'),
                'package': query_config('vehicle.package'),
                'python': query_config('vehicle.python'),
                'address': query_config('internal.services.driver'),
                'telemetry': query_config('internal.streams.driver_telemetry'),
                'imagery': query_config('internal.streams.imagery'),
                'kwargs': kwargs if kwargs != {} else None
        }

    if args.test:
        test_services(args.test, log)
    else:
        start_services(log, driver_info)
