// Frontend Configuration
// This file is dynamically updated by the startup script
window.APP_CONFIG = {
    API_BASE_URL: 'http://localhost:8000',
    APP_NAME: 'AI Doc Read Studio',
    VERSION: '1.0.0',
    frontend: {
        log_level: 'info',
        log_file: 'logs/frontend.log'
    },
    models: {
        available: [
        {
                "value": "nova-micro",
                "label": "Micro (Fast)",
                "description": "Fastest, Basic",
                "bedrock_id": "us.amazon.nova-micro-v1:0"
        },
        {
                "value": "nova-lite",
                "label": "Lite (Balanced)",
                "description": "Balanced",
                "bedrock_id": "us.amazon.nova-lite-v1:0"
        },
        {
                "value": "nova-pro",
                "label": "Pro (Advanced)",
                "description": "Advanced",
                "bedrock_id": "us.amazon.nova-pro-v1:0"
        },
        {
                "value": "nova-premier",
                "label": "Premier (Best)",
                "description": "Best Quality",
                "bedrock_id": "us.amazon.nova-premier-v1:0"
        }
],
        default_team: 'nova-lite',
        default_summary: 'nova-lite'
    }
};