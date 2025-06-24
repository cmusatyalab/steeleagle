import os
import subprocess

compiler_path = "/compiler"
output_path = "/compiler/out/flightplan_"
platform_path = "/compiler/python"


def compile_mission(dsl_file, kml_file, drone_list):
    # Construct the full paths for the DSL and KML files
    dsl_file_path = os.path.join(compiler_path, dsl_file)
    kml_file_path = os.path.join(compiler_path, kml_file)
    jar_path = os.path.join(compiler_path, "compile-1.5-full.jar")

    # Define the command and arguments
    command = [
        "java",
        "-jar",
        jar_path,
        "-d",
        drone_list,
        "-s",
        dsl_file_path,
        "-k",
        kml_file_path,
        "-o",
        output_path,
        "-p",
        platform_path,
    ]

    try:
        # Run the command
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("output: ", result)

        # Output the results
        print("Compilation successful.")

    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr)


if __name__ == "__main__":
    kml_file = "tst.kml"
    dsl_file = "tst.dsl"
    drone_list = "ant&mamba"
    compile_mission(dsl_file, kml_file, drone_list)
