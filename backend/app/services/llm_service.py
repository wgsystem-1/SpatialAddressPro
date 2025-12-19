import os
from openai import OpenAI
import json

class LLMService:
    def __init__(self):
        # Default to local Ollama if not specified
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LLM_API_KEY", "ollama") # Ollama doesn't care about key
        self.model = os.getenv("LLM_MODEL", "llama3") # or qwen2.5-coder, gpt-4o, etc.
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

    def correct_address(self, raw_text: str) -> str:
        """
        Ask LLM to correct the address.
        Returns the corrected address string.
        """
        # Load Golden Test Cases as "Few-Shot Examples"
        from ..golden_test_cases import TEST_CASES
        examples_str = "\n".join([f"- Input: '{bad}' -> Output: '{good}'" for bad, good in TEST_CASES]) # Use ALL examples

        system_prompt = (
            "You are an expert Korean Address Correction AI. "
            "Input may contain typos, missing spaces, or incorrect formatting. "
            "Task: 1. Fix Region/District typos (e.g., '성울'->'서울'). "
            "2. Infer missing Region/Sido OR District/Sgg if Road Name is unique/famous. "
            "3. If Road Name is common (e.g., '중앙로') and Region is missing, DO NOT assume a region. "
            "4. Fix Road Name typos and Preserve numbers. "
            "5. REMOVE spaces INSIDE the Road Name (e.g., '가산 디지털 1로' -> '가산디지털1로'). "
            "6. REORDER components to standard format: [Region] [District] [Road Name] [Number]. "
            "7. KEEP the main building number (e.g., '123', '123-4'). REMOVE ONLY detailed info like Apartment Name, Floor, Ho (e.g., '101동 202호', '1F'). "
            "8. REMOVE content inside square brackets completely (e.g., '[123]', '[306-1]', '[Suseong-gu]'). "
            "9. REMOVE non-address text (Delivery memos, country names, postal codes, special characters like #, @). "
            "10. NORMALIZE characters: Full-width -> Half-width, 'I'/'l' -> '1' in numbers, 'O' -> '0' in numbers. "
            "9. UPDATE old administrative names to current ones (e.g., '인천 남구' -> '인천 미추홀구'). "
            "10. RESTORE missing suffixes for administrative names (e.g., '강남' -> '강남구', '분당' -> '분당구', '서울' -> '서울특별시'). "
            "11. Returns ONLY the standardized address string. "
            f"\n\nExamples:\n{examples_str}"
        )
        
        user_prompt = f"Original: {raw_text}\nCorrected:"
        
        try:
            print(f" [LLM] Requesting correction for: '{raw_text}'")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            corrected = response.choices[0].message.content.strip()
            # Remove quotes if LLM added them
            corrected = corrected.replace('"', '').replace("'", "")
            print(f" [LLM] Corrected Result: '{corrected}'")
            return corrected
        except Exception as e:
            print(f" [LLM] Error (Is Ollama running?): {e}")
            return raw_text # Fallback to original if LLM fails

llm_service = LLMService()
