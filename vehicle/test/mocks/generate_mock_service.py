from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Protocol import
from steeleagle_sdk.protocol.descriptors import get_descriptors


@dataclass
class RPCMethod:
    name: str
    streaming: bool


def generate_mock_service(service_name, service_filename):
    """
    Builds a mock file given a service name, and writes it to the
    given output path.
    """
    # Jinja context variables
    context = {
        "methods": [],
        "service_name": service_name,
        "service_filename": service_filename,
        "in_progress_number": 3,
        "sleep_time": 0.1,
    }
    # Populate methods from descriptor file
    fds = get_descriptors()
    for file in fds.file:
        if file.name != f"services/{service_filename}.proto":
            continue
        for service in file.service:
            if service.name != service_name:
                continue
            # Generate mock methods for each of the methods in the service
            for method in service.method:
                if method.client_streaming and method.server_streaming:
                    raise NotImplementedError(
                        "No mock generation method for method type: bidirectional stream!"
                    )
                elif method.client_streaming:
                    raise NotImplementedError(
                        "No mock generation method for method type: client stream!"
                    )
                rpc = RPCMethod(method.name, method.server_streaming)
                context["methods"].append(rpc)

    # Get the Jinja template
    template_path = Path(__file__).parent / "templates/"
    environment = Environment(loader=FileSystemLoader(str(template_path)))
    template = environment.get_template("mock_service.py.jinja")
    output_path = (
        Path(__file__).parent / f"mock_services/_gen_mock_{service_filename}.py"
    )
    with open(str(output_path), "w") as f:
        f.write(template.render(context))
