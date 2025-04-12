# Add paths associated with the protocol and with utils
CONFIG_PATH=../../../config.yaml PYTHONPATH=$PYTHONPATH:../../../../protocol python3 -m pytest auto_test_suite.py --log-cli-level=INFO
