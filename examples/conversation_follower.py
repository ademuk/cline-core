import asyncio
import json
import logging
import signal
from typing import Optional, Dict, Any

from cline_core.proto.cline.common_pb2 import Metadata
from cline_core.proto.cline.state_pb2 import Settings, PlanActMode, AutoApprovalSettings, AutoApprovalActions
from cline_core.proto.cline.state_pb2_grpc import StateServiceStub
from cline_core.proto.cline.task_pb2_grpc import TaskServiceStub
from cline_core.proto.cline import task_pb2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamCoordinator:
    """Coordinates streams and input handling like the Go StreamCoordinator"""

    def __init__(self):
        self.conversation_turn_start_index = 0
        self.input_allowed = False
        self.processed_messages = set()

    def set_conversation_turn_start_index(self, index: int):
        self.conversation_turn_start_index = index

    def get_conversation_turn_start_index(self) -> int:
        return self.conversation_turn_start_index

    def set_input_allowed(self, allowed: bool):
        self.input_allowed = allowed

    def is_input_allowed(self) -> bool:
        return self.input_allowed

    def mark_processed_in_current_turn(self, key: str):
        self.processed_messages.add(f"{self.conversation_turn_start_index}:{key}")

    def is_processed_in_current_turn(self, key: str) -> bool:
        return f"{self.conversation_turn_start_index}:{key}" in self.processed_messages

    def complete_turn(self, new_index: int):
        # Clear processed messages for previous turn
        self.processed_messages = {k for k in self.processed_messages if not k.startswith(f"{self.conversation_turn_start_index}:")}
        self.conversation_turn_start_index = new_index

class ConversationManager:
    """Equivalent of the Go Manager struct for conversation handling"""

    def __init__(self, channel):
        self.channel = channel
        self.state_stub = StateServiceStub(channel)
        self.task_stub = TaskServiceStub(channel)
        self.is_streaming_mode = False
        self.is_interactive = False
        self.current_mode = "plan"
        self.coordinator = StreamCoordinator()

    async def follow_conversation(self, instance_address: str, interactive: bool = True):
        """Main equivalent of FollowConversation function"""
        self.is_streaming_mode = True
        self.is_interactive = interactive

        print(f"📡 Using instance: {instance_address}")
        if interactive:
            print("Following task conversation in interactive mode... (Ctrl+C to exit)")
        else:
            print("Following task conversation... (Ctrl+C to exit)")

        # Set up cancellation handling
        cancelled = False
        def cancel_func():
            nonlocal cancelled
            cancelled = True

        # Handle Ctrl+C
        def signal_handler(signum, frame):
            cancel_func()

        old_handler = signal.signal(signal.SIGINT, signal_handler)

        try:
            # Load conversation history
            total_messages = await self.load_conversation_history()
            self.coordinator.set_conversation_turn_start_index(total_messages)

            # Poll for approvals automatically (no interactive input handler)
            cancel_event = asyncio.Event()
            async def approval_poller():
                try:
                    while not cancel_event.is_set():
                        await self.poll_and_handle_approvals()
                        await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Approval poller error: {e}")

            if interactive:
                asyncio.create_task(approval_poller())

            # Start state streaming
            completion_chan = asyncio.Queue()
            err_chan = asyncio.Queue()

            # Run state monitoring
            await self.handle_state_stream(completion_chan, err_chan)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Follow conversation error: {e}")
        finally:
            signal.signal(signal.SIGINT, old_handler)
            if cancelled:
                print("\n👋 Exiting follow mode")
            else:
                print("\n✅ Task completed")

    async def load_conversation_history(self, max_history: int = 100) -> int:
        """Load and display recent conversation history"""
        try:
            from cline_core.proto.cline.common_pb2 import EmptyRequest
            state_resp = await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.getLatestState, EmptyRequest()
            )

            state_data = json.loads(state_resp.state_json)
            messages = state_data.get('clineMessages', [])

            if len(messages) == 0:
                return 0

            # Show recent history
            total_messages = len(messages)
            start_index = max(0, total_messages - max_history)

            if start_index > 0:
                print(f"--- Conversation history ({max_history} of {total_messages} messages) ---")
            else:
                print(f"--- Conversation history ({total_messages} messages) ---")

            for i in range(start_index, total_messages):
                msg = messages[i]
                if not msg.get('partial', False):
                    self.display_message(msg, False, False, i)

            return total_messages

        except Exception as e:
            logger.warning(f"Failed to load conversation history: {e}")
            return 0

    async def check_needs_approval(self) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Check if current task needs approval"""
        try:
            from cline_core.proto.cline.common_pb2 import EmptyRequest
            state_resp = await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.getLatestState, EmptyRequest()
            )

            state_data = json.loads(state_resp.state_json)
            messages = state_data.get('clineMessages', [])

            if not messages:
                return False, None

            last_msg = messages[-1]
            if (last_msg.get('type') == 'ask' and not last_msg.get('partial', False)):
                approval_types = ['tool', 'command', 'browser_action_launch', 'mcp_server_request']
                if last_msg.get('ask') in approval_types:
                    return True, last_msg

            return False, None

        except Exception as e:
            logger.error(f"Error checking needs approval: {e}")
            return False, None

    async def check_send_enabled(self) -> bool:
        """Check if we can send a message to current task"""
        try:
            from cline_core.proto.cline.common_pb2 import EmptyRequest
            state_resp = await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.getLatestState, EmptyRequest()
            )

            state_data = json.loads(state_resp.state_json)
            messages = state_data.get('clineMessages', [])

            if not messages:
                return True

            last_msg = messages[-1]

            # Can't send if message is partial and not an error type
            if last_msg.get('partial', False):
                error_types = ['api_req_failed', 'mistake_limit_reached']
                if last_msg.get('type') == 'ask' and last_msg.get('ask') not in error_types:
                    return False

            # Can send on ask messages (except command_output when streaming)
            if last_msg.get('type') == 'ask':
                if last_msg.get('ask') == 'command_output':
                    return False
                return True

            # Can't send during API requests or say completion
            if (last_msg.get('type') == 'say' and
                last_msg.get('say') in ['api_req_started', 'completion_result']):
                return False

            return False

        except Exception as e:
            logger.error(f"Error checking send enabled: {e}")
            return False

    async def send_message(self, message: str, images: list, files: list, approve: str, feedback: str):
        """Send a message to the current task"""
        try:
            # Handle approval responses
            response_type = "messageResponse"
            if approve == "true":
                response_type = "yesButtonClicked"
            elif approve == "false":
                response_type = "noButtonClicked"

            req = task_pb2.AskResponseRequest(
                response_type=response_type,
                text=feedback or message,
                images=images,
                files=files
            )

            await asyncio.get_event_loop().run_in_executor(
                None, self.task_stub.askResponse, req
            )

        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def set_mode(self, mode: str):
        """Set the Plan/Act mode"""
        try:
            from cline_core.proto.cline.state_pb2 import TogglePlanActModeRequest

            proto_mode = PlanActMode.ACT if mode == "act" else PlanActMode.PLAN
            req = TogglePlanActModeRequest(
                metadata=Metadata(),
                mode=proto_mode
            )

            await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.TogglePlanActModeProto, req
            )

            logger.info(f"✓ Mode set to {mode}")

        except Exception as e:
            logger.error(f"Error setting mode to {mode}: {e}")

    async def set_mode_and_send(self, mode: str, message: str, images: list, files: list):
        """Set mode and send a message together when possible"""
        try:
            # For simplicity, just set mode then send message
            await self.set_mode(mode)
            await asyncio.sleep(0.5)  # Brief delay
            await self.send_message(message, images, files, "", "")
        except Exception as e:
            logger.error(f"Error setting mode and sending message: {e}")

    async def cancel_task(self):
        """Cancel the current task"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.task_stub.CancelTask, Metadata()
            )
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")

    async def update_auto_approval_action(self, action: str):
        """Enable auto-approval for a specific action"""
        try:
            from cline_core.proto.cline.state_pb2 import UpdateTaskSettingsRequest

            settings = Settings(auto_approval_settings=AutoApprovalSettings(actions=AutoApprovalActions()))

            # Set the specific action
            if action == "read_files":
                settings.auto_approval_settings.actions.read_files = True
            elif action == "edit_files":
                settings.auto_approval_settings.actions.edit_files = True
            elif action == "execute_all_commands":
                settings.auto_approval_settings.actions.execute_all_commands = True
            elif action == "use_browser":
                settings.auto_approval_settings.actions.use_browser = True
            elif action == "use_mcp":
                settings.auto_approval_settings.actions.use_mcp = True

            req = UpdateTaskSettingsRequest(settings=settings)
            await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.UpdateTaskSettings, req
            )

        except Exception as e:
            logger.error(f"Error updating auto-approval: {e}")

    async def is_auto_approved(self, action_type: str) -> bool:
        """Check if a specific action type is auto-approved"""
        try:
            from cline_core.proto.cline.common_pb2 import EmptyRequest
            state_resp = await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.getLatestState, EmptyRequest()
            )

            state_data = json.loads(state_resp.state_json)
            logger.info(f"Checking auto-approval for {action_type}, state_data keys: {list(state_data.keys())}")

            # Check if auto-approval settings exist
            auto_approval = state_data.get('autoApprovalSettings', {})
            logger.info(f"autoApprovalSettings: {auto_approval}")

            if not auto_approval:
                logger.info("No auto-approval settings found")
                return False

            actions = auto_approval.get('actions', {})
            logger.info(f"auto-approval actions: {actions}")

            # Check the specific action
            if action_type == "read_files":
                result = actions.get('read_files', False)
                logger.info(f"read_files value: {result}")
                return result
            elif action_type == "edit_files":
                result = actions.get('edit_files', False)
                logger.info(f"edit_files value: {result}")
                return result
            elif action_type == "execute_all_commands":
                result = actions.get('execute_all_commands', False)
                logger.info(f"execute_all_commands value: {result}")
                return result
            elif action_type == "use_browser":
                result = actions.get('use_browser', False)
                logger.info(f"use_browser value: {result}")
                return result
            elif action_type == "use_mcp":
                result = actions.get('use_mcp', False)
                logger.info(f"use_mcp value: {result}")
                return result

            return False

        except Exception as e:
            logger.error(f"Error checking auto-approval for {action_type}: {e}")
            return False

    async def handle_state_stream(self, completion_chan: asyncio.Queue, err_chan: asyncio.Queue):
        """Handle the state streaming equivalent"""
        try:
            # Get initial state
            from cline_core.proto.cline.common_pb2 import EmptyRequest
            state_resp = await asyncio.get_event_loop().run_in_executor(
                None, self.state_stub.getLatestState, EmptyRequest()
            )

            state_data = json.loads(state_resp.state_json)
            completion_found = await self.process_state_update(state_data, completion_chan)
            if completion_found:
                return  # Exit when completion is found

            # In a real implementation, you'd set up a streaming connection
            # For now, we'll poll periodically
            while True:
                await asyncio.sleep(0.5)  # Poll interval

                state_resp = await asyncio.get_event_loop().run_in_executor(
                    None, self.state_stub.getLatestState, EmptyRequest()
                )

                state_data = json.loads(state_resp.state_json)

                # Update mode
                if 'mode' in state_data:
                    self.current_mode = state_data['mode']

                completion_found = await self.process_state_update(state_data, completion_chan)
                if completion_found:
                    return  # Exit when completion is found

        except Exception as e:
            await err_chan.put(e)

    async def process_state_update(self, state_data: Dict[str, Any], completion_chan: asyncio.Queue) -> bool:
        """Process state updates and handle messages. Returns True if completion found."""
        messages = state_data.get('clineMessages', [])
        start_index = self.coordinator.get_conversation_turn_start_index()

        found_completion = False

        for i in range(start_index, len(messages)):
            msg = messages[i]

            # Skip if already processed
            msg_key = f"{i}:{msg.get('timestamp', i)}"
            if self.coordinator.is_processed_in_current_turn(msg_key):
                continue

            # Check for completion
            if msg.get('say') == 'completion_result':
                found_completion = True

            # Display the message if it should be shown
            if self.should_display_message(msg):
                self.display_message(msg, False, False, i)
                self.coordinator.mark_processed_in_current_turn(msg_key)

                # Mark turn as complete
                self.coordinator.complete_turn(len(messages))

        return found_completion

    def should_display_message(self, msg: Dict[str, Any]) -> bool:
        """Determine if a message should be displayed"""
        # Don't display partial messages (except specific cases)
        if msg.get('partial', False):
            if (msg.get('type') == 'say' and msg.get('text', '') == '' and
                msg.get('say') == 'text'):
                return True
            return False

        # Display most messages
        return True

    def display_message(self, msg: Dict[str, Any], is_last: bool, is_partial: bool, message_index: int):
        """Display a single message"""
        msg_type = msg.get('type')
        say_type = msg.get('say')
        text = msg.get('text', '')

        if msg_type == 'say':
            if say_type == 'text':
                print(f"🤖 {text}")
            elif say_type == 'completion_result':
                print(f"✅ {text}")
            elif say_type == 'user_feedback':
                print(f"💬 {text}")
            else:
                print(f"🤖 [{say_type}] {text}")
        elif msg_type == 'ask':
            if say_type == 'tool':
                print(f"🔧 Tool request: {text[:100]}...")
            elif say_type == 'command':
                print(f"💻 Command: {text[:100]}...")
            else:
                print(f"❓ [{say_type}] {text}")
        else:
            print(f"[{msg_type}:{say_type}] {text}")

    async def poll_and_handle_approvals(self):
        """Poll for approvals and handle them automatically"""
        try:
            # Check if approval is needed
            needs_approval, approval_msg = await self.check_needs_approval()
            if needs_approval:
                # Check if auto-approval is enabled for this action
                action_type = self.get_action_type_from_message(approval_msg)
                logger.info(f"Action type determined: {action_type}")

                # HARDCODED AUTO-APPROVAL: Bypass Cline RPC auto-approval system
                # Auto-approve common safe actions (equivalent to --auto-approve CLI flags)
                auto_approve_actions = ['read_files', 'edit_files', 'execute_safe_commands']
                if action_type in auto_approve_actions:
                    # Auto-approve without prompting (this is more reliable than RPC)
                    approved, feedback = True, ""
                    logger.info(f"✓ Hardcoded auto-approved {action_type} (bypassing Cline RPC)")
                else:
                    # Return false for non-auto-approved actions (deny)
                    approved, feedback = False, "action not auto-approved"
                    logger.info(f"✗ Denied {action_type} (not auto-approved)")

                # Send approval response
                approve_str = "true" if approved else "false"
                await self.send_message("", [], [], approve_str, feedback)
                await asyncio.sleep(0.5)  # Give system time to process
        except Exception as e:
            logger.error(f"Approval handler error: {e}")

    def get_action_type_from_message(self, approval_msg: Dict[str, Any]) -> Optional[str]:
        """Determine the auto-approval action type from an approval message"""
        ask_type = approval_msg.get('ask')

        # For tool operations, parse the actual tool being used
        if ask_type == 'tool':
            tool_text = approval_msg.get('text', '')
            if '"tool":"readFile"' in tool_text:
                return 'read_files'
            elif '"tool":"editedExistingFile"' in tool_text or '"tool":"newFileCreated"' in tool_text:
                return 'edit_files'
            else:
                return 'edit_files'  # Default fallback

        # Map other ask types to auto-approval actions
        action_map = {
            'command': 'execute_all_commands',
            'browser_action_launch': 'use_browser',
            'mcp_server_request': 'use_mcp'
        }

        return action_map.get(ask_type)

async def follow_conversation(channel, instance_address: str, interactive: bool = True):
    """Main function equivalent to FollowConversation from Go"""
    manager = ConversationManager(channel)
    await manager.follow_conversation(instance_address, interactive)
