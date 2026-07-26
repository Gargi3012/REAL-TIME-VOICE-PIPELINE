import json
import os
import asyncio
from datetime import datetime
from loguru import logger

LEADS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "leads.json"))

_leads_lock = asyncio.Lock()

async def save_lead(params, name: str, phone: str, project_details: str = ""):
    """Save the caller's lead details (Name, Phone number, and project requirements) to the database.
    
    This tool should ONLY be called after the user has explicitly provided both their name and phone number.
    Do NOT call this tool with placeholder data.
    
    Args:
        name (str): The name of the user/caller.
        phone (str): The phone number of the user/caller.
        project_details (str): Summary of what the user wants to build or their project requirements.
    """
    import re
    # Extract only digits from the provided phone string
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) != 10:
        logger.warning(f"ACTIONABLE AI: 'save_lead' failed validation! Phone '{phone}' has {len(digits)} digits (expected 10).")
        if getattr(params, "result_callback", None):
            await params.result_callback({
                "status": "error", 
                "message": f"Validation Failed: The provided phone number '{phone}' is not a 10-digit number. You MUST tell the user that the number is not 10 digits and explicitly ask them to re-speak their 10-digit phone number."
            })
        return

    # Hash or mask PII in logs
    masked_phone = f"{phone[:3]}******{phone[-4:]}" if len(phone) > 7 else "***"
    logger.info(f"ACTIONABLE AI: Triggered 'save_lead' tool! Name: {name[:2]}***, Phone: {masked_phone}, Project: {project_details}")
    
    lead_entry = {
        "timestamp": datetime.now().isoformat(),
        "name": name,
        "phone": phone,
        "project_details": project_details
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

