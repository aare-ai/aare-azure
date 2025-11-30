"""
Ontology loader for aare.ai (Azure version)
Loads verification rules from Azure Blob Storage or returns default if storage fails
"""
import json
import os
import logging
from functools import lru_cache
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError


class OntologyLoader:
    def __init__(self, container_name=None, connection_string=None):
        self.container_name = container_name or os.environ.get(
            "ONTOLOGY_CONTAINER", "ontologies"
        )
        self.connection_string = connection_string or os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING", ""
        )
        self.blob_service_client = None

        if self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            except Exception as e:
                logging.warning(f"Failed to initialize blob client: {e}")

    @lru_cache(maxsize=10)
    def load(self, ontology_name):
        """Load ontology from Azure Blob Storage or return default"""
        try:
            if self.blob_service_client:
                container_client = self.blob_service_client.get_container_client(
                    self.container_name
                )
                blob_client = container_client.get_blob_client(f"{ontology_name}.json")
                download = blob_client.download_blob()
                ontology = json.loads(download.readall())
                return self._validate_ontology(ontology)
        except ResourceNotFoundError:
            logging.info(f"Ontology {ontology_name} not found in blob storage")
        except Exception as e:
            logging.warning(f"Failed to load from Blob Storage: {str(e)}")

        # Return default ontology
        logging.info(f"Using default ontology for {ontology_name}")
        return self._get_default_ontology()

    def _validate_ontology(self, ontology):
        """Validate ontology structure"""
        required_fields = ["name", "version", "constraints", "extractors"]
        for field in required_fields:
            if field not in ontology:
                raise ValueError(f"Invalid ontology: missing {field}")
        return ontology

    def _get_default_ontology(self):
        """Return default mortgage compliance ontology"""
        return {
            "name": "mortgage-compliance-v1",
            "version": "1.0.0",
            "description": "U.S. Mortgage Compliance - Core constraints",
            "constraints": [
                {
                    "id": "ATR_QM_DTI",
                    "category": "ATR/QM",
                    "description": "Debt-to-income ratio requirements",
                    "formula_readable": "(dti ≤ 43) ∨ (compensating_factors ≥ 2)",
                    "variables": [
                        {"name": "dti", "type": "real"},
                        {"name": "compensating_factors", "type": "int"},
                    ],
                    "error_message": "DTI exceeds 43% without sufficient compensating factors",
                    "citation": "12 CFR § 1026.43(c)",
                },
                {
                    "id": "HOEPA_HIGH_COST",
                    "category": "HOEPA",
                    "description": "High-cost mortgage counseling requirement",
                    "formula_readable": "(fee_percentage < 8) ∨ counseling_disclosed",
                    "variables": [
                        {"name": "fee_percentage", "type": "real"},
                        {"name": "counseling_disclosed", "type": "bool"},
                    ],
                    "error_message": "HOEPA triggered - counseling disclosure required",
                    "citation": "12 CFR § 1026.32",
                },
                {
                    "id": "UDAAP_NO_GUARANTEES",
                    "category": "UDAAP",
                    "description": "Prohibition on guarantee language",
                    "formula_readable": "¬(has_guarantee ∧ has_approval)",
                    "variables": [
                        {"name": "has_guarantee", "type": "bool"},
                        {"name": "has_approval", "type": "bool"},
                    ],
                    "error_message": "Cannot guarantee approval",
                    "citation": "12 CFR § 1036.3",
                },
                {
                    "id": "HPML_ESCROW",
                    "category": "Escrow",
                    "description": "Escrow requirements based on FICO",
                    "formula_readable": "(credit_score ≥ 620) ∨ ¬escrow_waived",
                    "variables": [
                        {"name": "credit_score", "type": "int"},
                        {"name": "escrow_waived", "type": "bool"},
                    ],
                    "error_message": "Cannot waive escrow with FICO < 620",
                    "citation": "12 CFR § 1026.35(b)",
                },
                {
                    "id": "REG_B_ADVERSE",
                    "category": "Regulation B",
                    "description": "Adverse action disclosure requirements",
                    "formula_readable": "is_denial → has_specific_reason",
                    "variables": [
                        {"name": "is_denial", "type": "bool"},
                        {"name": "has_specific_reason", "type": "bool"},
                    ],
                    "error_message": "Must disclose specific denial reason",
                    "citation": "12 CFR § 1002.9",
                },
            ],
            "extractors": {
                "dti": {"type": "float", "pattern": "dti[:\\s~]*(\\d+(?:\\.\\d+)?)"},
                "credit_score": {
                    "type": "int",
                    "pattern": "(?:fico|credit score)[:\\s]*(\\d{3})",
                },
                "fees": {
                    "type": "money",
                    "pattern": "\\$?([\\d,]+)k?\\s*(?:fees?|costs?)",
                },
                "loan_amount": {
                    "type": "money",
                    "pattern": "\\$?([\\d,]+)k?\\s*(?:loan|mortgage)",
                },
                "has_guarantee": {
                    "type": "boolean",
                    "keywords": ["guaranteed", "100%", "definitely"],
                },
                "has_approval": {"type": "boolean", "keywords": ["approved", "approve"]},
                "counseling_disclosed": {
                    "type": "boolean",
                    "keywords": ["counseling"],
                },
                "escrow_waived": {
                    "type": "boolean",
                    "keywords": ["escrow waived", "waive escrow", "skip escrow"],
                },
                "is_denial": {
                    "type": "boolean",
                    "keywords": ["denied", "cannot approve"],
                },
                "has_specific_reason": {
                    "type": "boolean",
                    "keywords": ["credit", "income", "dti", "debt", "score"],
                },
            },
        }

    def list_available(self):
        """List all available ontologies"""
        try:
            if self.blob_service_client:
                container_client = self.blob_service_client.get_container_client(
                    self.container_name
                )
                return [
                    blob.name.replace(".json", "")
                    for blob in container_client.list_blobs()
                    if blob.name.endswith(".json")
                ]
        except Exception as e:
            logging.warning(f"Failed to list ontologies: {e}")
        return ["mortgage-compliance-v1"]
