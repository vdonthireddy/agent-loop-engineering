import os
import re
from utils.llm import call_agent

class WorkspaceState:
    def __init__(self, root_dir="workspace"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        self.memory = {}

    def get(self, key):
        if key in self.memory:
            return self.memory[key]
            
        key_dir = os.path.join(self.root_dir, key)
        if os.path.exists(key_dir) and os.path.isdir(key_dir):
            content = ""
            for root, _, files in os.walk(key_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        # Convert absolute path to relative for prompt context
                        rel_path = os.path.relpath(file_path, key_dir)
                        content += f"\n\n--- File: {rel_path} ---\n\n"
                        content += f.read()
            return content
        return None

    def set_memory(self, key, value):
        self.memory[key] = value

    def set_files(self, key, text_response, extract=True):
        key_dir = os.path.join(self.root_dir, key)
        os.makedirs(key_dir, exist_ok=True)
        
        if not extract:
            with open(os.path.join(key_dir, "output.txt"), "w", encoding="utf-8") as f:
                f.write(text_response)
            return

        # Matches Markdown pattern:
        # **File: path/to/file.py**
        # ```python
        # code...
        # ```
        pattern = r"\*\*File:\s*([^\*]+?)\*\*\n+```[a-zA-Z]*\n(.*?)```"
        matches = re.findall(pattern, text_response, re.DOTALL)
        
        if not matches:
            # Fallback for single file or poorly formatted output
            code_match = re.search(r'```(?:[a-zA-Z]+)?\n(.*?)\n```', text_response, re.DOTALL)
            if code_match:
                with open(os.path.join(key_dir, "app.py"), "w", encoding="utf-8") as f:
                    f.write(code_match.group(1))
            else:
                with open(os.path.join(key_dir, "output.txt"), "w", encoding="utf-8") as f:
                    f.write(text_response)
            return
            
        for filename, code in matches:
            filename = filename.strip().strip('`')
            file_path = os.path.join(key_dir, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

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
        return call_agent(system_prompt, user_prompt)

class ActorCriticStrategy(LoopStrategy):
    def execute(self, context, max_retries=3):
        actor_config = self.config.get('actor')
        critic_config = self.config.get('critic')
        
        if not actor_config or not critic_config:
            raise ValueError(f"Actor or Critic missing for {self.phase_name}")
            
        feedback = None
        for attempt in range(max_retries):
            print(f"\n[Attempt {attempt+1}/{max_retries}]")
            
            system_prompt = actor_config['system_prompt']
            feedback_prompt = ""
            if feedback:
                feedback_prompt = actor_config.get('feedback_prompt_template', '').format(feedback=feedback)
                
            user_prompt = actor_config['user_prompt_template'].format(
                feedback_prompt=feedback_prompt,
                **context
            )
            
            print(f">>> Starting {self.phase_name.capitalize()} Actor")
            actor_response = call_agent(system_prompt, user_prompt)
            
            critic_sys = critic_config['system_prompt']
            critic_user = critic_config['user_prompt_template'].format(
                artifact=actor_response,
                **context
            )
            
            print(f">>> Starting {self.phase_name.capitalize()} Critic")
            critic_response = call_agent(critic_sys, critic_user)
            
            print(f"\n--- {self.phase_name.capitalize()} Critic Review ---")
            print(critic_response)
            print("----------------------------\n")
            
            if "PASS" in critic_response.upper() and "FAIL" not in critic_response.upper():
                print(">> Critic Approved!")
                return actor_response
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
        self.state = WorkspaceState()

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
            
            context = {}
            for inp in inputs:
                val = self.state.get(inp)
                if val is None:
                    print(f"Warning: Missing input '{inp}' for phase '{phase_name}'")
                context[inp] = val or ""
                
            phase_config = self.config['phases'].get(phase_name)
            if not phase_config:
                raise ValueError(f"Phase {phase_name} is not defined in phases block.")
                
            loop_strategy = LoopFactory.create(phase_name, phase_config)
            artifact_response = loop_strategy.execute(context)
            
            if not artifact_response:
                print(f"Pipeline aborted at Phase {phase_name.upper()}.")
                return False
                
            if output_key:
                extract = phase_config.get('actor', {}).get('extract_code', True)
                self.state.set_files(output_key, artifact_response, extract)
                
        print("\nWorkflow completed successfully!")
        return True
