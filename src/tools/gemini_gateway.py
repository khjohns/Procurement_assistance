import structlog
import os
import json
import google.generativeai as genai # Import the actual Gemini API client

logger = structlog.get_logger()

class GeminiGateway:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key) # Konfigurer Gemini API med nøkkelen
        self.model = genai.GenerativeModel('gemini-2.5-flash') # Bruk gemini-2.5-flash modellen
        logger.info("GeminiGateway initialized with gemini-2.5-flash model")

    async def generate(self, prompt: str, data: dict) -> str:
        """
        Sends a prompt and data to the Gemini API and returns the generated response.
        """
        logger.info("Sending prompt to Gemini API", prompt_length=len(prompt), data=data)
        
        try:
            # Kombiner prompt og data for å sende til Gemini API
            full_prompt = f"{prompt}\n\nAnskaffelsesforespørsel: {json.dumps(data, ensure_ascii=False)}"
            
            # Kall Gemini API
            response = await self.model.generate_content_async(full_prompt)
            
            # Returner teksten fra svaret
            response_text = response.text
            logger.info("Received response from Gemini API", response_text=response_text)
            return response_text
        except Exception as e:
            logger.error("Error during Gemini API call", error=str(e))
            # Returner en feilmelding som kan parses av TriageAgent
            return json.dumps({"farge": "RØD", "begrunnelse": f"Feil ved kall til Gemini API: {e}", "confidence": 0.0})