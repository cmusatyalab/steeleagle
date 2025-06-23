import asyncio
import importlib
import logging
import pkgutil

from control_service import ControlService
from data_service import DataService
from data_store import DataStore
from datasinks.ComputeItf import ComputeInterface
from util.utils import query_config, setup_logging

logger = logging.getLogger(__name__)


def discover_compute_classes():
    """Discover all compute classes dynamically from datasinks."""
    import datasinks

    compute_classes = {}
    for module_info in pkgutil.iter_modules(
        datasinks.__path__, datasinks.__name__ + "."
    ):
        module_name = module_info.name
        module = importlib.import_module(module_name)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ComputeInterface)
                and attr is not ComputeInterface
            ):
                compute_classes[attr_name.lower()] = attr
    return compute_classes


def run_compute_tasks(data_store, compute_dict):
    """Instantiate and launch compute modules."""
    compute_classes = discover_compute_classes()
    logger.info(f"Available compute classes: {', '.join(compute_classes.keys())}")

    tasks = []

    for compute_config in query_config("hub.computes"):
        compute_class = compute_config["compute_class"].lower()
        compute_id = compute_config["compute_id"]

        if compute_class not in compute_classes:
            logger.error(f"Compute class '{compute_class}' not found")
            continue

        Compute = compute_classes[compute_class]
        compute_instance = Compute(compute_id, data_store)

        logger.info(f"Starting compute {compute_class} with id {compute_id}")
        compute_dict[compute_id] = compute_instance
        data_store.append_compute(compute_id)

        tasks.append(asyncio.create_task(compute_instance.run()))

    return tasks


async def main():
    setup_logging(logger, "hub.logging")
    logger.info("Launching unified hub services")

    # Shared resources
    data_store = DataStore()
    compute_dict = {}

    # Spawn compute modules
    compute_tasks = run_compute_tasks(data_store, compute_dict)

    # Create services with shared references
    data_service = DataService(data_store, compute_dict)
    command_service = ControlService(data_store, compute_dict)

    await asyncio.gather(data_service.start(), command_service.start(), *compute_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Main: KeyboardInterrupt received, exiting...")
