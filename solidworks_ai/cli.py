import os
import sys
import logging
import winreg
from typing import Dict, Any, List
import win32com.client
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.text import Text

from solidworks_ai.memory.database import SessionLocal, init_db
from solidworks_ai.cad.solidworks import SolidWorksConnection, SolidWorksError
from solidworks_ai.cad.reader import read_active_model_summary
from solidworks_ai.ai.planner import DesignPlanner
from solidworks_ai.executor.executor import CommandExecutor
from solidworks_ai.executor.validator import validate_commands
from solidworks_ai.ai.parser import parse_commands_list
from solidworks_ai.executor.rollback import RollbackHandler
from solidworks_ai.config import GEMINI_API_KEY, MODEL_NAME, save_config

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "solidworks_ai.log"), encoding='utf-8') 
        if not getattr(sys, 'frozen', False) else 
        logging.FileHandler(os.path.join(sys.executable, "..", "logs", "solidworks_ai.log"), encoding='utf-8')
    ]
)
logging.getLogger().handlers[0].setLevel(logging.INFO)

console = Console()

# Dark Theme Styles
DARK_PANEL_STYLE = "white on #181818"
DARK_BORDER_COLOR = "#333333"      # Dim border
DARK_CYAN = "#00e5ff"              # Cyber Cyan
DARK_GREEN = "#00ff7f"             # Neon Spring Green
DARK_AMBER = "#ffb300"             # Status Warning Amber
DARK_RED = "#ff1744"               # Neon Red

class StateMachine:
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    COMPLETED = "COMPLETED"

class SolidWorksAICopilotCLI:
    def __init__(self, project_name: str = "DefaultProject") -> None:
        self.project_name = project_name
        self.state = StateMachine.PLANNING
        
        # Initialize Database
        init_db()
        self.db = SessionLocal()
        
        # Connection wrappers
        self.sw_conn = SolidWorksConnection()
        self.connected_to_sw = False
        
        # Initialize API Key
        self._initialize_api_key()

        # Initialize Planner, Executor, and Rollback
        self.planner = DesignPlanner(self.db, project_name)
        self.executor = CommandExecutor(self.db, self.sw_conn)
        self.rollback_handler = RollbackHandler(self.db, self.sw_conn)

    def _initialize_api_key(self) -> None:
        """Verifies if API key exists. If missing, prompts the user to enter it."""
        global GEMINI_API_KEY
        if not GEMINI_API_KEY:
            console.print(Panel(
                "[bold yellow]Gemini API Key is missing.[/bold yellow] The Copilot needs this key to interpret natural language.\n"
                "You can get a free key from Google AI Studio: [cyan]https://aistudio.google.com/[/cyan]",
                title="API Key Configuration",
                style=DARK_PANEL_STYLE,
                border_style=DARK_AMBER
            ))
            key = Prompt.ask("[bold cyan]Enter your Gemini API Key[/bold cyan]").strip()
            if key:
                save_config(key)
                GEMINI_API_KEY = key
                os.environ["GEMINI_API_KEY"] = key
                genai.configure(api_key=key)
                console.print("[green]✓ Key successfully saved to config.json![/green]\n")
            else:
                console.print("[red]✗ Running without API Key. Conversation planning will be disabled.[/red]\n")
        else:
            genai.configure(api_key=GEMINI_API_KEY)

    def is_solidworks_installed(self) -> bool:
        """Inspects registry to verify if SolidWorks is installed on Windows."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def check_and_connect_sw(self) -> bool:
        """
        Auto-detects SolidWorks status:
        1. Checks installation.
        2. Checks running status.
        3. Prompts to launch if installed but closed.
        """
        if not self.is_solidworks_installed():
            console.print("[bold red]✗ SolidWorks Not Found[/bold red]")
            console.print("Please make sure SolidWorks Desktop is installed on this machine.\n")
            self.connected_to_sw = False
            return False

        # Verify running
        try:
            win32com.client.GetActiveObject("SldWorks.Application")
            self.sw_conn.connect()
            self.connected_to_sw = True
            return True
        except Exception:
            # Installed but not running
            console.print("[yellow]SolidWorks is installed but not running.[/yellow]")
            launch = Prompt.ask("Launch SolidWorks now? [Y/N]", default="Y").strip().upper()
            if launch == "Y":
                with console.status("[bold green]Launching SolidWorks..."):
                    try:
                        self.sw_conn.connect()
                        self.connected_to_sw = True
                        console.print("[green]✓ SolidWorks launched successfully.[/green]")
                        return True
                    except Exception as e:
                        console.print(f"[red]Failed to launch SolidWorks: {e}[/red]")
            self.connected_to_sw = False
            return False

    def print_status_header(self) -> None:
        """Displays dark-mode status dashboard."""
        status_text = Text()
        status_text.append("SolidWorksAI Copilot v1.0\n", style=f"bold {DARK_CYAN}")
        
        # Installed status
        if self.is_solidworks_installed():
            status_text.append("✓ SolidWorks Installed\n", style="green")
        else:
            status_text.append("✗ SolidWorks Not Found\n", style="red")

        # Connection status
        if self.connected_to_sw:
            status_text.append("✓ Connected to SolidWorks\n", style="green")
            # Check for active doc
            try:
                model = self.sw_conn.get_active_document()
                title = model.GetTitle()
                status_text.append(f"✓ Active Part Loaded: {title}\n", style="green")
            except Exception:
                status_text.append("✗ No Active Part Loaded (instruct AI or open a part to start)\n", style="yellow")
        else:
            status_text.append("✗ Connected to SolidWorks\n", style="red")

        status_text.append(f"Project: {self.project_name} | State: {self.state}\n", style=f"{DARK_CYAN}")
        
        console.print(Panel(
            status_text,
            title="System Status",
            style=DARK_PANEL_STYLE,
            border_style=DARK_BORDER_COLOR
        ))

    def run(self) -> None:
        # Detect and connect to SolidWorks
        self.check_and_connect_sw()
        self.print_status_header()
        
        while True:
            # Gather active model details for context
            cad_summary = {"features": []}
            if self.connected_to_sw:
                try:
                    model = self.sw_conn.get_active_document()
                    cad_summary = read_active_model_summary(model)
                except Exception:
                    pass

            # Prompt Loop
            prompt_str = f"({self.state}) > "
            user_input = Prompt.ask(prompt_str).strip()
            
            if not user_input:
                continue

            # Command Routing
            input_lower = user_input.lower()
            
            if input_lower in ["exit", "quit"]:
                console.print("[yellow]Exiting SolidWorksAI. Goodbye![/yellow]")
                break
                
            elif input_lower == "help":
                self.handle_help()
                
            elif input_lower == "show plan":
                self.handle_show_plan()
                
            elif input_lower == "show model":
                self.handle_show_model(cad_summary)
                
            elif input_lower == "history":
                self.handle_show_history()
                
            elif input_lower == "undo":
                self.handle_undo()
                
            elif input_lower == "redo":
                console.print("[yellow]Redo is not supported natively. Use checkpoints/rollback command to restore states.[/yellow]\n")
                
            elif input_lower == "save":
                self.handle_save()
                
            elif input_lower.startswith("load "):
                path = user_input[5:].strip().strip('"')
                self.handle_load(path)
                
            elif input_lower == "clear":
                self.handle_clear_history()
                
            elif input_lower.startswith("set key "):
                new_key = user_input[8:].strip()
                self.handle_change_key(new_key)
                
            elif input_lower.startswith("rollback "):
                parts = user_input.split()
                if len(parts) == 2 and parts[1].isdigit():
                    cp_id = int(parts[1])
                    self.handle_rollback(cp_id)
                else:
                    console.print("[red]Invalid rollback command. Use: rollback <id>[/red]\n")

            elif user_input.upper() in ["FINAL SUBMIT", "EXECUTE"]:
                self.handle_execution()
                
            else:
                # Direct natural language prompt
                self.handle_planning(user_input, cad_summary)

    def handle_help(self) -> None:
        table = Table(title="Interactive CLI Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="yellow")
        table.add_column("Description")
        
        table.add_row("help", "Displays this help menu")
        table.add_row("show plan", "Shows the current pending execution plan proposed by the AI")
        table.add_row("show model", "Shows the active SolidWorks model summary feature tree")
        table.add_row("history", "Prints conversation message history")
        table.add_row("undo", "Reverts the last completed operation (reverts CAD and DB state)")
        table.add_row("save", "Saves the active SolidWorks part document")
        table.add_row("load <filepath>", "Opens a Part (.sldprt) document from a physical file path")
        table.add_row("set key <api_key>", "Updates your Gemini API key and saves it locally")
        table.add_row("rollback <checkpoint_id>", "Rolls back both database and CAD models to a specific checkpoint ID")
        table.add_row("clear", "Clears the conversation memory and feature maps")
        table.add_row("FINAL SUBMIT / EXECUTE", "Executes the pending AI-designed plan in SolidWorks")
        table.add_row("exit / quit", "Terminates the CLI application")
        
        console.print(Panel(table, style=DARK_PANEL_STYLE, border_style=DARK_BORDER_COLOR))
        console.print()

    def handle_change_key(self, new_key: str) -> None:
        if new_key:
            save_config(new_key)
            global GEMINI_API_KEY
            GEMINI_API_KEY = new_key
            os.environ["GEMINI_API_KEY"] = new_key
            genai.configure(api_key=new_key)
            console.print("[green]✓ Gemini API Key updated successfully in config.json![/green]\n")
        else:
            console.print("[red]API Key cannot be empty.[/red]\n")

    def handle_show_plan(self) -> None:
        pending_cmds, pending_steps = self.planner.get_pending_plan()
        if pending_cmds:
            table = Table(title="Pending Execution Plan", show_header=True, header_style="bold green")
            table.add_column("Step", style="dim", width=4)
            table.add_column("Proposed CAD Command")
            
            for idx, step in enumerate(pending_steps):
                table.add_row(f"{idx + 1}", f"✓ {step}")
            console.print(Panel(table, style=DARK_PANEL_STYLE, border_style=DARK_BORDER_COLOR))
            console.print("[dim]Type FINAL SUBMIT to execute.[/dim]\n")
        else:
            console.print("[yellow]No pending plan. Input a natural language request first.[/yellow]\n")

    def handle_show_model(self, cad_summary: Dict[str, Any]) -> None:
        features = cad_summary.get("features", [])
        if not features:
            console.print("[yellow]No active document open or feature tree is empty.[/yellow]\n")
            return
            
        table = Table(title=f"Active Model Summary ({cad_summary.get('document_name')})", show_header=True, header_style="bold cyan")
        table.add_column("Feature Name", style="yellow")
        table.add_column("Type", style="green")
        table.add_column("Dimensions (mm)")
        
        for feat in features:
            dims_str = ", ".join([f"{k}: {v:.2f}" for k, v in feat.get("dimensions", {}).items()])
            table.add_row(feat["name"], feat["type"], dims_str if dims_str else "N/A")
            
        console.print(Panel(table, style=DARK_PANEL_STYLE, border_style=DARK_BORDER_COLOR))
        console.print()

    def handle_show_history(self) -> None:
        history = self.planner.context_mgr.get_history(self.planner.get_project_id())
        if not history:
            console.print("[yellow]Conversation history is empty.[/yellow]\n")
            return
            
        history_text = Text()
        for msg in history:
            role = "User" if msg["role"] == "user" else "AI Copilot"
            color = "yellow" if msg["role"] == "user" else "green"
            history_text.append(f"[{role}]: ", style=color)
            history_text.append(f"{msg['content']}\n")
            
        console.print(Panel(
            history_text,
            title="Chat History",
            style=DARK_PANEL_STYLE,
            border_style=DARK_BORDER_COLOR
        ))
        console.print()

    def handle_save(self) -> None:
        if not self.connected_to_sw:
            console.print("[red]Cannot save. SolidWorks is not connected.[/red]\n")
            return
        try:
            model = self.sw_conn.get_active_document()
            self.sw_conn.save_document(model.GetPathName())
            console.print("[green]✓ Model saved successfully.[/green]\n")
        except Exception as e:
            console.print(f"[red]Failed to save document: {e}[/red]\n")

    def handle_load(self, filepath: str) -> None:
        if not self.connected_to_sw:
            if not self.check_and_connect_sw():
                return
        try:
            self.sw_conn.open_document(filepath)
            self.planner.context_mgr.update_project_file_path(self.planner.get_project_id(), filepath)
            console.print(f"[green]✓ Opened document: {filepath}[/green]\n")
        except Exception as e:
            console.print(f"[red]Failed to load file '{filepath}': {e}[/red]\n")

    def handle_clear_history(self) -> None:
        self.planner.context_mgr.clear_history(self.planner.get_project_id())
        console.print("[green]✓ Conversation history cleared.[/green]\n")

    def handle_planning(self, instruction: str, cad_summary: Dict[str, Any]) -> None:
        self.state = StateMachine.PLANNING
        
        with console.status("[bold blue]Analyzing prompt and generating CAD operations..."):
            explanation, plan_steps, missing_params = self.planner.process_instruction(
                instruction,
                cad_summary
            )

        console.print(Panel(
            f"[bold green]AI Assistant:[/bold green] {explanation}",
            title="Response",
            style=DARK_PANEL_STYLE,
            border_style=DARK_BORDER_COLOR
        ))

        if missing_params:
            console.print(f"[orange3]Please clarify:[/orange3] {', '.join(missing_params)}")
            console.print("[dim]Specify these values to finalize the plan.[/dim]\n")
            return

        pending_cmds, pending_steps = self.planner.get_pending_plan()
        if pending_cmds:
            table = Table(title="Proposed Execution Plan", show_header=True, header_style="bold green")
            table.add_column("Step", style="dim", width=4)
            table.add_column("CAD Command")
            
            for idx, step in enumerate(pending_steps):
                table.add_row(f"{idx + 1}", f"✓ {step}")
                
            console.print(Panel(table, style=DARK_PANEL_STYLE, border_style=DARK_BORDER_COLOR))
            console.print("\nType [bold green]FINAL SUBMIT[/bold green] or [bold green]EXECUTE[/bold green] to apply changes in SolidWorks.\n")
        else:
            console.print("[yellow]Plan is empty. Try a direct shape description (e.g. 'Create a plate 100x100x5 mm').[/yellow]\n")

    def handle_execution(self) -> None:
        pending_cmds, pending_steps = self.planner.get_pending_plan()
        if not pending_cmds:
            console.print("[yellow]No plan is currently staged for execution. Describe your target shape first.[/yellow]\n")
            return

        if not self.connected_to_sw:
            if not self.check_and_connect_sw():
                console.print("[red]Aborted. Connect to SolidWorks before executing CAD commands.[/red]\n")
                return

        self.state = StateMachine.EXECUTION
        console.print("[bold green]Executing operations live in SolidWorks...[/bold green]")
        
        try:
            validated_cmds = parse_commands_list(pending_cmds)
            validate_commands(validated_cmds)
            
            project_id = self.planner.get_project_id()
            executed_features = self.executor.execute_plan(
                project_id=project_id,
                commands=validated_cmds,
                checkpoint_name=f"Execution plan: {', '.join(pending_steps[:2])}"
            )
            
            self.state = StateMachine.COMPLETED
            console.print(f"\n[bold green]✓ Execution Successful![/bold green] Created/modified features: {', '.join(executed_features)}")
            
            # Reset plan
            self.planner.clear_pending_plan()
            self.state = StateMachine.PLANNING
            
        except ValueError as val_err:
            console.print(f"\n[bold red]Validation Error:[/bold red] {val_err}\n")
            self.state = StateMachine.PLANNING
        except Exception as e:
            console.print(f"\n[bold red]Execution Error:[/bold red] {e}\n")
            self.state = StateMachine.PLANNING

    def handle_undo(self) -> None:
        if not self.connected_to_sw:
            console.print("[red]Cannot undo. SolidWorks is not connected.[/red]\n")
            return
        project_id = self.planner.get_project_id()
        console.print("[bold yellow]Undoing last operation...[/bold yellow]")
        try:
            success = self.rollback_handler.undo_last_operation(project_id)
            if success:
                console.print("[bold green]✓ Undo successful! Restored SolidWorks model and database checkpoint.[/bold green]\n")
            else:
                console.print("[red]✗ No checkpoints available to undo.[/red]\n")
        except Exception as e:
            console.print(f"[bold red]Undo failed:[/bold red] {e}\n")

    def handle_rollback(self, checkpoint_id: int) -> None:
        if not self.connected_to_sw:
            console.print("[red]Cannot rollback. SolidWorks is not connected.[/red]\n")
            return
        project_id = self.planner.get_project_id()
        console.print(f"[bold yellow]Rolling back to checkpoint {checkpoint_id}...[/bold yellow]")
        try:
            success = self.rollback_handler.rollback_to_checkpoint(project_id, checkpoint_id)
            if success:
                console.print(f"[bold green]✓ Successfully restored checkpoint {checkpoint_id}.[/bold green]\n")
            else:
                console.print(f"[red]✗ Checkpoint {checkpoint_id} not found.[/red]\n")
        except Exception as e:
            console.print(f"[bold red]Rollback failed:[/bold red] {e}\n")
