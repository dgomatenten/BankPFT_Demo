### 🛠️ Prompt 8: "The Jinja2 Presentation Layer"

> "Awesome, our endpoints in the `app/routes/` routing layer are now catching user traffic and hitting the internal engines! The final major step is building the actual user interface screens.
>
> 1. Please generate the specific UI `.html` files needed inside the `app/templates/` folder (e.g. `app/templates/upload/index.html`, `app/templates/batch/monitor.html`).
>
> 2. Based on the rules laid out in `docs/AI_DEVELOPMENT_GUIDE.md`, you MUST use `{% extends 'layout/base.html' %}` on every file to snap it into our primary skeleton shell. 
>
> 3. Stick strictly to standard Bootstrap 5. Use native `table`, `table-responsive`, and `card` classes for data rendering. 
> 
> 4. Ensure you successfully utilize Jinja2 loops to parse the variables handed down from the Blueprint routes. Remember to natively include the Bootstrap Flash message loops so users see dynamic validation errors!"

***

### Why this is the perfect Eighth Step:
This is the grand finale! Because you forced the AI to build the side navigation hierarchy in the `README.md` and the master base template in `base.html` back in Prompt 2, generating the UI is incredibly easy for the AI here. 

It does not have to worry about styling headers, navbars, or complex CSS layouts. It just needs to drop native Bootstrap 5 cards and tables exactly where the data lives! This perfectly decouples your frontend logic from your backend infrastructure.
