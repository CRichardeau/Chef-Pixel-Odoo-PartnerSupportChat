# -*- coding: utf-8

import requests
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class PartnerSupportConnector(models.Model):
    _name = 'partner.support.connector'
    _description = 'Partner Support Connector'

    name = fields.Char("Connection Name", required=True)
    partner_url = fields.Char("Partner URL", required=True)
    api_key = fields.Char("API Key", required=True)
    is_active = fields.Boolean("Active", default=True)
    partner_database = fields.Char(String="Partner Database", copy=False)

    def test_connection(self):
        """Test the connection to partner support system"""
        try:
            # Just a simple test request to validate connection
            test_url = f"{self.partner_url}/api/validate_key"
            client_db = self.env.cr.dbname
            api_key = self.api_key
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                'api_key': api_key,
                'database': client_db
            }
            response = requests.post(
                test_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Test',
                        'message': 'Successfully connected to partner system',
                        'type': 'success',
                    }
                }
        except Exception as e:
            _logger.error(f"Connection test failed: {str(e)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Connection Test',
                'message': 'Failed to connect to partner system',
                'type': 'danger',
            }
        }
