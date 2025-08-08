import os
import json
import logging
from typing import Optional, Dict, Any

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def _get_config() -> Dict[str, Any]:
    cfg = {
        'enabled': bool(current_app.config.get('NOTIFICATIONS_ENABLED')),
        'resend_api_key': current_app.config.get('RESEND_API_KEY'),
        'email_to': current_app.config.get('NOTIFY_EMAIL_TO') or '',
        'email_from': current_app.config.get('NOTIFY_EMAIL_FROM') or 'notifications@localhost',
    }
    return cfg


def _send_resend_email(subject: str, html: str) -> bool:
    cfg = _get_config()
    if not cfg['enabled']:
        logger.debug('Notifications disabled; skipping Resend email')
        return False
    if not cfg['resend_api_key']:
        logger.warning('RESEND_API_KEY missing; cannot send email notification')
        return False
    recipients = [e.strip() for e in (cfg['email_to'] or '').split(',') if e.strip()]
    if not recipients:
        logger.warning('NOTIFY_EMAIL_TO not configured; cannot send email notification')
        return False
    try:
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {cfg["resend_api_key"]}',
                'Content-Type': 'application/json',
            },
            data=json.dumps({
                'from': cfg['email_from'],
                'to': recipients,
                'subject': subject,
                'html': html,
            }),
            timeout=10,
        )
        if 200 <= resp.status_code < 300:
            logger.info('Resend email sent')
            return True
        logger.error(f'Resend email failed: {resp.status_code} {resp.text}')
        return False
    except Exception as e:
        logger.error(f'Resend email exception: {str(e)}')
        return False


def notify_lead_replied(lead: Any, campaign: Any, message_preview: Optional[str] = None) -> None:
    """Send a notification that a lead has replied.

    lead: Lead model
    campaign: Campaign model
    message_preview: optional short text
    """
    try:
        subject = f"Lead replied: {lead.full_name} ({lead.company_name or 'Unknown Company'})"
        html = f"""
        <h3>Lead replied</h3>
        <p><strong>Lead:</strong> {lead.full_name}</p>
        <p><strong>Company:</strong> {lead.company_name or ''}</p>
        <p><strong>Campaign:</strong> {campaign.name if campaign else ''}</p>
        {f'<p><strong>Preview:</strong> {message_preview}</p>' if message_preview else ''}
        <p>Status has been set to <strong>responded</strong> and automation will not continue for this lead.</p>
        """
        _send_resend_email(subject, html)
    except Exception as e:
        logger.error(f"notify_lead_replied failed: {str(e)}")


