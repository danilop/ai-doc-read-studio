from fastapi import FastAPI, UploadFile, File, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler
)
from fastapi.exceptions import RequestValidationError
import traceback
from pydantic import BaseModel, validator, Field
from typing import List, Dict, AsyncGenerator
import os
import uuid
import json
import logging
import logging.handlers
from datetime import datetime
import asyncio
from collections import defaultdict
from slowapi import Limiter, _rate_limit_exceeded_handler
from typing import Set
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog
from .token_tracker import token_tracker

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
        return {"backend": {"log_level": "info", "log_file": "logs/backend.log"}}

config = load_config()

# Setup structured logging
def setup_logging():
    log_level = config.get("backend", {}).get("log_level", "info").upper()
    log_file = os.path.join("..", config.get("backend", {}).get("log_file", "backend.log"))

    # Ensure the log file directory exists
    if os.path.dirname(log_file):
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if log_level == "DEBUG" else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure root logger for backward compatibility
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure uvicorn loggers to use our config
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.setLevel(getattr(logging, log_level, logging.INFO))
    uvicorn_access_logger.setLevel(getattr(logging, log_level, logging.INFO))

    return structlog.get_logger(__name__)

logger = setup_logging()
logger.info("Starting AI Doc Read Studio Backend")

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

# Store application start time for version checking
APP_START_TIME = datetime.now().timestamp()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception occurred",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=traceback.format_exc()
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom validation error handler with structured logging."""
    logger.warning(
        "Request validation failed",
        path=request.url.path,
        method=request.method,
        errors=exc.errors()
    )
    return await request_validation_exception_handler(request, exc)

@app.exception_handler(HTTPException)
async def http_exception_handler_custom(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with structured logging."""
    if exc.status_code >= 500:
        logger.error(
            "HTTP server error",
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            detail=exc.detail
        )
    elif exc.status_code >= 400:
        logger.warning(
            "HTTP client error",
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            detail=exc.detail
        )
    return await http_exception_handler(request, exc)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to set cache control headers for all responses
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    # Add aggressive no-cache headers to all API responses
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    # Add a timestamp header for debugging
    response.headers["X-Response-Time"] = str(datetime.now().timestamp())
    return response

UPLOAD_DIR = "uploads"
SESSIONS_DIR = "sessions"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

class TeamMember(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=50)
    role: str = Field(..., min_length=1, max_length=200)
    model: str = Field(default="nova-pro", pattern="^(nova-micro|nova-lite|nova-pro|nova-premier)$")

class CreateSessionRequest(BaseModel):
    document_ids: List[str] = Field(..., min_items=1, max_items=10)  # All documents for the session
    team_members: List[TeamMember] = Field(..., min_items=1, max_items=10)

    @validator('team_members')
    def validate_unique_ids(cls, v):
        ids = [member.id for member in v]
        if len(ids) != len(set(ids)):
            raise ValueError('Team member IDs must be unique')
        return v

    @validator('document_ids')
    def validate_document_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Document IDs must be unique')
        return v

class AddPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)

class RegenerateRequest(BaseModel):
    pass  # No additional data needed

class RevertRequest(BaseModel):
    pass  # No additional data needed

class ActionableSummaryRequest(BaseModel):
    model: str = Field(default="nova-pro", pattern="^(nova-micro|nova-lite|nova-pro|nova-premier)$")  # Default to Nova Pro

class Session:
    def __init__(self, session_id: str, document_ids: List[str], team_members: List[TeamMember]):
        self.session_id = session_id
        self.document_ids = document_ids  # All documents in session
        self.team_members = team_members
        self.conversation = []
        self.created_at = datetime.now().isoformat()

sessions = {}
documents = {}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.session_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, session_id: str = None):
        await websocket.accept()
        self.active_connections["global"].add(websocket)
        if session_id:
            self.session_connections[session_id].add(websocket)
        logger.info("WebSocket connected", session_id=session_id, total_connections=len(self.active_connections["global"]))

    def disconnect(self, websocket: WebSocket, session_id: str = None):
        self.active_connections["global"].discard(websocket)
        if session_id:
            self.session_connections[session_id].discard(websocket)
        logger.info("WebSocket disconnected", session_id=session_id, total_connections=len(self.active_connections["global"]))

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning("Failed to send WebSocket message", error=str(e))

    async def broadcast_to_session(self, message: dict, session_id: str):
        if session_id in self.session_connections:
            for connection in self.session_connections[session_id].copy():
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning("Failed to broadcast to session", session_id=session_id, error=str(e))
                    self.session_connections[session_id].discard(connection)

    async def broadcast_global(self, message: dict):
        for connection in self.active_connections["global"].copy():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning("Failed to broadcast globally", error=str(e))
                self.active_connections["global"].discard(connection)

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "AI Doc Read Studio API"}

@app.get("/version")
async def get_version():
    """Get API version and timestamp for cache-busting.

    The cache_buster is based on the application start time, so it only changes
    when the server is restarted (indicating a new deployment).
    """
    return {
        "version": config.get("app", {}).get("version", "1.0.0"),
        "timestamp": datetime.now().isoformat(),
        "cache_buster": f"v{APP_START_TIME}"
    }

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

@app.post("/upload")
@limiter.limit("10/minute")
async def upload_document(request: Request, file: UploadFile = File(...)):
    try:
        logger.info("Starting document upload", filename=file.filename, content_type=file.content_type)

        # Read file content to check size
        contents = await file.read()
        file_size = len(contents)

        if file_size > MAX_FILE_SIZE:
            logger.warning("File too large", filename=file.filename, file_size=file_size, max_size=MAX_FILE_SIZE)
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        if file_size == 0:
            logger.warning("Empty file uploaded", filename=file.filename)
            raise HTTPException(status_code=400, detail="File is empty")

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.txt', '.md', '.docx', '.pdf']:
            logger.warning("Unsupported file type attempted", filename=file.filename, extension=file_extension)
            raise HTTPException(status_code=400, detail="Unsupported file type")

        document_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}{file_extension}")

        with open(file_path, "wb") as f:
            f.write(contents)  # Use the already read contents

        documents[document_id] = {
            "id": document_id,
            "filename": file.filename,
            "path": file_path,
            "extension": file_extension,
            "uploaded_at": datetime.now().isoformat()
        }

        logger.info("Document uploaded successfully", filename=file.filename, document_id=document_id, file_size=file_size)
        return {"document_id": document_id, "filename": file.filename}
    except HTTPException:
        # Re-raise HTTPExceptions so they maintain their status codes
        raise
    except Exception as e:
        logger.error("Error uploading document", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions")
@limiter.limit("5/minute")
async def create_session(data: CreateSessionRequest, request: Request):
    try:
        logger.info("Creating session", document_ids=data.document_ids, team_size=len(data.team_members))

        # Validate all documents exist
        for doc_id in data.document_ids:
            if doc_id not in documents:
                logger.error("Document not found", document_id=doc_id)
                raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        session_id = str(uuid.uuid4())
        session = Session(session_id, data.document_ids, data.team_members)
        sessions[session_id] = session

        logger.info("Session created successfully", session_id=session_id, team_size=len(data.team_members))
        # Get all document filenames
        document_filenames = [documents[doc_id]["filename"] for doc_id in data.document_ids]

        return {
            "session_id": session_id,
            "document_filenames": document_filenames,
            "conversation": session.conversation
        }
    except HTTPException:
        # Re-raise HTTPExceptions so they maintain their status codes
        raise
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/{session_id}/prompt")
@limiter.limit("20/minute")
async def add_prompt(session_id: str, data: AddPromptRequest, request: Request):
    try:
        logger.info(f"Received prompt request for session {session_id}: '{data.prompt[:50]}...'")
        
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]

        # Get all document objects for the session
        session_documents = [documents[doc_id] for doc_id in session.document_ids]

        # Use real Strands agents with correct Bedrock model IDs
        from .agents import run_discussion_round
        logger.info("Loaded real Strands agents")
        logger.info(f"Running discussion round with {len(session.team_members)} team members")
        responses = await run_discussion_round(
            session,
            session_documents,
            data.prompt
        )
        logger.info(f"Discussion round completed with {len(responses)} responses")

        session.conversation.append({
            "type": "user",
            "content": data.prompt,
            "timestamp": datetime.now().isoformat()
        })

        for response in responses:
            session.conversation.append(response)

        # Broadcast new responses via WebSocket
        for response in responses:
            await manager.broadcast_to_session({
                "type": "agent_response",
                "data": response
            }, session_id)

        return {"conversation": session.conversation}
    except HTTPException:
        # Re-raise HTTPExceptions so they maintain their status codes
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/stream")
async def stream_responses(session_id: str, prompt: str):
    """Stream agent responses as they are generated using SSE."""
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            if session_id not in sessions:
                yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                return

            session = sessions[session_id]
            session_documents = [documents[doc_id] for doc_id in session.document_ids]

            # Add user message
            user_msg = {
                "type": "user",
                "content": prompt,
                "timestamp": datetime.now().isoformat()
            }
            session.conversation.append(user_msg)
            yield f"data: {json.dumps({'event': 'user_message', 'data': user_msg})}\n\n"

            # Get agents and run them
            from .agents import create_agent, parse_multiple_documents
            documents_content = parse_multiple_documents(session_documents)

            # Build conversation history
            conversation_history = "<conversation_history>\n"
            for msg in session.conversation[:-1]:  # Exclude the just-added user message
                if msg["type"] == "user":
                    conversation_history += f"<user_message>{msg['content']}</user_message>\n"
                else:
                    role = msg.get('role', 'Team Member')
                    conversation_history += f"<agent_message agent='{msg['agent_name']}' role='{role}'>{msg['content']}</agent_message>\n"
            conversation_history += f"<current_user_prompt>{prompt}</current_user_prompt>\n"
            conversation_history += "</conversation_history>"

            # Process agents one by one for streaming
            for member in session.team_members:
                yield f"data: {json.dumps({'event': 'agent_thinking', 'agent': member.name})}\n\n"

                agent = await create_agent(member, documents_content, conversation_history)
                agent_prompt = f"""
Current discussion prompt: {prompt}

Please provide your perspective on this document and the current discussion from your role as {member.role}.
Focus on actionable feedback and insights specific to your expertise.
"""

                try:
                    from .agents import invoke_agent_with_retry, get_bedrock_model_id
                    bedrock_model_id = get_bedrock_model_id(member.model)
                    response_text, response_time = await invoke_agent_with_retry(
                        agent, agent_prompt, member.name, session_id, bedrock_model_id
                    )

                    agent_response = {
                        "type": "agent",
                        "agent_id": member.id,
                        "agent_name": member.name,
                        "role": member.role,
                        "model": member.model,
                        "content": response_text,
                        "timestamp": datetime.now().isoformat(),
                        "response_time_seconds": round(response_time, 2),
                        "response_length": len(response_text)
                    }

                    session.conversation.append(agent_response)
                    yield f"data: {json.dumps({'event': 'agent_response', 'data': agent_response})}\n\n"

                except Exception as e:
                    error_response = {
                        "type": "agent",
                        "agent_id": member.id,
                        "agent_name": member.name,
                        "role": member.role,
                        "model": member.model,
                        "content": f"I apologize, but I'm having trouble responding right now. Error: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }
                    session.conversation.append(error_response)
                    yield f"data: {json.dumps({'event': 'agent_error', 'data': error_response})}\n\n"

                await asyncio.sleep(0.5)  # Small delay between agents

            yield f"data: {json.dumps({'event': 'complete'})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/sessions/{session_id}/regenerate")
async def regenerate_last_responses(session_id: str, request: RegenerateRequest):
    """Regenerate the last agent responses for the most recent user prompt."""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]
        logger.info(f"Regenerating last responses for session {session_id}")

        # Find the last user message and remove all agent responses after it
        last_user_index = -1
        for i in range(len(session.conversation) - 1, -1, -1):
            if session.conversation[i]["type"] == "user":
                last_user_index = i
                break

        if last_user_index == -1:
            raise HTTPException(status_code=400, detail="No user messages found to regenerate responses for")

        # Get the last user prompt
        last_user_message = session.conversation[last_user_index]
        last_prompt = last_user_message["content"]

        # Remove all messages after the last user message (agent responses)
        session.conversation = session.conversation[:last_user_index + 1]

        # Get all document objects for the session
        session_documents = [documents[doc_id] for doc_id in session.document_ids]

        # Generate new responses
        from .agents import run_discussion_round
        logger.info(f"Regenerating responses for prompt: {last_prompt}")
        responses = await run_discussion_round(
            session,
            session_documents,
            last_prompt
        )

        # Add new responses to conversation
        for response in responses:
            session.conversation.append(response)

        logger.info(f"Regenerated {len(responses)} new responses")
        return {"conversation": session.conversation}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating responses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/{session_id}/revert")
async def revert_to_previous_message(session_id: str, request: RevertRequest):
    """Revert conversation back to the previous user message by removing the last user message and all subsequent responses."""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]
        logger.info(f"Reverting last message for session {session_id}")

        if len(session.conversation) <= 1:
            raise HTTPException(status_code=400, detail="Cannot revert - conversation is too short")

        # Find the last user message and remove it and all messages after it
        last_user_index = -1
        for i in range(len(session.conversation) - 1, -1, -1):
            if session.conversation[i]["type"] == "user":
                last_user_index = i
                break

        if last_user_index == -1:
            raise HTTPException(status_code=400, detail="Cannot revert - no user messages found")

        # Remove the last user message and all responses after it
        session.conversation = session.conversation[:last_user_index]

        logger.info(f"Reverted conversation to {len(session.conversation)} messages")
        return {"conversation": session.conversation}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reverting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/{session_id}/actionable-summary")
async def generate_actionable_summary(session_id: str, request: ActionableSummaryRequest):
    """Generate an actionable summary of all suggestions from the conversation."""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]
        logger.info(f"Generating actionable summary for session {session_id}")

        # Get all document objects for the session
        session_documents = [documents[doc_id] for doc_id in session.document_ids]

        # Generate actionable summary using a specialized agent
        from .agents import generate_actionable_summary
        logger.info(f"Creating actionable summary agent with model: {request.model}")
        summary_markdown = await generate_actionable_summary(
            session,
            session_documents,
            request.model
        )

        logger.info("Successfully generated actionable summary")
        return {
            "summary": summary_markdown,
            "filename": f"actionable_summary_{session_id[:8]}.md"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating actionable summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    # Get all document filenames
    document_filenames = []
    for doc_id in session.document_ids:
        doc = documents.get(doc_id, {})
        document_filenames.append(doc.get("filename", "Unknown"))

    return {
        "session_id": session.session_id,
        "document_ids": session.document_ids,
        "document_filenames": document_filenames,
        "team_members": [member.dict() for member in session.team_members],
        "conversation": session.conversation,
        "created_at": session.created_at
    }

class LogRequest(BaseModel):
    source: str
    logs: str

@app.post("/logs")
async def write_logs(request: LogRequest):
    try:
        log_file = f"logs/{request.source}.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        with open(log_file, "a") as f:
            f.write(request.logs)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error writing {request.source} logs: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/sessions/{session_id}/tokens")
async def get_session_tokens(session_id: str):
    """Get token summary for a specific session."""
    try:
        token_summary = token_tracker.get_session_token_summary(session_id)
        return token_summary
    except Exception as e:
        logger.error("Error retrieving session tokens", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tokens/summary")
async def get_total_tokens():
    """Get total token summary across all sessions."""
    try:
        token_summary = token_tracker.get_total_token_summary()
        return token_summary
    except Exception as e:
        logger.error("Error retrieving total tokens", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent-templates")
async def get_agent_templates():
    """Get available agent templates for different review types."""
    try:
        templates_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent_templates.json")
        with open(templates_path, 'r') as f:
            templates = json.load(f)

        logger.info("Agent templates requested", categories=len(templates.get("categories", {})))
        return templates
    except FileNotFoundError:
        logger.error("Agent templates file not found")
        raise HTTPException(status_code=404, detail="Agent templates not found")
    except Exception as e:
        logger.error("Error loading agent templates", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

class CreateTeamFromTemplateRequest(BaseModel):
    template_ids: List[str] = Field(..., min_items=1, max_items=10)
    document_ids: List[str] = Field(..., min_items=1, max_items=10)
    initial_prompt: str = Field(..., min_length=1, max_length=2000)

@app.post("/sessions/from-template")
@limiter.limit("5/minute")
async def create_session_from_template(data: CreateTeamFromTemplateRequest, request: Request):
    """Create a session using predefined agent templates."""
    try:
        logger.info("Creating session from templates", template_ids=data.template_ids, document_count=len(data.document_ids))

        # Load agent templates
        templates_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent_templates.json")
        with open(templates_path, 'r') as f:
            templates_config = json.load(f)

        # Build template lookup
        template_lookup = {}
        for category in templates_config["categories"].values():
            for template in category["templates"]:
                template_lookup[template["id"]] = template

        # Validate all templates exist
        for template_id in data.template_ids:
            if template_id not in template_lookup:
                raise HTTPException(status_code=400, detail=f"Template not found: {template_id}")

        # Validate all documents exist
        for doc_id in data.document_ids:
            if doc_id not in documents:
                raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        # Create team members from templates
        team_members = []
        for i, template_id in enumerate(data.template_ids):
            template = template_lookup[template_id]
            team_member = TeamMember(
                id=f"template_{template_id}_{i}",
                name=template["name"],
                role=template["role"],
                model=template["model"]
            )
            team_members.append(team_member)

        # Create session
        session_id = str(uuid.uuid4())
        session = Session(session_id, data.document_ids, team_members)
        sessions[session_id] = session

        logger.info("Session created from templates", session_id=session_id, team_size=len(team_members))

        # Use specialized agent creation with custom prompts
        from .agents import run_discussion_round_with_templates
        session_documents = [documents[doc_id] for doc_id in data.document_ids]

        # Pass template system prompts to the agents
        template_prompts = {member.id: template_lookup[data.template_ids[i]]["system_prompt"]
                          for i, member in enumerate(team_members)}

        try:
            responses = await run_discussion_round_with_templates(
                session,
                session_documents,
                data.initial_prompt,
                template_prompts
            )
        except AttributeError:
            # Fallback to regular discussion if template function not available
            logger.warning("Template-specific function not available, using regular discussion")
            from .agents import run_discussion_round
            responses = await run_discussion_round(
                session,
                session_documents,
                data.initial_prompt
            )

        session.conversation.append({
            "type": "user",
            "content": data.initial_prompt,
            "timestamp": datetime.now().isoformat()
        })

        for response in responses:
            session.conversation.append(response)

        # Broadcast new agent responses via WebSocket
        for response in responses:
            await manager.broadcast_to_session({
                "type": "agent_response",
                "data": response
            }, session_id)

        logger.info(f"Session {session_id} created from templates with {len(session.conversation)} messages")

        # Get document filenames
        document_filenames = [documents[doc_id]["filename"] for doc_id in data.document_ids]

        return {
            "session_id": session_id,
            "document_filenames": document_filenames,
            "conversation": session.conversation,
            "templates_used": [template_lookup[tid]["name"] for tid in data.template_ids]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session from templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tokens/export")
async def export_tokens():
    """Export token data to JSON file."""
    try:
        filepath = token_tracker.export_tokens_to_json()
        return {
            "message": "Token data exported successfully",
            "filepath": filepath,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Error exporting tokens", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Global WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # Echo back for testing
            await manager.send_personal_message({"type": "echo", "message": data}, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/{session_id}")
async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
    """Session-specific WebSocket endpoint for real-time agent updates."""
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return

    await manager.connect(websocket, session_id)
    try:
        # Send session info immediately upon connection
        session = sessions[session_id]
        await manager.send_personal_message({
            "type": "session_info",
            "session_id": session_id,
            "team_size": len(session.team_members),
            "document_count": len(session.document_ids),
            "conversation_length": len(session.conversation)
        }, websocket)

        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Handle any client messages if needed
            message = json.loads(data) if data else {}
            if message.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error("WebSocket session error", session_id=session_id, error=str(e))
        manager.disconnect(websocket, session_id)

class ExportRequest(BaseModel):
    format: str = Field(..., pattern="^(markdown|pdf)$")
    include_metadata: bool = Field(default=True)

class ContentExportRequest(BaseModel):
    content: str = Field(..., description="Markdown content to export")
    format: str = Field(..., pattern="^(markdown|pdf)$")
    filename: str = Field(..., description="Base filename for the export")

@app.post("/sessions/{session_id}/export")
async def export_conversation(session_id: str, request: ExportRequest):
    """Export conversation to markdown or PDF format."""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]
        logger.info("Exporting conversation", session_id=session_id, format=request.format)

        if request.format == "markdown":
            content = generate_markdown_export(session, request.include_metadata)
            filename = f"conversation_{session_id[:8]}.md"
            media_type = "text/markdown"
        elif request.format == "pdf":
            # For PDF, we'll generate markdown first then convert
            markdown_content = generate_markdown_export(session, request.include_metadata)
            try:
                # Try to import reportlab for PDF generation
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                import io
                import re

                # Create PDF buffer
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []

                # Custom styles
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=16,
                    spaceAfter=30,
                )

                # Convert markdown to PDF-friendly format
                # This is a basic conversion - could be enhanced with proper markdown->PDF library
                lines = markdown_content.split('\n')
                for line in lines:
                    if line.startswith('# '):
                        story.append(Paragraph(line[2:], title_style))
                    elif line.startswith('## '):
                        story.append(Paragraph(line[3:], styles['Heading2']))
                    elif line.startswith('### '):
                        story.append(Paragraph(line[4:], styles['Heading3']))
                    elif line.strip():
                        # Clean up markdown formatting for PDF
                        clean_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                        clean_line = re.sub(r'\*(.*?)\*', r'<i>\1</i>', clean_line)
                        story.append(Paragraph(clean_line, styles['Normal']))
                    else:
                        story.append(Spacer(1, 12))

                doc.build(story)
                content = buffer.getvalue()
                buffer.close()

                filename = f"conversation_{session_id[:8]}.pdf"
                media_type = "application/pdf"

            except ImportError:
                # Fallback to markdown if reportlab not available
                logger.warning("reportlab not available, falling back to markdown export")
                content = generate_markdown_export(session, request.include_metadata)
                filename = f"conversation_{session_id[:8]}.md"
                media_type = "text/markdown"
            except Exception as pdf_error:
                logger.error("PDF generation failed", error=str(pdf_error))
                # Fallback to markdown
                content = generate_markdown_export(session, request.include_metadata)
                filename = f"conversation_{session_id[:8]}.md"
                media_type = "text/markdown"

        logger.info("Conversation exported successfully", filename=filename, size=len(content))

        # Return as file download
        from fastapi.responses import Response

        # Ensure content is bytes for consistent handling
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        return Response(
            content=content_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(content_bytes))
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting conversation", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export/content")
async def export_content(request: ContentExportRequest):
    """Export arbitrary content to markdown or PDF format."""
    try:
        logger.info("Exporting content", format=request.format, filename=request.filename)
        
        if request.format == "markdown":
            content_bytes = request.content.encode('utf-8')
            filename = request.filename if request.filename.endswith('.md') else f"{request.filename}.md"
            media_type = "text/markdown"
        elif request.format == "pdf":
            # For PDF, we'll convert markdown to PDF using the same approach as conversation export
            try:
                # Try to import reportlab for PDF generation
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from io import BytesIO
                import re
                
                # Create a BytesIO buffer for PDF
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1*inch)
                styles = getSampleStyleSheet()
                story = []
                
                # Custom styles
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    spaceAfter=12,
                    spaceBefore=12
                )
                
                heading_style = ParagraphStyle(
                    'CustomHeading',
                    parent=styles['Heading2'],
                    fontSize=14,
                    spaceAfter=8,
                    spaceBefore=10
                )
                
                # Parse markdown content and convert to PDF elements
                lines = request.content.split('\n')
                current_paragraph = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_paragraph:
                            story.append(Paragraph(' '.join(current_paragraph), styles['Normal']))
                            current_paragraph = []
                        story.append(Spacer(1, 6))
                        continue
                    
                    # Handle headers
                    if line.startswith('# '):
                        if current_paragraph:
                            story.append(Paragraph(' '.join(current_paragraph), styles['Normal']))
                            current_paragraph = []
                        story.append(Paragraph(line[2:], title_style))
                    elif line.startswith('## '):
                        if current_paragraph:
                            story.append(Paragraph(' '.join(current_paragraph), styles['Normal']))
                            current_paragraph = []
                        story.append(Paragraph(line[3:], heading_style))
                    elif line.startswith('### '):
                        if current_paragraph:
                            story.append(Paragraph(' '.join(current_paragraph), styles['Normal']))
                            current_paragraph = []
                        story.append(Paragraph(line[4:], styles['Heading3']))
                    elif line.startswith('- ') or line.startswith('* '):
                        if current_paragraph:
                            story.append(Paragraph(' '.join(current_paragraph), styles['Normal']))
                            current_paragraph = []
                        story.append(Paragraph(f"• {line[2:]}", styles['Normal']))
                    else:
                        current_paragraph.append(line)
                
                # Add any remaining paragraph
                if current_paragraph:
                    story.append(Paragraph(' '.join(current_paragraph), styles['Normal']))
                
                # Build PDF
                doc.build(story)
                content_bytes = buffer.getvalue()
                buffer.close()
                
                filename = request.filename.replace('.md', '.pdf') if request.filename.endswith('.md') else f"{request.filename}.pdf"
                media_type = "application/pdf"
                
            except ImportError:
                # Fallback to markdown if reportlab not available
                logger.warning("reportlab not available, falling back to markdown export")
                content_bytes = request.content.encode('utf-8')
                filename = request.filename if request.filename.endswith('.md') else f"{request.filename}.md"
                media_type = "text/markdown"
            except Exception as pdf_error:
                logger.error("PDF generation failed", error=str(pdf_error))
                # Fallback to markdown
                content_bytes = request.content.encode('utf-8')
                filename = request.filename if request.filename.endswith('.md') else f"{request.filename}.md"
                media_type = "text/markdown"
        
        logger.info("Content exported successfully", filename=filename, size=len(content_bytes))
        
        # Return as file download
        from fastapi.responses import Response
        return Response(
            content=content_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Content-Length": str(len(content_bytes))
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

def generate_markdown_export(session: Session, include_metadata: bool = True) -> str:
    """Generate markdown export of the conversation."""
    lines = []

    # Header
    lines.append("# AI Document Review Session")
    lines.append("")

    if include_metadata:
        # Session metadata
        lines.append("## Session Information")
        lines.append("")
        lines.append(f"**Session ID:** {session.session_id}")
        lines.append(f"**Created:** {session.created_at}")
        lines.append(f"**Documents:** {len(session.document_ids)}")
        lines.append(f"**Team Members:** {len(session.team_members)}")
        lines.append("")

        # Document information
        if session.document_ids:
            lines.append("### Documents")
            lines.append("")
            for i, doc_id in enumerate(session.document_ids, 1):
                doc = documents.get(doc_id, {})
                filename = doc.get("filename", "Unknown")
                lines.append(f"{i}. {filename}")
            lines.append("")

        # Team information
        lines.append("### Team Members")
        lines.append("")
        for i, member in enumerate(session.team_members, 1):
            lines.append(f"{i}. **{member.name}** - {member.role} (Model: {member.model})")
        lines.append("")

        lines.append("---")
        lines.append("")

    # Conversation
    lines.append("## Conversation")
    lines.append("")

    for msg in session.conversation:
        timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00")).strftime("%H:%M:%S")

        if msg["type"] == "user":
            lines.append(f"### 👤 User ({timestamp})")
            lines.append("")
            lines.append(msg["content"])
            lines.append("")
        elif msg["type"] == "agent":
            agent_name = msg.get("agent_name", "Agent")
            role = msg.get("role", "")
            model = msg.get("model", "")

            header = f"### 🤖 {agent_name}"
            if role:
                header += f" - {role}"
            if model:
                header += f" ({model})"
            header += f" ({timestamp})"

            lines.append(header)
            lines.append("")
            lines.append(msg["content"])
            lines.append("")

            # Add performance metadata if available
            if include_metadata and "response_time_seconds" in msg:
                lines.append(f"*Response time: {msg['response_time_seconds']}s*")
                lines.append("")

    if include_metadata:
        lines.append("---")
        lines.append("")
        lines.append(f"*Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
