import asyncio
import logging
from cline_core import ClineInstance

import grpc
from cline_core.proto.cline import task_pb2
from cline_core.proto.cline import task_pb2_grpc
from cline_core.proto.cline import state_pb2


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    with ClineInstance.with_available_ports() as instance:
        with grpc.aio.insecure_channel(instance.address) as channel:
            response = await task_pb2_grpc.TaskServiceStub(channel).newTask(task_pb2.NewTaskRequest(
                metadata=task_pb2.Metadata(),
                text="Create a simple hello world Python script and save it as hello.py",
                task_settings=state_pb2.Settings(
                    auto_approval_settings=state_pb2.AutoApprovalSettings(
                        actions=state_pb2.AutoApprovalActions(
                            read_files=True,
                            edit_files=True,
                            execute_safe_commands=True,
                        )
                    ),
                    mode=state_pb2.PlanActMode.ACT
                )
            ))

            logger.info(f"✅ Task created successfully with ID: {response.value}")

if __name__ == "__main__":
    asyncio.run(main())
