_PYTHONPATH=../:../../protocol/:../../protocol/python_bindings/:./
_INTERNALPATH=../.internal.yaml
_CONFIGPATH=test.yaml
PYTHONPATH=$_PYTHONPATH CONFIGPATH=$_CONFIGPATH INTERNALPATH=$_INTERNALPATH python3 ../kernel/control/manager.py
