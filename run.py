from app import create_app
import os

application = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    application.run(debug=debug, host="0.0.0.0", port=5000)

