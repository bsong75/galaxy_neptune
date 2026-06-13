import logging
import threading
import time
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
from flask_cors import CORS
from flasgger import Swagger
from routes.graph import graph_bp
from routes.chat import chat_bp
from routes.upax import upax_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins='*')

app.config['SWAGGER'] = {
    'title': 'Neptune Galaxy API',
    'version': '1.0',
    'description': 'Graph-based passenger network explorer API',
    'uiversion': 3,
}
Swagger(app)

app.register_blueprint(graph_bp, url_prefix='/api')
app.register_blueprint(chat_bp, url_prefix='/api')
app.register_blueprint(upax_bp, url_prefix='/api')


def _cleanup_loop():
    """Background thread that cleans up old graph data every 24 hours."""
    from neptune_client import get_driver
    from graph_builder import cleanup_old_graphs

    # Wait 60s on startup before first cleanup attempt
    time.sleep(60)

    while True:
        try:
            driver = get_driver()
            deleted = cleanup_old_graphs(driver, max_age_hours=24)
            logger.info(f"Scheduled cleanup complete: {deleted} nodes removed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        # Sleep 24 hours
        time.sleep(24 * 60 * 60)


# Start cleanup thread (daemon so it dies with the main process)
_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
