import os
import json
import traceback
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from pydantic import BaseModel
from dataclasses import asdict
import logfire
from fastapi import WebSocket
from dotenv import load_dotenv
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai import Agent
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse
from agents.web_surfer import WebSurfer
from agents.code_agent import coder_agent
from agents.planner_agent import planner_agent
from agents.orchestrator_agent import orchestrator_agent, orchestrator_deps
load_dotenv()


# Main Orchestrator Class
class SystemInstructor:
    def __init__(self):
        self.websocket: Optional[WebSocket] = None
        self.stream_output: Optional[StreamResponse] = None
        self.orchestrator_response: List[StreamResponse] = []
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging with proper formatting"""
        logfire.configure(
            send_to_logfire='if-token-present',
            token=os.getenv("LOGFIRE_TOKEN"),
            scrubbing=False,
        )

    async def _safe_websocket_send(self, message: Any) -> bool:
        """Safely send message through websocket with error handling"""
        try:
            if self.websocket and self.websocket.client_state.CONNECTED:
                await self.websocket.send_text(json.dumps(asdict(message)))
                return True
            return False
        except Exception as e:
            logfire.error(f"WebSocket send failed: {str(e)}")
            return False

    async def run(self, task: str, websocket: WebSocket) -> List[Dict[str, Any]]:
        """Main orchestration loop with comprehensive error handling"""
        self.websocket = websocket
        stream_output = StreamResponse(
            agent_name="Orchestrator",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )
        self.orchestrator_response.append(stream_output)
        deps_for_orchestrator =  orchestrator_deps(
            websocket=self.websocket,
            stream_output=stream_output
        )
        try:
            # Initialize system
            await self._safe_websocket_send(stream_output)
            stream_output.steps.append("Agents initialized successfully")
            await self._safe_websocket_send(stream_output)

            orchestrator_response = await orchestrator_agent.run(
                user_prompt=task,
                deps=deps_for_orchestrator
            )
            stream_output.output = orchestrator_response
            await self._safe_websocket_send(stream_output)

            logfire.info("Task completed successfully")
            return [asdict(i) for i in self.orchestrator_response]

        except Exception as e:
            error_msg = f"Critical orchestration error: {str(e)}\n{traceback.format_exc()}"
            logfire.error(error_msg)
            
            if stream_output:
                stream_output.output = error_msg
                stream_output.status_code = 500
                self.orchestrator_response.append(stream_output)
                await self._safe_websocket_send(stream_output)
            
            # Even in case of critical error, return what we have
            return [asdict(i) for i in self.orchestrator_response]

        finally:
            logfire.info("Orchestration process complete")
            # Clear any sensitive data
    async def shutdown(self):
        """Clean shutdown of orchestrator"""
        try:
            # Close websocket if open
            if self.websocket:
                await self.websocket.close()
            
            # Clear all responses
            self.orchestrator_response = []
            
            logfire.info("Orchestrator shutdown complete")
            
        except Exception as e:
            logfire.error(f"Error during shutdown: {str(e)}")
            raise