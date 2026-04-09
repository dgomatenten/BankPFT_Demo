### 🛠️ Prompt 6: "The Business Services"

> "Fantastic. We now have a secure UI, mapping models, raw database scripts, and centralized JSON configuration. It is time to build our internal engines.
>
> 1. Please create our primary service files inside `app/services/` based on our Functional Specification.
> 
> 2. Create `app/services/upload_service.py` to handle CSV parsing. Crucially, this script must import our `config_loader` and validate incoming files *strictly* against the rules defined in `upload_config.json`. Do not hardcode validation rules here!
>
> 3. Create `app/services/sp_runner.py` to handle our native database interactions. Make sure this securely connects to PostgreSQL and natively captures runtime properties and pushes them to `BatchExecution` models.
>
> 4. Keep these files highly modular. They should not directly handle HTTP requests (we will hook them to Blueprints in the next step)."

***

### Why this is the perfect Sixth Step:
Now that the database and JSON files exist, you can finally build the "Brains" of the app! 

If you asked the AI to build `upload_service.py` back on Day 1, it would have hardcoded CSV formats directly into Python logic. But because we forced it to build the JSON Configs (Prompt 5) first, it natively knows that it must write a *dynamic* engine that just reads from those configs! This guarantees your code remains totally scalable and decoupled.
