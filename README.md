# AI Doc Read Studio

When teams gather together to review important documents, magic happens. Different perspectives collide, expertise mingles, and insights emerge that no single person could have discovered alone.

This project uses [Strands Agents](https://strandsagents.com/latest/) and [Amazon Nova](https://nova.amazon.com) models to build **AI Doc Read Studio**, a web-based collaborative document review application using AI agents to simulate a discussion.

You can use it to prepare for a meeting or just get feedback on what you're working on.

<img width="1406" height="1307" alt="ai-doc-read-studio" src="https://github.com/user-attachments/assets/a61a7263-27a7-4d12-9785-834029dfc1cc" />

## Features

- **Document Upload**: Support for TXT, Markdown, Word (.docx), and PDF files
- **Team Management**: Configure AI agents with custom roles and Nova model selection
- **Multi-Agent Conversations**: Intelligent discussions using Strands Agents framework
- **Real-time Updates**: WebSocket-based live conversation updates
- **Export Options**: Download conversations and action plans as Markdown or PDF
- **Model Selection**: Choose from Amazon Nova Micro, Lite, Pro, or Premier models

## Quick Start

### Prerequisites
- Python 3.10+ 
- [UV package manager](https://docs.astral.sh/uv/) - fastest Python package installer
- AWS credentials configured for Bedrock access

### Quick Start

```bash
git clone https://github.com/danilop/ai-doc-read-studio
cd ai-doc-read-studio
# Simplified way to install dependencies and start both backend and frontend servers
./start.sh
```

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/danilop/ai-doc-read-studio
   cd ai-doc-read-studio
   ```

2. **Install dependencies with UV:**
   ```bash
   uv sync
   ```

### Running the Application

#### 🚀 Recommended: Unified Startup
```bash
# Start both backend and frontend servers
uv run python start_app.py
```

#### Alternative: Start Servers Separately

**Backend:**
```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
uv run python -m http.server 3000 --directory frontend
```

### Access the Application

- **Web Interface**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Backend API**: http://localhost:8000

## Usage

### Basic Workflow

1. **Upload Documents**: Drag and drop or select files (TXT, MD, DOCX, PDF)
2. **Configure Team**: Set up AI agents with different roles and models
3. **Start Discussion**: Let agents analyze and discuss the document
4. **Interactive Chat**: Ask follow-up questions and guide the conversation
5. **Export Results**: Download conversations and action plans

### Team Setup

The application supports multiple AI agents with different perspectives:
- **Product Manager**: Strategy and market analysis
- **Tech Lead**: Technical architecture and implementation
- **UX Designer**: User experience and design considerations
- **Security Expert**: Security and compliance review

### Model Options

Choose from Amazon Nova models based on your needs:
- **Nova Micro**: Fast, basic analysis
- **Nova Lite**: Balanced performance and cost
- **Nova Pro**: Advanced reasoning capabilities  
- **Nova Premier**: Highest quality analysis

## Development

### Project Structure

```
ai-doc-read-studio/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main application
│   ├── agents.py           # AI agents integration
│   └── document_parser.py  # Document processing
├── frontend/               # Web interface
│   ├── index.html          # Main UI
│   ├── app.js              # Frontend logic
│   └── config.js           # Configuration
├── tests/                  # Test suite
├── pyproject.toml          # UV dependencies
├── config.json             # Application config
└── sample_doc.md          # Sample document
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=backend --cov-report=html

# Run specific test files
uv run pytest tests/test_api.py -v
```

### Code Quality

```bash
# Format code
uv run black .

# Lint code  
uv run ruff check .

# Fix linting issues
uv run ruff check . --fix
```

### Development Dependencies

Install development tools:
```bash
uv sync --dev
```

## Configuration

### Application Settings

Edit `config.json` to customize:
```json
{
  "backend": {
    "host": "0.0.0.0",
    "port": 8000,
    "log_level": "info"
  },
  "frontend": {
    "host": "localhost",
    "port": 3000
  },
  "api": {
    "base_url": "http://localhost:8000"
  }
}
```

### AWS Configuration

For production use with real AI models:

1. **Configure AWS credentials:**
   ```bash
   aws configure
   # OR set environment variables
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret  
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **Ensure Bedrock access:** Your AWS account needs access to Amazon Bedrock and Nova models

## API Endpoints

- `POST /upload` - Upload documents
- `POST /sessions` - Create discussion session  
- `POST /sessions/{id}/prompt` - Add conversation prompt
- `GET /sessions/{id}` - Get session details
- `POST /sessions/{id}/export` - Export conversation
- `POST /export/content` - Export arbitrary content
- `WebSocket /ws` - Real-time updates

## Troubleshooting

1. **Installation issues**: Ensure UV is installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Port conflicts**: Check if ports 8000/3000 are available
3. **AWS credentials**: Demo mode works without AWS; production needs Bedrock access
4. **Module errors**: Always use `uv run` for Python commands
5. **Cache issues**: Clear browser cache or use Ctrl+F5

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks: `uv run pytest && uv run ruff check . && uv run black .`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: For bugs and feature requests
- Documentation: Check the `/docs` endpoint when running
- Sample Document: Use `sample_doc.md` for testing
