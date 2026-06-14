import json
import logging
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from solidworks_ai.config import GEMINI_API_KEY, MODEL_NAME
from solidworks_ai.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("GEMINI_API_KEY is not set in environment or config.")

    def query(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        db_features: List[Dict[str, Any]],
        cad_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sends the user request, chat history, database feature list,
        and current SolidWorks model summary to Gemini and returns the parsed JSON dict.
        """
        if not self.api_key:
            return {
                "explanation": "Gemini API key is not configured. Please set GEMINI_API_KEY environment variable.",
                "plan": [],
                "commands": [],
                "missing_parameters": []
            }

        # Build context prompt
        context = f"""
--- CURRENT PROJECT DATABASE MAPPED FEATURES ---
{json.dumps(db_features, indent=2)}

--- ACTIVE SOLIDWORKS FEATURE TREE SUMMARY ---
{json.dumps(cad_summary, indent=2)}
"""
        
        # Prepare contents
        contents = []
        
        # Add system prompt as a separate system instruction or first message
        # In newer generativeai libraries, we pass system_instruction to GenerativeModel constructor
        # We can reconstruct history for the chat
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [msg["content"]]})
            
        # Append latest context and message
        full_user_input = f"{context}\n\nUser Instruction: {user_message}"
        contents.append({"role": "user", "parts": [full_user_input]})

        try:
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                system_instruction=SYSTEM_PROMPT
            )
            
            # Request JSON output
            response = model.generate_content(
                contents,
                generation_config={"response_mime_type": "application/json"}
            )
            
            response_text = response.text.strip()
            logger.debug(f"Gemini raw response: {response_text}")
            
            # Parse response JSON
            data = json.loads(response_text)
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from Gemini response. Raw: {response.text}. Error: {e}")
            return {
                "explanation": "Internal Error: Received invalid JSON from AI.",
                "plan": [],
                "commands": [],
                "missing_parameters": []
            }
        except Exception as e:
            logger.error(f"Error querying Gemini: {e}")
            return {
                "explanation": f"Failed to connect to AI service: {e}",
                "plan": [],
                "commands": [],
                "missing_parameters": []
            }
        
    def generate_direct_response(self, prompt: str) -> str:
        """Helper for simple queries without structured response formatting constraints."""
        if not self.api_key:
            return "API Key not set."
        try:
            model = genai.GenerativeModel(model_name=MODEL_NAME)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error: {e}"
