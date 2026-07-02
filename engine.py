import re
from utils.llm import call_agent

class AgentEngine:
    def __init__(self, config):
        self.config = config

    def run_actor(self, phase_name, context, feedback=None):
        phase_config = self.config['phases'].get(phase_name)
        if not phase_config or 'actor' not in phase_config:
            raise ValueError(f"Actor configuration not found for phase: {phase_name}")
            
        actor_config = phase_config['actor']
        
        system_prompt = actor_config['system_prompt']
        
        feedback_prompt = ""
        if feedback:
            feedback_prompt = actor_config.get('feedback_prompt_template', '').format(feedback=feedback)
            
        # Safely format context variables
        user_prompt = actor_config['user_prompt_template'].format(
            feedback_prompt=feedback_prompt,
            **context
        )
        
        print(f">>> Starting {phase_name.capitalize()} Actor")
        response = call_agent(system_prompt, user_prompt)
        
        if actor_config.get('extract_code', False):
            code_match = re.search(r'```(?:python)?\n(.*?)\n```', response, re.DOTALL)
            if code_match:
                return code_match.group(1)
                
        return response

    def run_critic(self, phase_name, context, artifact):
        phase_config = self.config['phases'].get(phase_name)
        if not phase_config or 'critic' not in phase_config:
            raise ValueError(f"Critic configuration not found for phase: {phase_name}")
            
        critic_config = phase_config['critic']
        system_prompt = critic_config['system_prompt']
        
        user_prompt = critic_config['user_prompt_template'].format(
            artifact=artifact,
            **context
        )
        
        print(f">>> Starting {phase_name.capitalize()} Critic")
        response = call_agent(system_prompt, user_prompt)
        
        print(f"\n--- {phase_name.capitalize()} Critic Review ---")
        print(response)
        print("----------------------------\n")
        
        is_pass = "PASS" in response.upper()
        is_fail = "FAIL" in response.upper()
        
        if is_pass and not is_fail:
            return True, response
        elif is_fail and not is_pass:
            return False, response
        return False, response

    def run_loop(self, phase_name, context, max_retries=3):
        feedback = None
        for attempt in range(max_retries):
            print(f"\n[Attempt {attempt+1}/{max_retries}]")
            artifact = self.run_actor(phase_name, context, feedback)
            
            passed, new_feedback = self.run_critic(phase_name, context, artifact)
            if passed:
                print(">> Critic Approved!")
                return artifact
            else:
                print(">> Critic Failed. Providing feedback to Actor...")
                feedback = new_feedback
                
        print(">> Max retries exceeded. Critic did not approve.")
        return None
