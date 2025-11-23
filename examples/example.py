import asyncio
import logging
import grpc

from cline_core import ClineInstance
from cline_core.proto.cline.common_pb2 import Metadata
from cline_core.proto.cline.task_pb2 import NewTaskRequest
from cline_core.proto.cline import task_pb2_grpc
from cline_core.proto.cline.state_pb2 import Settings, PlanActMode, AutoApprovalSettings, AutoApprovalActions
from cline_core.proto.cline.state_pb2_grpc import StateServiceStub
from conversation_follower import follow_conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    with ClineInstance.with_available_ports() as instance:
        with grpc.insecure_channel(instance.address) as channel:
            # Set global auto-approval settings (equivalent to CLI settings)
            try:
                from cline_core.proto.cline.state_pb2 import AutoApprovalSettingsRequest

                auto_approval_req = AutoApprovalSettingsRequest(
                    metadata=Metadata(),
                    version=1,  # Default version
                    actions=AutoApprovalActions(
                        read_files=True,
                        edit_files=True,
                        execute_safe_commands=True,
                        execute_all_commands=True,
                        use_browser=True,
                        use_mcp=True
                    ),
                    enable_notifications=False
                )

                state_stub = StateServiceStub(channel)
                await asyncio.get_event_loop().run_in_executor(
                    None, state_stub.updateAutoApprovalSettings, auto_approval_req
                )
                logger.info("✓ Global auto-approval settings updated")

            except Exception as e:
                logger.warning(f"Could not set global auto-approval: {e}")

            response = task_pb2_grpc.TaskServiceStub(channel).newTask(NewTaskRequest(
                metadata=Metadata(),
                text="Create a simple hello world Python script and save it as hello.py",
                task_settings=Settings(
                    auto_approval_settings=AutoApprovalSettings(
                        actions=AutoApprovalActions(
                            read_files=True,
                            edit_files=True,
                            execute_safe_commands=True,
                        )
                    ),
                    mode=PlanActMode.ACT,
                    enable_checkpoints_setting=False
                )
            ))

            logger.info(f"✅ Task created successfully with ID: {response.value}")

            # Use the new conversation follower implementation (equivalent to FollowConversation + NewInputHandler)
            logger.info("Starting conversation follower...")
            await follow_conversation(channel, instance.address, interactive=True)

if __name__ == "__main__":
    asyncio.run(main())
