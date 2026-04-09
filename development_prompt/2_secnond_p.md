After the AI has generated the foundational folder structure and the [app/__init__.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/__init__.py:0:0-0:0) file from your First Prompt, your application exists but is "empty". 

Here is exactly what you should feed the AI next to build out the visual skeleton of the app!

***

### 🛠️ Prompt 2: "The Blueprint & Base UI"

> "Excellent. Now that the [app/__init__.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/__init__.py:0:0-0:0) factory and structural folders are created, let's build the visual and authentication skeleton.
>
> 1. Please create [app/templates/layout/base.html](cci:7://file:///home/dgoma/app_dev/BankPFT/app/templates/layout/base.html:0:0-0:0). Make this a **Bootstrap 5** HTML shell locally sourcing Bootstrap (no external CDNs). It should include a left-side navigation sidebar and a top navbar container. We will use this file to extend all future screens using `{% extends 'layout/base.html' %}`.
>
> 2. Create [app/models/auth.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/models/auth.py:0:0-0:0). Define a `User` model inheriting from `db.Model` using SQLAlchemy, and inject the `generate_password_hash` logic. Remember to configure it to work with Flask-Login.
>
> 3. Create a new Authentication Blueprint at [app/routes/auth.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/routes/auth.py:0:0-0:0) with `/login` and `/logout` endpoints, and attach it to our [app/__init__.py](cci:7://file:///home/dgoma/app_dev/BankPFT/app/__init__.py:0:0-0:0) factory."

***

### Why this is the perfect Second Step:
By following this exact order, you are establishing the two most critical bottlenecks in any web application immediately:
1. **The UI Shell (`base.html`)**: You lock the AI into using local Bootstrap 5, guaranteeing every future screen it generates will cleanly snap right into your sidebar layout!
2. **The Authentication Layer**: Because every future API or Route will require a mocked `@login_required` decorator, getting the `User` model out of the way on Day 1 prevents massive refactoring headaches on Day 3.