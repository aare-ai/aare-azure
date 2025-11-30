# aare.ai - Azure Functions Deployment

Azure Functions implementation of the aare.ai Z3 SMT verification engine.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Azure Functions                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    /verify endpoint                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐     │   │
│  │  │   LLM    │→ │ Ontology │→ │   Z3 SMT Verifier  │     │   │
│  │  │  Parser  │  │  Loader  │  │  (Constraint Logic)│     │   │
│  │  └──────────┘  └──────────┘  └────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│                     Azure Blob Storage                          │
│                      (ontologies/*.json)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Azure Functions Core Tools v4](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- Python 3.11+
- An Azure subscription

## Project Structure

```
aare-azure/
├── function_app.py          # Main Azure Functions entry point
├── handlers/
│   ├── __init__.py
│   ├── llm_parser.py        # LLM output text parser
│   ├── ontology_loader.py   # Loads rules from Blob Storage
│   └── smt_verifier.py      # Z3 theorem prover engine
├── infra/
│   ├── main.bicep           # Infrastructure as Code
│   └── main.bicepparam      # Bicep parameters
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD pipeline
├── host.json                # Azure Functions configuration
├── local.settings.json      # Local development settings
├── requirements.txt         # Python dependencies
└── README.md
```

## Local Development

### 1. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure local settings

Edit `local.settings.json` to set your Azure Storage connection string (or use Azurite for local emulation):

```json
{
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "AZURE_STORAGE_CONNECTION_STRING": "your-connection-string"
  }
}
```

### 3. Run locally

```bash
func start
```

The API will be available at `http://localhost:7071/verify`

### 4. Test the endpoint

```bash
curl -X POST http://localhost:7071/verify \
  -H "Content-Type: application/json" \
  -d '{
    "llm_output": "Based on your DTI of 35% and FICO score of 720, you are approved for a $350,000 mortgage.",
    "ontology": "mortgage-compliance-v1"
  }'
```

## Deployment

### Option 1: GitHub Actions (Recommended)

1. Create an Azure Service Principal:

```bash
az ad sp create-for-rbac --name "aareai-github-actions" \
  --role contributor \
  --scopes /subscriptions/{subscription-id} \
  --sdk-auth
```

2. Add the output as a GitHub secret named `AZURE_CREDENTIALS`

3. Push to `main` branch or manually trigger the workflow

### Option 2: Manual Deployment

1. **Deploy infrastructure**:

```bash
# Login to Azure
az login

# Create resource group
az group create --name aareai-prod-rg --location westus2

# Deploy Bicep template
az deployment group create \
  --resource-group aareai-prod-rg \
  --template-file infra/main.bicep \
  --parameters environment=prod
```

2. **Deploy function code**:

```bash
# Get the function app name from deployment output
FUNC_APP_NAME=$(az deployment group show \
  --resource-group aareai-prod-rg \
  --name main \
  --query properties.outputs.functionAppName.value -o tsv)

# Deploy
func azure functionapp publish $FUNC_APP_NAME
```

### Option 3: VS Code

1. Install the Azure Functions extension
2. Sign in to Azure
3. Right-click on the project → Deploy to Function App

## API Reference

### POST /verify

Verifies LLM output against compliance constraints.

**Request:**
```json
{
  "llm_output": "Your LLM-generated text here",
  "ontology": "mortgage-compliance-v1"
}
```

**Response:**
```json
{
  "verified": true,
  "violations": [],
  "parsed_data": {
    "dti": 35,
    "credit_score": 720,
    "loan_amount": 350000
  },
  "ontology": {
    "name": "mortgage-compliance-v1",
    "version": "1.0.0",
    "constraints_checked": 5
  },
  "proof": {
    "method": "Z3 SMT Solver",
    "version": "4.12.1"
  },
  "verification_id": "uuid",
  "execution_time_ms": 45,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Available Ontologies

- `mortgage-compliance-v1` - U.S. mortgage lending compliance
- `fair-lending-v1` - Fair lending regulations
- `hipaa-v1` - HIPAA PHI protection

## Security

- Function-level authentication enabled by default
- CORS restricted to aare.ai domains
- HTTPS-only communication
- No public blob access

### Obtaining an API Key

```bash
# Get the function app's host key
az functionapp keys list \
  --name aareai-func-prod \
  --resource-group aareai-prod-rg
```

Use the `default` host key in your requests:
```bash
curl -X POST https://aareai-func-prod.azurewebsites.net/verify \
  -H "Content-Type: application/json" \
  -H "x-functions-key: YOUR_API_KEY" \
  -d '{"llm_output": "...", "ontology": "mortgage-compliance-v1"}'
```

## Monitoring

- Application Insights is automatically configured
- View logs in Azure Portal → Function App → Monitor
- Query logs with Log Analytics

## Cost Estimation

Using the Consumption plan (Y1):
- First 1 million executions/month: Free
- Additional executions: ~$0.20 per million
- Storage: ~$0.02/GB/month

Typical production usage (10,000 verifications/day): **~$5-10/month**
