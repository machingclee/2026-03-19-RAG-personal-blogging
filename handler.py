from mangum import Mangum
from app import app


# Mangum adapter wraps the ASGI app for AWS Lambda
handler = Mangum(app)
