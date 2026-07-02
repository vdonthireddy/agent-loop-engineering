import os
import argparse
import yaml

from engine import AgentEngine

SPECS_DIR = "specs"
DEPLOY_DIR = "deploy"
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
    os.makedirs(DEPLOY_DIR, exist_ok=True)
    
    code = engine.state.get("code")
    if code:
        deploy_path = os.path.join(DEPLOY_DIR, "deployed_app.py")
        with open(deploy_path, "w", encoding="utf-8") as f:
            f.write(code)
            
    manifest = engine.state.get("manifest")
    if manifest:
        manifest_path = os.path.join(DEPLOY_DIR, "manifest.txt")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest)
            
    tests = engine.state.get("tests")
    if tests:
        test_path = os.path.join(DEPLOY_DIR, "test_app.py")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(tests)
            
    print(f"Deployment complete! Files saved to {DEPLOY_DIR}/")

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
