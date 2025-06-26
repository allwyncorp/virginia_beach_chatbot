# Virginia Beach Chatbot

A comprehensive AI-powered chatbot for the City of Virginia Beach that provides information about city services, facilities, and local government procedures. The chatbot uses AWS services including Amazon Lex, Amazon Bedrock, and DynamoDB to deliver intelligent responses to citizen inquiries.

## 🏗️ Architecture

The application consists of three main components:

### 1. **Infrastructure (IaC)**
- **AWS CDK** for infrastructure as code
- **Amazon Lex** for natural language understanding
- **Amazon Bedrock** for AI text generation (Claude Instant v1)
- **DynamoDB** for chat history storage
- **S3** for data storage and UI hosting
- **CloudFront** for content delivery
- **API Gateway** for REST API endpoints
- **Lambda Functions** for backend processing

### 2. **Backend Services**
- **Chat Handler Lambda**: Main conversation orchestrator
- **Data Ingestion Lambda**: Web crawler for city website content
- **Chat API Lambda**: REST API endpoint for web interface

### 3. **Frontend**
- **React.js** web application
- **AWS Amplify** UI components
- **Responsive design** for mobile and desktop

## 🚀 Quick Start

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **Node.js** (v16 or later)
3. **Python** (3.11 or later)
4. **AWS CLI** configured with your credentials
5. **AWS CDK** installed globally

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd virginia_beach_chatbot
   ```

2. **Install AWS CDK globally**
   ```bash
   npm install -g aws-cdk
   ```

3. **Install infrastructure dependencies**
   ```bash
   cd iac
   pip install -r requirements.txt
   ```

4. **Install UI dependencies**
   ```bash
   cd ../ui
   npm install
   ```

## 📦 Deployment

### Step 1: Deploy Infrastructure

1. **Navigate to the IaC directory**
   ```bash
   cd iac
   ```

2. **Bootstrap CDK (first time only)**
   ```bash
   cdk bootstrap
   ```

3. **Deploy the stack**
   ```bash
   cdk deploy
   ```

   This will create all AWS resources including:
   - S3 buckets for data and UI hosting
   - DynamoDB table for chat history
   - Lambda functions
   - Amazon Lex bot
   - API Gateway
   - CloudFront distribution
   - IAM roles and policies

4. **Note the outputs** - CDK will display important information including:
   - CloudFront URL for the web interface
   - API Gateway endpoint
   - Bot IDs and ARNs

### Step 2: Build and Deploy UI

1. **Navigate to the UI directory**
   ```bash
   cd ../ui
   ```

2. **Update API endpoint** (if needed)
   Edit `src/App.js` and update the `API_URL` constant with your API Gateway endpoint from the CDK output.

3. **Build the React application**
   ```bash
   npm run build
   ```

4. **Deploy UI to S3** (this is handled automatically by CDK, but you can redeploy manually)
   ```bash
   cd ../iac
   cdk deploy
   ```

### API Usage

The chatbot can also be accessed via REST API:

```bash
curl -X POST https://your-api-gateway-url/prod/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the parking rates?",
    "sessionId": "user-session-123"
  }'
```

## 🔧 Configuration

### Environment Variables

The following environment variables are automatically set by CDK:

- `PROCESSED_DATA_BUCKET`: S3 bucket for crawled data
- `CHAT_HISTORY_TABLE`: DynamoDB table name
- `BEDROCK_MODEL_ID`: AI model identifier (default: anthropic.claude-instant-v1)
- `LEX_BOT_ID`: Amazon Lex bot identifier
- `LEX_BOT_ALIAS_ID`: Bot alias identifier

### Customization

#### Changing the AI Model

Edit `iac/iac_stack.py` and modify the `BEDROCK_MODEL_ID` environment variable:

```python
"BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",  # Example
```

#### Modifying the Web Crawler

Edit `lambda/data-ingestion/index.py` to change:
- `START_URL`: The website to crawl
- `MAX_PAGES_TO_CRAWL`: Number of pages to process

#### Updating the UI

1. Modify `ui/src/App.js` for UI changes
2. Update `ui/src/App.css` for styling
3. Run `npm run build` to rebuild
4. Redeploy with `cdk deploy`

## 🔍 Monitoring and Logs

### CloudWatch Logs

Monitor Lambda function execution:
- **Chat Handler**: `/aws/lambda/CovbChatHandlerLambda`
- **Data Ingestion**: `/aws/lambda/CovbDataIngestionLambda`
- **Chat API**: `/aws/lambda/CovbChatApiLambda`

### DynamoDB Metrics

Monitor chat history table performance in the DynamoDB console.

### CloudFront Analytics

View web interface usage statistics in the CloudFront console.

## 🛠️ Development

### Local Development

1. **UI Development**
   ```bash
   cd ui
   npm start
   ```
   Access at `http://localhost:3000`

2. **Lambda Testing**
   Use AWS SAM or test directly in the AWS console

3. **Infrastructure Changes**
   ```bash
   cd iac
   cdk diff  # Preview changes
   cdk deploy  # Apply changes
   ```
 
