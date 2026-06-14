import logging
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from solidworks_ai.ai.gemini_client import GeminiClient
from solidworks_ai.ai.parser import parse_commands_list, CommandType
from solidworks_ai.memory.context_manager import ContextManager

logger = logging.getLogger(__name__)

class DesignPlanner:
    def __init__(self, db_session: Session, project_name: str) -> None:
        self.db = db_session
        self.context_mgr = ContextManager(db_session)
        self.project = self.context_mgr.get_or_create_project(project_name)
        self.gemini = GeminiClient()
        self.pending_commands: List[Dict[str, Any]] = []
        self.pending_plan_steps: List[str] = []

    def get_project_id(self) -> int:
        return self.project.id

    def clear_pending_plan(self) -> None:
        """Resets the currently accumulated plan."""
        self.pending_commands = []
        self.pending_plan_steps = []

    def process_instruction(
        self,
        user_instruction: str,
        active_cad_summary: Dict[str, Any]
    ) -> Tuple[str, List[str], List[str]]:
        """
        Processes a user request by:
        1. Querying Gemini with current project history, db features, and cad state.
        2. Parsing the response JSON.
        3. Saving message history.
        4. Updating pending commands and steps.
        
        Returns:
            (explanation, plan_steps, missing_parameters)
        """
        # Retrieve context from database
        history = self.context_mgr.get_history(self.project.id)
        db_features = self.context_mgr.get_features(self.project.id)

        logger.info(f"Querying Gemini with instruction: '{user_instruction}'")
        
        # Get AI decision
        ai_response = self.gemini.query(
            user_message=user_instruction,
            history=history,
            db_features=db_features,
            cad_summary=active_cad_summary
        )

        explanation = ai_response.get("explanation", "")
        plan_steps = ai_response.get("plan", [])
        commands_dict_list = ai_response.get("commands", [])
        missing_params = ai_response.get("missing_parameters", [])

        # Validate commands using Pydantic parser
        if commands_dict_list:
            try:
                # This will raise an exception if invalid
                parse_commands_list(commands_dict_list)
                # If valid, accumulate or set the new pending commands
                self.pending_commands = commands_dict_list
                self.pending_plan_steps = plan_steps
            except ValueError as e:
                logger.error(f"Failed to parse commands proposed by AI: {e}")
                explanation = f"AI proposed an invalid operation. Error: {e}"
                self.pending_commands = []
                self.pending_plan_steps = []
        else:
            # If no commands proposed (e.g. planning mode / missing params), keep pending clear
            # or if we are building up iteratively, we can choose to keep or overwrite.
            # Here, we overwrite with the latest plan state.
            self.pending_commands = []
            self.pending_plan_steps = []

        # Record messages in DB history
        # User message
        self.context_mgr.add_message(self.project.id, "user", user_instruction)
        
        # AI response explanation
        ai_history_content = f"Explanation: {explanation}\nPlan: {plan_steps}\nCommands: {commands_dict_list}"
        self.context_mgr.add_message(self.project.id, "model", ai_history_content)

        return explanation, plan_steps, missing_params

    def get_pending_plan(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Returns the currently active pending commands and plan steps."""
        return self.pending_commands, self.pending_plan_steps
