import asyncio
import logging
import grpc

from cline_core import ClineInstance
from cline_core.proto.cline.common_pb2 import Metadata
from cline_core.proto.cline.task_pb2 import NewTaskRequest
from cline_core.proto.cline import task_pb2_grpc
from cline_core.proto.cline.state_pb2 import Settings, PlanActMode, AutoApprovalSettings, AutoApprovalActions
from conversation_follower import follow_conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    with ClineInstance.with_available_ports() as instance:
        with grpc.insecure_channel(instance.address) as channel:
            response = task_pb2_grpc.TaskServiceStub(channel).newTask(NewTaskRequest(
                metadata=Metadata(),
                text="Create a simple hello world Python script and save it as hello.py",
                task_settings=Settings(
                    mode=PlanActMode.ACT,
                    enable_checkpoints_setting=False
                )
            ))

            logger.info(f"✅ Task created successfully with ID: {response.value}")

            logger.info("Starting conversation follower...")
            await follow_conversation(channel, instance.address, interactive=True)

if __name__ == "__main__":
    asyncio.run(main())
