"""
API documentation routes (Swagger UI and OpenAPI spec serving).
"""

import os
from flask import Blueprint, Response, send_file

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/openapi.yaml", methods=["GET"])
def serve_openapi_yaml() -> Response:
    """Serve the OpenAPI YAML specification from the docs folder."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs"))
    path = os.path.join(base_dir, "openapi.yaml")
    return send_file(path, mimetype="application/yaml")


@docs_bp.route("/docs", methods=["GET"])
def swagger_ui() -> Response:
    """Serve a minimal Swagger UI that loads the YAML spec."""
    html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>LinkedIn Automation API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
    <script>
      window.onload = () => {
        window.ui = SwaggerUIBundle({
          url: './openapi.yaml',
          dom_id: '#swagger-ui',
          deepLinking: true,
          presets: [SwaggerUIBundle.presets.apis],
        });
      };
    </script>
  </body>
  </html>
    """
    return Response(html, mimetype="text/html")


