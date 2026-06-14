import sys
from solidworks_ai.cli import SolidWorksAICopilotCLI

def main() -> None:
    """Entry point for the SolidWorks AI Copilot."""
    project_name = "DefaultProject"
    
    # Check if a custom project name was specified in the CLI args
    if len(sys.argv) > 1:
        project_name = sys.argv[1]
        
    try:
        cli = SolidWorksAICopilotCLI(project_name=project_name)
        cli.run()
    except KeyboardInterrupt:
        print("\nExiting Copilot...")
        sys.exit(0)
    except Exception as e:
        print(f"Startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
