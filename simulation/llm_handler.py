# simulation/llm_handler.py

import requests
from dotenv import load_dotenv
import os

class LLMHandler:
    """
    Handles interaction with the OpenAI GPT-4.1 mini API for narrative and embedding generation.
    """
    def __init__(self, api_key=None, model="gpt-4.1-mini"):
        load_dotenv()
        self.api_key = api_key or os.getenv("API_KEY")
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"  # No trailing slash per OpenAI docs
        self.embedding_url = "https://api.openai.com/v1/embeddings"

    def generate_narrative(self, prompt, max_tokens=512):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.8
        }
        response = requests.post(self.base_url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"OpenAI API error: {response.status_code} {response.text}")
            raise
        return response.json()['choices'][0]['message']['content']

    def get_embedding(self, text):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "text-embedding-ada-002",
            "input": text
        }
        response = requests.post(self.embedding_url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"OpenAI API error: {response.status_code} {response.text}")
            raise
        return response.json()['data'][0]['embedding']

    def check_llm_api(self):
        """Check if the OpenAI LLM API is reachable and working."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Say hello."}],
            "max_tokens": 10,
            "temperature": 0.0
        }
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return True, response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"LLM API check failed: {e}")
            return False, str(e)

