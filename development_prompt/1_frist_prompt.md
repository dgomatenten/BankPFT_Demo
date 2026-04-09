If you are starting a completely new project on Day 1, you want to immediately establish the "rules of the game" before the AI writes a single line of code.

Once you have created your new folder and copied over the [README.md](cci:7://file:///home/dgoma/app_dev/BankPFT/README.md:0:0-0:0), [copilot-instructions.md](cci:7://file:///home/dgoma/app_dev/BankPFT/copilot-instructions.md:0:0-0:0), and [docs/AI_DEVELOPMENT_GUIDE.md](cci:7://file:///home/dgoma/app_dev/BankPFT/docs/AI_DEVELOPMENT_GUIDE.md:0:0-0:0) files from this project, here is the exact **Master Prompt** you should use as your very first message to initialize the AI:

***

### 🚀 The "Day 1" Master Prompt

> "We are starting a brand new application. I want this new project to utilize the exact same architectural foundations, UI libraries, and coding paradigms as my previous BankPFT project. 
>
> I have attached three documents to this chat:
> 1. [README.md](cci:7://file:///home/dgoma/app_dev/BankPFT/README.md:0:0-0:0) (to show you the file structure)
> 2. [copilot-instructions.md](cci:7://file:///home/dgoma/app_dev/BankPFT/copilot-instructions.md:0:0-0:0) (to establish your strict coding rules)
> 3. [docs/AI_DEVELOPMENT_GUIDE.md](cci:7://file:///home/dgoma/app_dev/BankPFT/docs/AI_DEVELOPMENT_GUIDE.md:0:0-0:0) (to establish how features are built)
>
> Please read these three files carefully. Acknowledge that you understand that you must use **Flask Application Factories**, **Blueprint Routing**, **Local Bootstrap 5**, and native **PostgreSQL JSONB** data structures instead of heavy relational ones.
>
> Once you acknowledge these rules, please generate the basic [app/__init__.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/__init__.py:0:0-0:0) factory. Additionally, please generate both a [start.sh](cci:7://file:///home/dgoma/app_dev/BankPFT/start.sh:0:0-0:0) and a `start.bat` startup script to initialize our new project mirroring the architecture shown in the README, ensuring we can natively map dependencies on both Linux and Windows environments!"

***

### Why this works:
Using this as your very first prompt guarantees that the AI completely absorbs your preferred architecture before it makes any assumptions. By asking it to build the [app/__init__.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/__init__.py:0:0-0:0) file first, you immediately test that it is successfully following the "Application Factory" and "Blueprint" constraints mentioned in your instruction files!

Created 1_frist_prompt.txt

When you send that exact prompt to the AI, it will immediately generate the **two foundational pillars** of your new application to prove it understands the BankPFT architecture:

### 1. [app/__init__.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/__init__.py:0:0-0:0) (The Application Factory)
Instead of building a simple, messy single-file Flask app, the AI will generate a scalable `create_app()` factory function. 

It will set up the core infrastructure inside this file, including:
- Initializing the `db = SQLAlchemy()` instance.
- Setting up the `LoginManager` for user authentication.
- Registering a dummy `Blueprint` (like `app.register_blueprint(dashboard_bp)`) to prove that it knows all future routes must be cleanly isolated into separate files.

### 2. [start.sh](cci:7://file:///home/dgoma/app_dev/BankPFT/start.sh:0:0-0:0) (The Bootstrapper)
It will generate the shell script that developers will use to launch the application locally. 

Just like BankPFT, it will write a bash script that:
- Automatically creates a secure Python virtual environment (`python3 -m venv venv`).
- Installs the required packages (`pip install -r requirements.txt`).
- Boots up the Flask development server on `localhost:5000` connected to PostgreSQL.

***

By forcing the AI to build these two exact files right out of the gate, you immediately set the structural tone for the entire project lifecycle! From that point forward, you can start asking it to build your specific database models and UI screens, and it will effortlessly snap them into that clean architectural pattern.
