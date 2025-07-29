"""
Token tracking module for API usage and model invocations.
"""
import json
from datetime import datetime
from typing import Dict, List
from collections import defaultdict
import structlog

logger = structlog.get_logger(__name__)

class TokenTracker:
    """Track token usage for API invocations and model usage."""

    def __init__(self):
        self.session_tokens: Dict[str, List[Dict]] = defaultdict(list)
        self.total_tokens: Dict[str, Dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text (rough approximation)."""
        # Very rough estimation: ~4 characters per token on average
        return max(1, len(text) // 4)

    def track_agent_invocation(
        self,
        session_id: str,
        agent_name: str,
        model: str,
        input_text: str,
        output_text: str,
        response_time: float
    ) -> Dict:
        """Track tokens for a single agent invocation."""

        # Estimate token counts
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = self.estimate_tokens(output_text)

        # Create token record
        token_record = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "agent_name": agent_name,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "response_time_seconds": response_time
        }

        # Store the record
        self.session_tokens[session_id].append(token_record)
        self.total_tokens[model]["input"] += input_tokens
        self.total_tokens[model]["output"] += output_tokens

        logger.info(
            "Agent invocation tokens tracked",
            session_id=session_id,
            agent_name=agent_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            response_time_seconds=response_time
        )

        return token_record

    def get_session_token_summary(self, session_id: str) -> Dict:
        """Get token summary for a specific session."""
        session_records = self.session_tokens.get(session_id, [])

        if not session_records:
            return {
                "session_id": session_id,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_invocations": 0,
                "model_breakdown": {},
                "agent_breakdown": {}
            }

        total_input_tokens = sum(record["input_tokens"] for record in session_records)
        total_output_tokens = sum(record["output_tokens"] for record in session_records)
        total_tokens = total_input_tokens + total_output_tokens
        total_invocations = len(session_records)

        # Model breakdown
        model_breakdown = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "invocations": 0})
        agent_breakdown = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "invocations": 0})

        for record in session_records:
            model = record["model"]
            agent = record["agent_name"]
            input_tokens = record["input_tokens"]
            output_tokens = record["output_tokens"]

            model_breakdown[model]["input_tokens"] += input_tokens
            model_breakdown[model]["output_tokens"] += output_tokens
            model_breakdown[model]["total_tokens"] += input_tokens + output_tokens
            model_breakdown[model]["invocations"] += 1

            agent_breakdown[agent]["input_tokens"] += input_tokens
            agent_breakdown[agent]["output_tokens"] += output_tokens
            agent_breakdown[agent]["total_tokens"] += input_tokens + output_tokens
            agent_breakdown[agent]["invocations"] += 1

        return {
            "session_id": session_id,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "total_invocations": total_invocations,
            "model_breakdown": dict(model_breakdown),
            "agent_breakdown": dict(agent_breakdown),
            "records": session_records
        }

    def get_total_token_summary(self) -> Dict:
        """Get total token summary across all sessions."""
        total_input_tokens = sum(tokens["input"] for tokens in self.total_tokens.values())
        total_output_tokens = sum(tokens["output"] for tokens in self.total_tokens.values())
        total_tokens = total_input_tokens + total_output_tokens
        total_sessions = len(self.session_tokens)
        total_invocations = sum(len(records) for records in self.session_tokens.values())

        return {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "total_sessions": total_sessions,
            "total_invocations": total_invocations,
            "tokens_by_model": {
                model: {
                    "input_tokens": tokens["input"],
                    "output_tokens": tokens["output"],
                    "total_tokens": tokens["input"] + tokens["output"]
                } for model, tokens in self.total_tokens.items()
            },
            "average_tokens_per_session": total_tokens // total_sessions if total_sessions > 0 else 0,
            "average_tokens_per_invocation": total_tokens // total_invocations if total_invocations > 0 else 0
        }

    def export_tokens_to_json(self, filepath: str = None) -> str:
        """Export all token data to JSON file."""
        if filepath is None:
            filepath = f"token_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "summary": self.get_total_token_summary(),
            "session_details": {
                session_id: self.get_session_token_summary(session_id)
                for session_id in self.session_tokens.keys()
            }
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Token data exported to {filepath}")
        return filepath

# Global token tracker instance
token_tracker = TokenTracker()
