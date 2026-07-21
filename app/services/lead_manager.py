import json
import os
import asyncio
from datetime import datetime
from loguru import logger

LEADS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "leads.json"))

_leads_lock = asyncio.Lock()

async def save_lead(params, name: str, phone: str):
    # Hash or mask PII in logs
    masked_phone = f"{phone[:3]}******{phone[-4:]}" if len(phone) > 7 else "***"
    logger.info(f"ACTIONABLE AI: Triggered 'save_lead' tool! Name: {name[:2]}***, Phone: {masked_phone}")
    
    lead_entry = {
        "timestamp": datetime.now().isoformat(),
        "name": name,
        "phone": phone
    }
    
    try:
        async with _leads_lock:
            leads = []
            if os.path.exists(LEADS_FILE):
                with open(LEADS_FILE, "r") as f:
                    content = f.read().strip()
                    if content:
                        leads = json.loads(content)
            
            leads.append(lead_entry)
            
            with open(LEADS_FILE, "w") as f:
                json.dump(leads, f, indent=4)
            
        logger.info(f"Lead saved successfully to {LEADS_FILE}")
        
        # Return success back to the LLM so it can inform the user
        if getattr(params, "result_callback", None):
            await params.result_callback({"status": "success", "message": "Lead saved successfully."})
        
    except Exception as e:
        logger.error(f"Failed to save lead: {e}")
        if getattr(params, "result_callback", None):
            await params.result_callback({"status": "error", "message": "Failed to save lead."})

