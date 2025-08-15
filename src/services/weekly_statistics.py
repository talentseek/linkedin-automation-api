import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import func, and_
import resend
from src.extensions import db
from src.models import Client, Campaign, Lead, Event, LinkedInAccount

logger = logging.getLogger(__name__)

class WeeklyStatisticsService:
    """Service for generating and sending weekly client statistics."""
    
    def __init__(self):
        self.resend_api_key = os.environ.get('RESEND_API_KEY')
        self.from_email = os.environ.get('NOTIFY_EMAIL_FROM', 'notifications@notifications.costperdemo.com')
        self.enabled = os.environ.get('WEEKLY_STATS_ENABLED', 'false').lower() == 'true'
        
        if self.resend_api_key:
            resend.api_key = self.resend_api_key
            logger.info("Resend API key configured for weekly statistics")
        else:
            logger.warning("No Resend API key found - weekly statistics will be disabled")
            self.enabled = False
    
    def generate_client_statistics(self, client_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate comprehensive statistics for a client."""
        try:
            # Get client details
            client = Client.query.get(client_id)
            if not client:
                return None
            
            # Get all campaigns for this client
            campaigns = Campaign.query.filter_by(client_id=client_id).all()
            campaign_ids = [c.id for c in campaigns]
            
            if not campaign_ids:
                return {
                    'client': client,
                    'period': {'start': start_date, 'end': end_date},
                    'campaigns': [],
                    'summary': {
                        'total_leads': 0,
                        'new_leads': 0,
                        'connections': 0,
                        'replies': 0,
                        'messages_sent': 0,
                        'conversion_rate': 0.0
                    }
                }
            
            # Get leads for this period
            leads = Lead.query.filter(
                Lead.campaign_id.in_(campaign_ids),
                Lead.created_at >= start_date,
                Lead.created_at <= end_date
            ).all()
            
            # Get events for this period
            events = Event.query.filter(
                Event.lead_id.in_([l.id for l in leads]),
                Event.timestamp >= start_date,
                Event.timestamp <= end_date
            ).all()
            
            # Calculate statistics
            total_leads = len(leads)
            new_leads = len([l for l in leads if l.status in ['pending_invite', 'invite_sent', 'invited']])
            connections = len([l for l in leads if l.status in ['connected', 'messaged', 'responded', 'completed']])
            replies = len([e for e in events if e.event_type == 'message_received'])
            messages_sent = len([e for e in events if e.event_type == 'message_sent'])
            
            # Calculate conversion rate
            conversion_rate = (connections / total_leads * 100) if total_leads > 0 else 0.0
            
            # Campaign-specific statistics
            campaign_stats = []
            for campaign in campaigns:
                campaign_leads = [l for l in leads if l.campaign_id == campaign.id]
                campaign_events = [e for e in events if e.lead_id in [l.id for l in campaign_leads]]
                
                campaign_stat = {
                    'campaign': campaign,
                    'total_leads': len(campaign_leads),
                    'new_leads': len([l for l in campaign_leads if l.status in ['pending_invite', 'invite_sent', 'invited']]),
                    'connections': len([l for l in campaign_leads if l.status in ['connected', 'messaged', 'responded', 'completed']]),
                    'replies': len([e for e in campaign_events if e.event_type == 'message_received']),
                    'messages_sent': len([e for e in campaign_events if e.event_type == 'message_sent']),
                    'conversion_rate': (len([l for l in campaign_leads if l.status in ['connected', 'messaged', 'responded', 'completed']]) / len(campaign_leads) * 100) if campaign_leads else 0.0
                }
                campaign_stats.append(campaign_stat)
            
            # Recent activity (last 7 days)
            recent_start = end_date - timedelta(days=7)
            recent_leads = [l for l in leads if l.created_at >= recent_start]
            recent_events = [e for e in events if e.timestamp >= recent_start]
            
            return {
                'client': client,
                'period': {'start': start_date, 'end': end_date},
                'campaigns': campaign_stats,
                'summary': {
                    'total_leads': total_leads,
                    'new_leads': new_leads,
                    'connections': connections,
                    'replies': replies,
                    'messages_sent': messages_sent,
                    'conversion_rate': conversion_rate
                },
                'recent_activity': {
                    'new_leads': len(recent_leads),
                    'new_events': len(recent_events),
                    'recent_replies': len([e for e in recent_events if e.event_type == 'message_received']),
                    'recent_connections': len([e for e in recent_events if e.event_type == 'connection_accepted'])
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating statistics for client {client_id}: {str(e)}")
            return None
    
    def send_weekly_report(self, client_id: str, recipient_email: Optional[str] = None) -> bool:
        """Send weekly statistics report to a client."""
        if not self.enabled:
            logger.info("Weekly statistics disabled - skipping report")
            return False
        
        try:
            # Calculate date range (last 7 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            # Generate statistics
            stats = self.generate_client_statistics(client_id, start_date, end_date)
            if not stats:
                logger.error(f"Failed to generate statistics for client {client_id}")
                return False
            
            # Get recipient email
            if not recipient_email:
                recipient_email = stats['client'].email or f"client-{client_id}@example.com"
            
            # Create email content
            subject = f"📊 Weekly Report: {stats['client'].name} ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
            html_content = self._create_weekly_report_template(stats)
            
            # Send email
            response = resend.Emails.send({
                "from": self.from_email,
                "to": recipient_email,
                "subject": subject,
                "html": html_content
            })
            
            logger.info(f"Weekly report sent to {recipient_email} for client {client_id}: {response.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending weekly report for client {client_id}: {str(e)}")
            return False
    
    def send_all_weekly_reports(self) -> Dict[str, bool]:
        """Send weekly reports to all active clients."""
        if not self.enabled:
            logger.info("Weekly statistics disabled - skipping all reports")
            return {}
        
        try:
            # Get all active clients
            clients = Client.query.filter_by(status='active').all()
            
            results = {}
            for client in clients:
                success = self.send_weekly_report(client.id, client.email)
                results[client.id] = success
            
            logger.info(f"Sent weekly reports to {len(clients)} clients: {sum(results.values())} successful")
            return results
            
        except Exception as e:
            logger.error(f"Error sending all weekly reports: {str(e)}")
            return {}
    
    def _create_weekly_report_template(self, stats: Dict[str, Any]) -> str:
        """Create HTML template for weekly statistics report."""
        client = stats['client']
        summary = stats['summary']
        campaigns = stats['campaigns']
        recent = stats['recent_activity']
        period = stats['period']
        
        # Format dates
        start_str = period['start'].strftime('%B %d, %Y')
        end_str = period['end'].strftime('%B %d, %Y')
        
        # Create campaign rows
        campaign_rows = ""
        for campaign_stat in campaigns:
            campaign = campaign_stat['campaign']
            campaign_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    <strong>{campaign.name}</strong><br>
                    <small style="color: #666;">{campaign.status}</small>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">{campaign_stat['total_leads']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">{campaign_stat['connections']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">{campaign_stat['replies']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">{campaign_stat['conversion_rate']:.1f}%</td>
            </tr>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #0077b5, #005885); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #0077b5; }}
                .stat-label {{ color: #666; margin-top: 5px; }}
                .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .table th {{ background: #0077b5; color: white; padding: 15px; text-align: left; }}
                .table td {{ padding: 12px; border-bottom: 1px solid #eee; }}
                .highlight {{ background: #e3f2fd; padding: 20px; border-left: 4px solid #2196f3; margin: 20px 0; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Weekly LinkedIn Automation Report</h1>
                    <p><strong>{client.name}</strong> • {start_str} - {end_str}</p>
                </div>
                
                <div class="content">
                    <h2>📈 Performance Summary</h2>
                    
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-number">{summary['total_leads']}</div>
                            <div class="stat-label">Total Leads</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{summary['connections']}</div>
                            <div class="stat-label">Connections</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{summary['replies']}</div>
                            <div class="stat-label">Replies</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{summary['conversion_rate']:.1f}%</div>
                            <div class="stat-label">Conversion Rate</div>
                        </div>
                    </div>
                    
                    <div class="highlight">
                        <h3>🚀 Recent Activity (Last 7 Days)</h3>
                        <p><strong>{recent['new_leads']}</strong> new leads • <strong>{recent['recent_connections']}</strong> new connections • <strong>{recent['recent_replies']}</strong> new replies</p>
                    </div>
                    
                    <h2>📋 Campaign Breakdown</h2>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Campaign</th>
                                <th style="text-align: center;">Total Leads</th>
                                <th style="text-align: center;">Connections</th>
                                <th style="text-align: center;">Replies</th>
                                <th style="text-align: center;">Conversion Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                            {campaign_rows}
                        </tbody>
                    </table>
                    
                    <div class="highlight">
                        <h3>💡 Key Insights</h3>
                        <ul>
                            <li>Your campaigns generated <strong>{summary['total_leads']}</strong> leads this week</li>
                            <li>Connection rate: <strong>{summary['conversion_rate']:.1f}%</strong></li>
                            <li>Engagement rate: <strong>{(summary['replies'] / summary['connections'] * 100) if summary['connections'] > 0 else 0:.1f}%</strong> of connections replied</li>
                            <li>Total messages sent: <strong>{summary['messages_sent']}</strong></li>
                        </ul>
                    </div>
                    
                    <h2>🎯 Next Steps</h2>
                    <p>Based on this week's performance, we recommend:</p>
                    <ul>
                        <li>Review and respond to the <strong>{summary['replies']}</strong> leads who replied</li>
                        <li>Monitor campaigns with lower conversion rates</li>
                        <li>Consider optimizing messaging for better engagement</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>This report was automatically generated by LinkedIn Automation API</p>
                    <p>Report period: {start_str} - {end_str}</p>
                    <p>Need help? Contact your automation specialist.</p>
                </div>
            </div>
        </body>
        </html>
        """

# Global service instance
_weekly_stats_service = None

def get_weekly_statistics_service() -> WeeklyStatisticsService:
    """Get the global weekly statistics service instance."""
    global _weekly_stats_service
    if _weekly_stats_service is None:
        _weekly_stats_service = WeeklyStatisticsService()
    return _weekly_stats_service
