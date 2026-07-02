import os
import argparse
import yaml

from engine import AgentEngine

SPECS_DIR = "specs"
WORKSPACE_DIR = "workspace"
CONFIG_FILE = "config/agents.yaml"

def read_specs(specs_dir):
    specs_content = ""
    for root, dirs, files in os.walk(specs_dir):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    specs_content += f"\n\n--- SPEC: {file_path} ---\n\n"
                    lines = f.readlines()[:500]
                    specs_content += "".join(lines)
    return specs_content

def run_pipeline():
    if not os.path.exists(SPECS_DIR):
        print(f"Error: {SPECS_DIR} directory not found.")
        return

    # Load agent configuration
    with open(CONFIG_FILE, "r") as f:
        config = yaml.safe_load(f)
        
    engine = AgentEngine(config)

    print("\n==============================")
    print("1. Reading Specs...")
    specs = read_specs(SPECS_DIR)
    if not specs.strip():
        print("No specifications found.")
        return
        
    # Inject initial state
    engine.state.set_memory("specs", specs)
    
    # Run dynamic workflow
    success = engine.run_workflow()
    
    if not success:
        print("\nWorkflow aborted.")
        return
        
    print("\nWorkflow completed successfully!")
    print(f"Artifacts have been dynamically saved to the {WORKSPACE_DIR}/ directory.")

def main():
    parser = argparse.ArgumentParser(description="Loop Engineering Orchestrator")
    parser.add_argument(
        "--agent", 
        type=str, 
        choices=["pipeline"],
        default="pipeline",
        help="Run the configured YAML workflow."
    )
    
    args = parser.parse_args()
    
    if args.agent == "pipeline":
        run_pipeline()

if __name__ == "__main__":
    main()
