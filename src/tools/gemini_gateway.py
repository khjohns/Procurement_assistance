# tools/gemini_gateway.py
import structlog
import os
import json
import google.generativeai as genai
from typing import Optional, Dict, Any

logger = structlog.get_logger()

class GeminiGateway:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.default_model = 'gemini-2.5-flash'
        logger.info("GeminiGateway initialized with gemini-2.5-flash model")
    
    async def generate(self, 
                      prompt: str, 
                      data: Optional[Dict[str, Any]] = None,
                      model: Optional[str] = None,
                      temperature: float = 0.7,
                      response_mime_type: Optional[str] = None) -> str:
        """
        Sends a prompt to the Gemini API and returns the generated response.
        
        Args:
            prompt: The prompt text
            data: Optional data to include (for backwards compatibility)
            model: Model name to use (default: gemini-2.5-flash)
            temperature: Temperature for generation (0.0-1.0)
            response_mime_type: Expected MIME type of response (e.g., "application/json")
        """
        logger.info("Sending prompt to Gemini API", 
                   prompt_length=len(prompt), 
                   model=model or self.default_model,
                   temperature=temperature)
        
        try:
            # Velg modell
            model_name = model or self.default_model
            
            # Konfigurer generation config
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": 2048,
            }
            
            # Hvis response_mime_type er satt, bruk det
            if response_mime_type == "application/json":
                generation_config["response_mime_type"] = "application/json"
            
            # Opprett modell med config
            gemini_model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config
            )
            
            # Hvis data er gitt, legg det til prompten (for bakoverkompatibilitet)
            if data:
                full_prompt = f"{prompt}\n\nData: {json.dumps(data, ensure_ascii=False)}"
            else:
                full_prompt = prompt
            
            # Kall Gemini API
            response = await gemini_model.generate_content_async(full_prompt)
            
            # Returner teksten fra svaret
            response_text = response.text
            logger.info("Received response from Gemini API", 
                       response_length=len(response_text))
            return response_text
            
        except Exception as e:
            logger.error("Error during Gemini API call", error=str(e))
            # Hvis JSON forventes, returner en feil-JSON
            if response_mime_type == "application/json":
                return json.dumps({
                    "error": f"Gemini API error: {str(e)}",
                    "status": "failed"
                })
            else:
                return f"Feil ved kall til Gemini API: {e}"