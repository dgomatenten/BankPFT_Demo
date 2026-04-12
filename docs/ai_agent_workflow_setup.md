# AI Agent Workflow Setup — BankPFT (Windows/Flask/Postgres)

## 1. Environment Configuration
To replicate the Agentic Workflow described in the technical documentation, configure your VS Code environment as follows:

### Prerequisites
- **VS Code** with GitHub Copilot / Copilot Chat.
- **PostgreSQL 14+** (Local or Docker).
- **Python 3.10+** (Virtual environment recommended).

### Custom Agent Activation
1.  Ensure the agents are placed in `.github/agents/`.
2.  (Note: In environments where `.github/agents/` is not natively parsed, use these files as "System Instruction" templates for Copilot Chat custom instructions).

---

## 2. Replicating the Multi-Agent System

| Agent | VS Code Tooling | Core Responsibility |
| :--- | :--- | :--- |
| **@architect** | Custom Instruction / Model Switching | Pattern enforcement & Database Schema integrity. |
| **@researcher** | `@workspace` + MCP Servers | Navigating `docs/` and researching external APIs. |
| **@reviewer** | Agentic Workflows / Actions | 4-Stage Pipeline (Quality -> Arch -> Security -> Docs). |

---

## 3. Agentic Workflow: The 4-Stage Pipeline
When submitting changes or preparing a Pull Request, trigger the following instruction sequence:

1.  **Trigger Quality Review**: "@reviewer please simplify this diff for Flask best practices."
2.  **Trigger Architecture Check**: "@architect does this change break the batch orchestration logic?"
3.  **Trigger Security Scan**: "@reviewer check these new routes for SQL injection or missing auth."
4.  **Update Specification**: "@researcher update the `api_specification.md` to reflect these changes."

---

## 4. Model Context Management (Hyper-Context)
- **Local MCP**: Install the Postgres-MCP server to give agents direct (read-only) visibility into your local `proc_` and `stg_` tables.
- **Workspace Indexing**: Ensure VS Code has indexed the `docs/` and `app/` folders for high-precision `@workspace` searches.

---

## 5. Prompt Examples: How to Orchestrate Your Agents

To trigger the specialized logic defined in your agents, use these prompts in VS Code's Copilot Chat:

### For Architectural Design
> "@architect review my current diff in `app/models/` and ensure it doesn't break our PostgreSQL naming conventions or the audit traceability pattern."

### For Codebase Research
> "@researcher search the @workspace for all files related to the '3-Panel Trace' view and explain how the frontend links to the backend SP results."

### For the 4-Stage Quality Review
> "@reviewer run the 4-stage pipeline on this file. Focus on Stage 1 (Logic) and Stage 3 (SQL Injection and Flask Auth)."

### For Comprehensive Implementation
> "@antigravity take the design from @architect and the research from @researcher to implement the new 'Batch Execution' monitoring endpoint as a background task."

### For Documentation
> "@researcher check if my latest changes to the FTP engine require an update to the `ftp_specification.md`."

