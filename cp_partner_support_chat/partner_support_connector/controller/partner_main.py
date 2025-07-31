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

            channel = request.env['discuss.channel'].sudo().search([
                ('id', '=', data.get('channel_id'))
            ])
            if not channel:
                return {'status': 'error', 'message': 'Channel not found'}

            partner_id = request.env.user.partner_id
            if 'is_one_partner_talk' in data:
                partner_obj = request.env['res.partner'].sudo()
                support_session = channel.support_session_id
                company_name = support_session.partner_company
                author_name = ''
                if 'author_id' in data:
                    author_id = data.get('author_id')
                    if 'name' in author_id:
                        author_name = author_id.get('name')
                if support_session and not support_session.operator_name:
                    if company_name:
                        company_partner = partner_obj.search([
                            ('name', '=', company_name)
                        ], limit=1)
                        if not company_partner:
                            company_partner = partner_obj.create({
                                'name': company_name,
                                'company_type': 'company'
                            })
                        partner_id = partner_obj.search([
                            ('name', '=', author_name),
                            ('parent_id', '=', company_partner.id)
                        ], limit=1)
                        if not partner_id:
                            partner_id = partner_obj.create({
                                'name': author_name,
                                'company_type': 'person',
                                'parent_id': company_partner.id,
                            })
                        support_session.operator_name = partner_id.name
                        channel.write({
                            'channel_partner_ids': [(4, partner_id.id)],
                            'livechat_operator_id': partner_id.id,
                        })

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
                author_id=partner_id.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            return {'status': 'success', 'message_id': msg.id}

        except Exception as e:
            _logger.exception("Failed to process message: ")
            return {'status': 'error', 'message': str(e)}
