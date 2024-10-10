from py4j.java_gateway import JavaGateway 
import os

# Path to the JAR file
jar_path = os.path.join(os.path.dirname(__file__), 'lib', 'compile-1.0-full.jar')
print(jar_path)



def compile_dsl(dsl_file_path, kml_file_path, output_file_path="./flightplan.ms", altitude="15", platform="python/user/project"):
    # Launch the Java Gateway with the JAR in the classpath and create a gateway object
    gateway = JavaGateway.launch_gateway(classpath=jar_path)
    print("Gateway launched:", gateway)
    Compiler = gateway.jvm.org.droneDSL.compile.Compiler  # Reference to the Compiler class in Java
    compiler = Compiler()  # Instantiate the Compiler class
    compiler.runWithArguments(dsl_file_path, output_file_path, kml_file_path, altitude, platform)
    gateway.close()  # Close the gateway after use
