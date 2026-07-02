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
    engine.state.set("specs", specs)
    
    # Run dynamic workflow
    success = engine.run_workflow()
    
    if not success:
        print("\nWorkflow aborted.")
        return
        
    print("\n==============================")
    print("Saving Deployment Artifacts")
    
    code_dir = os.path.join(WORKSPACE_DIR, "code")
    test_dir = os.path.join(WORKSPACE_DIR, "test")
    deploy_dir = os.path.join(WORKSPACE_DIR, "deploy")
    
    os.makedirs(code_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(deploy_dir, exist_ok=True)
    
    code = engine.state.get("code")
    if code:
        code_path = os.path.join(code_dir, "deployed_app.py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)
            
    manifest = engine.state.get("manifest")
    if manifest:
        manifest_path = os.path.join(deploy_dir, "manifest.txt")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest)
            
    tests = engine.state.get("tests")
    if tests:
        test_path = os.path.join(test_dir, "test_app.py")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(tests)
            
    print(f"Deployment complete! Files saved to {WORKSPACE_DIR}/")

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
