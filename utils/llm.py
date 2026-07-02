import os
from dotenv import load_dotenv
import ollama

load_dotenv()
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5-coder:0.5b")

def call_agent(system_prompt, user_prompt):
    print(f"[*] Calling Agent (Model: {MODEL_NAME})...")
    response = ollama.chat(model=MODEL_NAME, messages=[
        {
            'role': 'system',
            'content': system_prompt
        },
        {
            'role': 'user',
            'content': user_prompt
        }
    ])
    return response['message']['content']
