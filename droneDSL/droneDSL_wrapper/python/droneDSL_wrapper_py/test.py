import os
from compiler import compile_dsl  # Ensure correct import based on your setup

# Define the test inputs for DSL and output file paths
dsl_file_path = os.path.join(os.path.dirname(__file__), 'test.dsl')
kml_file_path = os.path.join(os.path.dirname(__file__), 'test.kml')

print("KML Path:", kml_file_path)
print("DSL File Path:", dsl_file_path)

# Call the compile_dsl function with the test arguments

compile_dsl(dsl_file_path, kml_file_path)
print("Compilation successful.")

