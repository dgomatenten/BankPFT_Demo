### 🛠️ Prompt 5: "The JSON Configuration Engine"

> "Great! Our database tables are complete. Now we need to define the Application logic rules that manipulate this data.
>
> 1. Remember my rule from the `docs/AI_DEVELOPMENT_GUIDE.md`: We must define our application structures and variables into JSON files, **not** into massive python arrays.
>
> 2. Please create the initial `app/config/` directory. Inside of it, I want you to create three master configuration systems based on our functional specifications:
>     - `upload_config.json` (to define what CSV files users are allowed to upload to our new tables)
>     - `validation_rules.json` (to define what mathematical constraints or validations happen on those files)
>     - `rule_config.json` (to define the overarching operational configurations for our new business platform)
>
> 3. Once those JSON rules are defined, please create a single Python file at `app/core/config_loader.py` that will statically load and cache these JSON files deeply into the application runtime!"

***

### Why this is the perfect Fifth Step:
If you let the AI skip this step, it will do what all AIs instinctively love to do: It will build massive list arrays inside of `app/routes/` holding terrible, messy variables to control logic flow. 

By forcing the AI to build `app/config/*.json` files immediately after the database has finished, you train the AI to treat the `.json` files as the ultimate source of truth for the Application's UI flows and data limits! Your frontend views and backend scripts will now forever pull their constraints from that neat configuration map rather than messy hard-coded Python scripts!
