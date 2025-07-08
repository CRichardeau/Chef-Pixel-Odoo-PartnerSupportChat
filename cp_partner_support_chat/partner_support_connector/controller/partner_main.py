# -*- coding: utf-8

from odoo import http
from odoo.http import request
import logging
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ClientSupportBridgeController(http.Controller):

    def _authenticate_client(self, db_name, api_key):
        """Authenticate incoming client request"""
        auth_client = request.env['partner.support.connector'].sudo().search([
            ('partner_database', '=', db_name),
            ('api_key', '=', api_key),
            ('is_active', '=', True)
        ], limit=1)

        return True if auth_client else False

    @http.route('/api/client_validate_key', type='json', auth='public', csrf=False, methods=['POST'])
    def initiate_support_session(self, **kw):
        """API endpoint to initiate a support session"""
        data = json.loads(request.httprequest.data.decode('utf-8'))
        # Extract and validate parameters
        db_name = data.get('database')
        api_key = data.get('api_key')

        if not all([db_name, api_key]):
            return {'error': 'Missing required parameters'}

        # Authenticate client
        auth_client = self._authenticate_client(db_name, api_key)
        if not auth_client:
            return {'error': 'Authentication failed'}
        else:
            return {'success': True}

    @http.route('/partner_support_connector/receive_message', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_message(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
            print('\n---client receive message-->', data)
            channel = request.env['discuss.channel'].sudo().search([
                ('id', '=', data.get('channel_id'))
            ])

            if not channel:
                return {'status': 'error', 'message': 'Channel not found'}

            body = data.get('body')
            soup = BeautifulSoup(body, 'html.parser')
            link_text = soup.get_text()

            try:
                result = urlparse(link_text)
                if all([result.scheme, result.netloc]):
                    body = f'<a href="{link_text}" target="_blank">{link_text}</a>'
                else:
                    body = link_text
            except ValueError:
                body = link_text
            msg = channel.with_context(to_bridge=True, mail_create_nosubscribe=True,
                                       mail_create_nolog=True).sudo().message_post(
                body=Markup(f'<p>{body}</p>'),
                author_id=request.env.user.partner_id.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            return {'status': 'success', 'message_id': msg.id}

        except Exception as e:
            _logger.exception("Failed to process message: ")
            return {'status': 'error', 'message': str(e)}
