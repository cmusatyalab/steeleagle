import os
import time
import subprocess
import argparse
# Utility imports
from util.cleanup import register_cleanup_handler
register_cleanup_handler()

def start_services(log):
    running = []
    logger = ['python', 'logger/main.py']
    core = [
        ['python', 'mission/main.py'], # Mission
        ['python', 'kernel/main.py'] # Kernel
    ]
    if log:
        core.insert(0, logger)
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
    args = parser.parse_args()

    # Set environment variables here
    os.environ['PYTHONPATH'] = '.'
    os.environ['CONFIGPATH'] = args.config
    os.environ['INTERNALPATH'] = args.internal
    os.environ['LAWPATH'] = args.law
    
    from util.config import query_config
    log = query_config('logging.generate_flight_log')

    if args.test:
        test_services(args.test, log)
    else:
        start_services (log)
