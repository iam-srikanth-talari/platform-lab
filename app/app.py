from flask import Flask, jsonify, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

REQUEST_COUNT = Counter(
    "demo_app_requests_total",
    "Total number of requests received by the application",
    ["endpoint"],
)


@app.route("/")
def home():
    REQUEST_COUNT.labels(endpoint="/").inc()

    return jsonify(
        {
            "application": "demo-app",
            "message": "Platform Engineering Lab",
            "status": "running",
        }
    )


@app.route("/health")
def health():
    REQUEST_COUNT.labels(endpoint="/health").inc()

    return jsonify({"status": "healthy"}), 200


@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

# from flask import Flask, jsonify

# app = Flask(__name__)


# @app.route("/")
# def home():
#     return jsonify(
#         {
#             "application": "demo-app",
#             "message": "Platform Engineering Lab",
#             "status": "running",
#         }
#     )


# @app.route("/health")
# def health():
#     return jsonify({"status": "healthy"}), 200


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8000)