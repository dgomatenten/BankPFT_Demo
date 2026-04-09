### 🛠️ Prompt 11: "The Release Bootstrapper (Docker & Gunicorn)"

> "The application is flawlessly built, comprehensively tested via pytest, and filled with robust mock data. It is time to prepare this for Production release.
>
> 1. Please generate a `Dockerfile` and a `docker-compose.yml` to containerize the entire application. It must launch our Flask app on port 5000 and connect it to a native PostgreSQL 16 container instance.
>
> 2. Ensure that our production deployment does NOT run via the generic `flask run` dev-server. You must configure the production environment to run through **Gunicorn** natively binding the Application Factory using `app:create_app()`.
>
> 3. Update our existing `start.sh` bootstrapper script to include a `./start.sh prod` tag that will natively trigger the Gunicorn daemon!"

***

### Why this is the ultimate 11th Step:
You are crossing the finish line! After writing this prompt, the AI will package your meticulously crafted framework into a hardened Docker environment.

If you had asked the AI for `docker-compose.yml` on Day 1 (when there was no code), it would have hallucinated generic dependencies and paths. But by waiting until Prompt 11, the AI has perfectly loaded every path, model, and script into its memory buffer. It knows exactly what `requirements.txt` to lock, it knows exactly what PostgreSQL port to expose for your DDL scripts, and it knows exactly where the Application Factory lives!
