from setuptools import setup, find_packages

setup(
    name="drone_dsl_wrapper",
    version="1.0",
    packages=find_packages(where="."),  # Detects packages without repeating paths
    package_dir={"": "."},  # Use current directory as the package root
    package_data={
        "droneDSL_wrapper_py": ["lib/compile-1.0-full.jar"],  # Include JAR in the package
    },
    install_requires=["py4j"],
    description="A Python wrapper for DroneDSL using Py4J",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
