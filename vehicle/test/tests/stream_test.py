import pytest
import asyncio
import logging

# Helper import
from test.helpers import send_requests, Request

# Protocol import
import steeleagle_sdk.protocol.services.compute_service_pb2 as compute_proto
import steeleagle_sdk.protocol.messages.telemetry_pb2 as telemetry_proto

logger = logging.getLogger(__name__)


class Test_Stream:
    """
    Test class focused on image and telemetry streams.
    """

    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_compute_control(
        self,
        messages,
        swarm_controller,
        results,
        imagery,
        driver_telemetry,
        mission_telemetry,
        gabriel,
        kernel,
    ):
        # Start test:
        requests = [
            Request(
                "Compute.SetDatasinks",
                compute_proto.SetDatasinksRequest(
                    datasinks=[
                        compute_proto.DatasinkInfo(id="engine", location=0),
                        compute_proto.DatasinkInfo(id="engine", location=1),
                    ]
                ),
            )
        ]

        await send_requests(requests, swarm_controller, None)

        expected = {"REMOTE": 3, "LOCAL": 3}
        (
            await imagery.send_multipart(
                [b"imagery", telemetry_proto.Frame().SerializeToString()]
            ),
        )
        (
            await driver_telemetry.send_multipart(
                [
                    b"driver_telemetry",
                    telemetry_proto.DriverTelemetry().SerializeToString(),
                ]
            ),
        )
        await mission_telemetry.send_multipart(
            [
                b"mission_telemetry",
                telemetry_proto.MissionTelemetry().SerializeToString(),
            ]
        )
        await asyncio.sleep(1)
        received = {"REMOTE": 0, "LOCAL": 0}
        for i in range(6):
            try:
                (
                    topic,
                    data,
                ) = (
                    await results.recv_multipart()
                )  # This will timeout after half a second if nothing is received
                received[topic.decode("utf-8")] += 1
            except Exception as e:
                pass
        assert expected == received

        # Try removing the remote datasink to make sure it has an effect
        requests = [
            Request(
                "Compute.RemoveDatasinks",
                compute_proto.RemoveDatasinksRequest(
                    datasinks=[compute_proto.DatasinkInfo(id="engine", location=0)]
                ),
            )
        ]

        await send_requests(requests, swarm_controller, None)

        expected = {"REMOTE": 0, "LOCAL": 3}
        (
            await imagery.send_multipart(
                [b"imagery", telemetry_proto.Frame().SerializeToString()]
            ),
        )
        (
            await driver_telemetry.send_multipart(
                [
                    b"driver_telemetry",
                    telemetry_proto.DriverTelemetry().SerializeToString(),
                ]
            ),
        )
        await mission_telemetry.send_multipart(
            [
                b"mission_telemetry",
                telemetry_proto.MissionTelemetry().SerializeToString(),
            ]
        )
        await asyncio.sleep(1)
        received = {"REMOTE": 0, "LOCAL": 0}
        for i in range(6):
            try:
                (
                    topic,
                    data,
                ) = (
                    await results.recv_multipart()
                )  # This will timeout after half a second if nothing is received
                received[topic.decode("utf-8")] += 1
            except Exception as e:
                pass
        assert expected == received

        # Try adding back the remote datasink to make sure it has an effect
        requests = [
            Request(
                "Compute.AddDatasinks",
                compute_proto.AddDatasinksRequest(
                    datasinks=[compute_proto.DatasinkInfo(id="engine", location=0)]
                ),
            )
        ]

        await send_requests(requests, swarm_controller, None)

        expected = {"REMOTE": 3, "LOCAL": 3}
        (
            await imagery.send_multipart(
                [b"imagery", telemetry_proto.Frame().SerializeToString()]
            ),
        )
        (
            await driver_telemetry.send_multipart(
                [
                    b"driver_telemetry",
                    telemetry_proto.DriverTelemetry().SerializeToString(),
                ]
            ),
        )
        await mission_telemetry.send_multipart(
            [
                b"mission_telemetry",
                telemetry_proto.MissionTelemetry().SerializeToString(),
            ]
        )
        await asyncio.sleep(1)
        received = {"REMOTE": 0, "LOCAL": 0}
        for i in range(6):
            try:
                (
                    topic,
                    data,
                ) = (
                    await results.recv_multipart()
                )  # This will timeout after half a second if nothing is received
                received[topic.decode("utf-8")] += 1
            except Exception as e:
                pass
        assert expected == received
