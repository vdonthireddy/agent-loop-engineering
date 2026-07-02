import re
from utils.llm import call_agent

class GlobalState:
    def __init__(self):
        self.state = {}
        
    def get(self, key):
        return self.state.get(key)
        
    def set(self, key, value):
        self.state[key] = value

class LoopStrategy:
    def __init__(self, phase_name, phase_config):
        self.phase_name = phase_name
        self.config = phase_config

    def execute(self, context):
        raise NotImplementedError("Subclasses must implement execute()")

class LinearStrategy(LoopStrategy):
    def execute(self, context):
        actor_config = self.config.get('actor')
        if not actor_config:
            raise ValueError(f"Actor configuration missing for {self.phase_name}")
            
        system_prompt = actor_config['system_prompt']
        user_prompt = actor_config['user_prompt_template'].format(
            feedback_prompt="",
            **context
        )
        
        print(f">>> Starting {self.phase_name.capitalize()} (Linear)")
        response = call_agent(system_prompt, user_prompt)
        
        if actor_config.get('extract_code', False):
            code_match = re.search(r'```(?:python)?\n(.*?)\n```', response, re.DOTALL)
            if code_match:
                return code_match.group(1)
        return response

class ActorCriticStrategy(LoopStrategy):
    def execute(self, context, max_retries=3):
        actor_config = self.config.get('actor')
        critic_config = self.config.get('critic')
        
        if not actor_config or not critic_config:
            raise ValueError(f"Actor or Critic missing for {self.phase_name}")
            
        feedback = None
        for attempt in range(max_retries):
            print(f"\n[Attempt {attempt+1}/{max_retries}]")
            
            # --- ACTOR ---
            system_prompt = actor_config['system_prompt']
            feedback_prompt = ""
            if feedback:
                feedback_prompt = actor_config.get('feedback_prompt_template', '').format(feedback=feedback)
                
            user_prompt = actor_config['user_prompt_template'].format(
                feedback_prompt=feedback_prompt,
                **context
            )
            
            print(f">>> Starting {self.phase_name.capitalize()} Actor")
            response = call_agent(system_prompt, user_prompt)
            
            artifact = response
            if actor_config.get('extract_code', False):
                code_match = re.search(r'```(?:python)?\n(.*?)\n```', response, re.DOTALL)
                if code_match:
                    artifact = code_match.group(1)
                    
            # --- CRITIC ---
            critic_sys = critic_config['system_prompt']
            critic_user = critic_config['user_prompt_template'].format(
                artifact=artifact,
                **context
            )
            
            print(f">>> Starting {self.phase_name.capitalize()} Critic")
            critic_response = call_agent(critic_sys, critic_user)
            
            print(f"\n--- {self.phase_name.capitalize()} Critic Review ---")
            print(critic_response)
            print("----------------------------\n")
            
            is_pass = "PASS" in critic_response.upper()
            is_fail = "FAIL" in critic_response.upper()
            
            if is_pass and not is_fail:
                print(">> Critic Approved!")
                return artifact
            else:
                print(">> Critic Failed. Providing feedback to Actor...")
                feedback = critic_response
                
        print(">> Max retries exceeded. Critic did not approve.")
        return None

class LoopFactory:
    @staticmethod
    def create(phase_name, phase_config):
        strategy = phase_config.get('loop_strategy', 'linear')
        if strategy == 'actor_critic':
            return ActorCriticStrategy(phase_name, phase_config)
        elif strategy == 'linear':
            return LinearStrategy(phase_name, phase_config)
        else:
            raise ValueError(f"Unknown loop strategy: {strategy}")

class AgentEngine:
    def __init__(self, config):
        self.config = config
        self.state = GlobalState()

    def run_workflow(self):
        workflow = self.config.get('workflow')
        if not workflow:
            raise ValueError("No workflow defined in configuration.")
            
        print(f"\nStarting Workflow: {workflow.get('name', 'Unnamed')}")
        print("==============================")
        
        for step in workflow.get('steps', []):
            phase_name = step.get('phase')
            inputs = step.get('inputs', [])
            output_key = step.get('output_key')
            
            print(f"\nExecuting Phase: {phase_name.upper()}")
            
            # Prepare context from state
            context = {}
            for inp in inputs:
                val = self.state.get(inp)
                if val is None:
                    print(f"Warning: Missing input '{inp}' for phase '{phase_name}'")
                context[inp] = val
                
            # Create and execute loop strategy
            phase_config = self.config['phases'].get(phase_name)
            if not phase_config:
                raise ValueError(f"Phase {phase_name} is not defined in phases block.")
                
            loop_strategy = LoopFactory.create(phase_name, phase_config)
            artifact = loop_strategy.execute(context)
            
            if not artifact:
                print(f"Pipeline aborted at Phase {phase_name.upper()}.")
                return False
                
            # Save output to state
            if output_key:
                self.state.set(output_key, artifact)
                
        print("\nWorkflow completed successfully!")
        return True
