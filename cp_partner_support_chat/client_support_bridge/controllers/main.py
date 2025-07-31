from odoo import http
from odoo.http import request
import logging
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ClientSupportBridgeController(http.Controller):

    @http.route('/client_support/initiate', type='json', auth='public', csrf=False, methods=['POST'])
    def initiate_support_session(self, **kw):
        """
        API endpoint to initiate a support session
        """
        data = json.loads(request.httprequest.data.decode('utf-8'))

        # Extract and validate parameters
        db_name = data.get('db_name')
        api_key = data.get('api_key')
        user_id = data.get('user_id')
        user_name = data.get('user_name')
        company_name = data.get('company_name')
        client_channel = data.get('client_channel')
        partner_session = data.get('partner_session')
        
        if not all([db_name, api_key, user_id, user_name, company_name]):
            return {'error': 'Missing required parameters'}

        bridge = request.env['client.support.bridge'].sudo().search([
            ('client_db', '=', db_name),
            ('token', '=', api_key),
        ])
        if not bridge:
            return {'error': 'Check Database name and API key.'}

        support_users = request.env['res.users'].sudo().search([])
            
        # Initialize chat session
        result = bridge.initialize_chat_session(user_id, user_name, company_name, client_channel, partner_session,
                                                support_users)
        return result

    @http.route('/client_support_bridge/receive_message', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_message(self, **kwargs):
        try:        
            data = json.loads(request.httprequest.data.decode('utf-8'))

            channel = request.env['discuss.channel'].sudo().search([
                ('id', '=', data.get('channel_id'))
            ])
            if not channel:
                return {'status': 'error', 'message': 'Channel not found'}

            partner_id = request.env.user.partner_id
            if 'author_id' in data:
                author_id = data.get('author_id')
                if 'name' in author_id:
                    author_name = author_id.get('name')
                    partner_id = request.env['res.partner'].sudo().search([
                        ('name', '=', author_name)
                    ], limit=1)

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
            msg = channel.with_context(from_bridge=True,mail_create_nosubscribe=True,mail_create_nolog=True).sudo().message_post(
                body=Markup(f'<p>{body}</p>'),
                author_id=partner_id.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            
            return {'status': 'success', 'message_id': msg.id}

        except Exception as e:
            _logger.exception("Failed to process message: ")
            return {'status': 'error', 'message': str(e)}

    @http.route('/client_support/close_chat', type='json', auth='public', csrf=False, methods=['POST'])
    def close_support_session(self, **kw):
        """
        API endpoint to close a support session
        """
        data = json.loads(request.httprequest.data.decode('utf-8'))

        partner_session = data.get('partner_session')
        db_name = data.get('db_name')
        api_key = data.get('api_key')

        if not all([partner_session, db_name, api_key]):
            return {'error': 'Missing required parameters.'}

        bridge = request.env['client.support.bridge'].sudo().search([
            ('client_db', '=', db_name),
            ('token', '=', api_key),
        ])
        if not bridge:
            return {'error': 'Check Database name and API key.'}

        # Close chat session
        result = bridge.close_chat_session(partner_session)
        return result
