"""
aare.ai - Azure Functions main entry point
Verification endpoint using Z3 theorem prover
"""
import azure.functions as func
import json
import uuid
import logging
from datetime import datetime

from aare_core import OntologyLoader, LLMParser, SMTVerifier

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Initialize components
ontology_loader = OntologyLoader()
llm_parser = LLMParser()
smt_verifier = SMTVerifier()

# CORS allowed origins
ALLOWED_ORIGINS = [
    "https://aare.ai",
    "https://www.aare.ai",
    "http://localhost:8000",
    "http://localhost:3000"
]


def get_cors_headers(request: func.HttpRequest) -> dict:
    """Generate CORS headers based on request origin"""
    origin = request.headers.get("Origin", "")

    # Check if origin is allowed
    if origin in ALLOWED_ORIGINS:
        allowed_origin = origin
    else:
        allowed_origin = ALLOWED_ORIGINS[0]  # Default to primary domain

    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Headers": "Content-Type,x-api-key,x-functions-key",
        "Access-Control-Allow-Methods": "OPTIONS,POST"
    }


@app.route(route="verify", methods=["POST", "OPTIONS"])
def verify(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for aare.ai verification

    Request body:
    {
        "llm_output": "text to verify",
        "ontology": "ontology-name-v1"
    }
    """
    logging.info("aare.ai verification request received")

    cors_headers = get_cors_headers(req)

    # Handle CORS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(
            "",
            status_code=200,
            headers=cors_headers
        )

    try:
        # Parse request body
        req_body = req.get_json()
        llm_output = req_body.get("llm_output", "")
        ontology_name = req_body.get("ontology", "mortgage-compliance-v1")

        if not llm_output:
            return func.HttpResponse(
                json.dumps({"error": "llm_output is required"}),
                status_code=400,
                headers=cors_headers
            )

        # Load ontology
        ontology = ontology_loader.load(ontology_name)

        # Parse LLM output into structured data
        extracted_data = llm_parser.parse(llm_output, ontology)

        # Verify constraints using Z3
        verification_result = smt_verifier.verify(extracted_data, ontology)

        # Build response
        response_body = {
            "verified": verification_result["verified"],
            "violations": verification_result["violations"],
            "parsed_data": extracted_data,
            "ontology": {
                "name": ontology["name"],
                "version": ontology["version"],
                "constraints_checked": len(ontology["constraints"])
            },
            "proof": verification_result["proof"],
            "solver": "Constraint Logic",
            "verification_id": str(uuid.uuid4()),
            "execution_time_ms": verification_result["execution_time_ms"],
            "timestamp": datetime.utcnow().isoformat()
        }

        return func.HttpResponse(
            json.dumps(response_body),
            status_code=200,
            headers=cors_headers
        )

    except ValueError as e:
        logging.error(f"Invalid request: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON in request body"}),
            status_code=400,
            headers=cors_headers
        )
    except Exception as e:
        logging.error(f"Verification error: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "error": str(e),
                "type": type(e).__name__
            }),
            status_code=500,
            headers=cors_headers
        )
